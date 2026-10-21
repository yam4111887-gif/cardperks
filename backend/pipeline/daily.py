"""卡優惠 CardPerks — 每日資料執行器：爬取 → 差異報告 →（人工審核）→ 匯入

流程：
    1. 執行爬蟲（crawler.py）抓最新頁面
    2. 與 approved_offers.jsonl 比對，產出 out/diff_report.md：
       - NEW      新出現的活動（待解析＋審核）
       - GONE     已上架來源在本次爬取中消失（可能已結束，待人工確認下架）
    3. 提醒下一步：llm_parse.py → review.py → 重啟 app.py

排程（擇一）：
    Windows：工作排程器每天 08:00 執行 python pipeline/daily.py
    Linux/Mac：cron → 0 8 * * * cd /path/backend && python pipeline/daily.py
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
CRAWLED = os.path.join(OUT_DIR, "crawled_items.jsonl")
APPROVED = os.path.join(OUT_DIR, "approved_offers.jsonl")
REPORT = os.path.join(OUT_DIR, "diff_report.md")


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    print("=== CardPerks 每日資料執行 ===")
    # 0) 資料庫初始化與過期下架（全新資料庫也能跑：建表→種子→匯入→下架）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models import get_engine, Base
    from seed import ensure_seed, load_approved, expire_offers
    from sqlalchemy.orm import Session

    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ensure_seed(db)          # 空庫時種入示範資料（冪等）
        load_approved(db)        # 匯入 repo 中已審核的優惠（冪等）
        n = expire_offers(db)
        if n:
            print(f"已下架 {n} 筆過期優惠")

    # 1) 爬蟲
    r = subprocess.run([sys.executable, os.path.join(HERE, "crawler.py")],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-800:] if r.stdout else "")
    if r.returncode != 0:
        print("爬蟲失敗：", (r.stderr or "")[-400:])
        sys.exit(1)

    # 2) 準確度稽核（抽樣複查來源頁）
    r2 = subprocess.run([sys.executable, os.path.join(HERE, "audit_accuracy.py"), "--sample", "6"],
                        capture_output=True, text=True, encoding="utf-8")
    print(r2.stdout[-400:] if r2.stdout else "")
    if r2.returncode != 0:
        print("稽核失敗（不中斷）:", (r2.stderr or "")[-200:])

    # 3) 差異比對（智慧去重：URL 正規化＋銀行×商家覆蓋＋噪音過濾）
    write_report()


# ---------- 差異報告（獨立函式：--diff-only 可單獨呼叫，秒級重新審計） ----------

import re

NOISE_PATTERNS = (
    "信貸", "房貸", "登錄專區", "活動登錄", "已登錄", "優惠總覽", "活動專區｜",
    "一覽表", "卡友服務", "申請進度", "信用卡 -", "IG_", "國際組織優惠", "Bank ",
    "官網", "最新優惠活動", "一卡在手",
)
NOISE_URL_PATTERNS = ("personalloan", "/loan/", "mortgage", "/mkt/loan")


def _norm_url(u: str) -> str:
    """URL 正規化：去 query/fragment/結尾斜線、小寫 host，讓比對不受參數差異影響"""
    try:
        u = u.split("#")[0].split("?")[0]
        return u.rstrip("/").lower()
    except Exception:
        return u or ""


def _is_noise(item) -> bool:
    t = item.get("title", "")
    u = item.get("url", "")
    if not t or t.strip() == item.get("bank_name", "").strip():
        return True
    if any(p in u.lower() for p in NOISE_URL_PATTERNS):
        return True
    return any(p in t for p in NOISE_PATTERNS)


def _covered(item, approved_pairs) -> bool:
    """同銀行×同商家已有上架優惠 → 視為已涵蓋（不論活動頁 URL 差異）"""
    for bank, mkey in approved_pairs:
        if item.get("bank") == bank and mkey and mkey in item.get("title", ""):
            return True
    return False


def write_report():
    crawled_items = read_jsonl(CRAWLED)
    crawled_urls = {_norm_url(c.get("url", "")) for c in crawled_items}
    approved = read_jsonl(APPROVED)
    approved_src = {_norm_url(a.get("source_url") or "") for a in approved}
    # 每筆已上架優惠 → (bank, 商家名關鍵字取前 4 字) 簽名
    approved_pairs = set()
    for a in approved:
        mn = (a.get("merchant_name") or "").replace("（", "(").split("(")[0][:4]
        approved_pairs.add((a.get("bank"), mn))

    new_items, covered_items, noise_items = [], [], []
    for c in crawled_items:
        if not c.get("detail_text"):
            continue
        if _norm_url(c.get("url", "")) in approved_src:
            continue  # 同來源頁已上架
        if _is_noise(c):
            noise_items.append(c)
        elif _covered(c, approved_pairs):
            covered_items.append(c)
        else:
            new_items.append(c)

    gone = [a for a in approved if _norm_url(a.get("source_url") or "") not in crawled_urls]

    lines = [
        "# 每日差異報告",
        f"產出時間：{datetime.now(timezone.utc).isoformat()}",
        "",
        f"- 本次爬取連結：{len(crawled_items)} 條（噪音過濾 {len(noise_items)}／已涵蓋 {len(covered_items)}）",
        f"- 已上架優惠：{len(approved)} 筆",
        "",
        f"## 🆕 新活動（{len(new_items)}，待審核）",
    ]
    lines += [f"- [{c['bank_name']}] {c['title']} → {c['url']}" for c in new_items] or ["- 無（全部已涵蓋或噪音）"]
    lines += ["", f"## ♻️ 已涵蓋（{len(covered_items)}，同銀行×商家已有上架，略過）"]
    lines += [f"- [{c['bank_name']}] {c['title'][:50]}" for c in covered_items[:8]] or ["- 無"]
    if len(covered_items) > 8:
        lines.append(f"- …等共 {len(covered_items)} 條")
    lines += ["", f"## ⚠️ 疑似結束（{len(gone)}，待人工確認下架）"]
    lines += [f"- [{a.get('bank_name', a.get('bank', ''))}] {a.get('card_name')} @ {a.get('merchant_name')}（來源已消失）" for a in gone] or ["- 無"]
    lines += ["", "## 下一步", "1. 只看 🆕 區：值得上架的寫入 pending → `review.py approve` → push", "2. `python pipeline/daily.py --diff-only` 可隨時秒級重新產生本報告"]

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n報告 → {REPORT}")
    print(f"🆕 新活動 {len(new_items)} / ♻️ 已涵蓋 {len(covered_items)} / 🔇 噪音 {len(noise_items)} / ⚠️ 疑似結束 {len(gone)}")


if __name__ == "__main__":
    if "--diff-only" in sys.argv:
        write_report()
    else:
        main()
