"""卡優惠 CardPerks — LLM 解析（爬蟲結果 → 結構化優惠草稿，status=pending）

用法：
    cd backend
    python pipeline/llm_parse.py            # 讀 crawled_items.jsonl → pending_offers.jsonl

環境變數（GLM / OpenAI 皆可，端點相容）：
    LLM_PROVIDER     glm（預設建議，glm-4-flash 免費）| openai
    LLM_API_KEY      智譜 BigModel 或 OpenAI 的 API key
                     （注意：GLM Coding Plan 是綁開發工具的訂閱，不能當 API key 用，
                       需到 open.bigmodel.cn 另申請 API key）
    LLM_BASE_URL     覆寫端點（一般不用設）
    LLM_MODEL        覆寫模型（GLM 預設 glm-4-flash；OpenAI 預設 gpt-4o-mini）
    相容 OPENAI_API_KEY / OPENAI_BASE_URL 舊名

法遵注意：
- 解析對象為「公開頁面之事實資訊」（回饋率/期間/條件），LLM 需附來源 URL，不逐字重製原文
- 產出一律 status=pending，未經人工審核（review.py）不得上架（approved）
- 本管線不含任何使用者個資（只解析銀行公開頁面），跨境處理風險低
"""
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
CRAWLED = os.path.join(OUT_DIR, "crawled_items.jsonl")
PENDING = os.path.join(OUT_DIR, "pending_offers.jsonl")

REQUIRED_FIELDS = ["card_slug", "card_name", "merchant_slug", "merchant_name",
                   "reward_rate", "ends_on", "source_url"]

SYSTEM_PROMPT = """你是信用卡優惠資料結構化助理。請把提供的優惠頁面資訊解析成 JSON 物件陣列。
規則：
1. 只輸出 JSON 陣列，不要任何其他文字。
2. 每個物件欄位：
   - card_slug: 卡片英文代稱（自訂小寫英文，如 ubear_icash）
   - card_name: 卡片中文名稱（從標題判斷，如「U Bear 卡」）
   - merchant_slug / merchant_name: 適用商家（全通路則用 "all" / "全部通路"）
   - category: 類別（網購/行動支付/超市/超商/餐廳/加油/娛樂/其他）
   - reward_rate: 回饋率數字（%，如 3.8）
   - monthly_cap: 每月回饋上限（新台幣，無上限為 0）
   - requires_login: 是否需要登錄（true/false）
   - pay_channel: 限定支付（any/line_pay/pi_wallet/tap/other）
   - starts_on / ends_on: 日期 YYYY-MM-DD，未知給 null（ends_on 必填，無期限給當季末）
   - terms: 其他條款摘要（用自己的話改寫，不得逐字複製原文）
   - source_url: 來源網址
3. 無法從標題判斷的欄位給合理預設並在 terms 註明「待人工確認」。
4. 事實數據必須忠於來源，不得推測數字。"""


def build_user_prompt(items):
    lines = [f"來源清單（共 {len(items)} 條）："]
    for it in items:
        lines.append(f"- 銀行:{it['bank_name']} | 標題:{it['title']} | URL:{it['url']}")
    lines.append("請解析以上每一條為一個 JSON 物件。")
    return "\n".join(lines)


PROVIDER_DEFAULTS = {
    "glm": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
}


def llm_config():
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    def_base, def_model = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    api_key = (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    base = (os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or def_base).rstrip("/")
    model = os.environ.get("LLM_MODEL") or def_model
    return api_key, base, model


def call_llm(items):
    api_key, base, model = llm_config()
    if not api_key:
        return None
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(items)},
            ],
            "temperature": 0,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def validate(raw_text, crawled):
    """抽出 JSON、檢查必要欄位，補上 pending 狀態"""
    start, end = raw_text.find("["), raw_text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("LLM 輸出中找不到 JSON 陣列")
    arr = json.loads(raw_text[start:end + 1])
    valid = []
    for o in arr:
        missing = [f for f in REQUIRED_FIELDS if f not in o or o[f] in (None, "")]
        if missing:
            print(f"[DROP] 缺欄位 {missing}：{o.get('card_name', '?')}")
            continue
        o["status"] = "pending"
        o["parsed_at"] = crawled[0]["fetched_at"] if crawled else None
        valid.append(o)
    return valid


def main():
    if not os.path.exists(CRAWLED):
        sys.exit(f"找不到 {CRAWLED}，請先執行 python pipeline/crawler.py")

    with open(CRAWLED, encoding="utf-8") as f:
        items = [json.loads(l) for l in f if l.strip()]
    print(f"讀入 {len(items)} 條爬蟲結果")

    result = call_llm(items)
    if result is None:
        print("未設定 LLM_API_KEY —— 以下 prompt 可手動貼給任何 LLM（含 GLM）使用：\n")
        print(SYSTEM_PROMPT)
        print(build_user_prompt(items))
        sys.exit(0)

    offers = validate(result, items)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(PENDING, "w", encoding="utf-8") as f:
        for o in offers:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"解析完成：{len(offers)} 筆待審核 → {PENDING}")
    print("下一步：python pipeline/review.py list")


if __name__ == "__main__":
    main()
