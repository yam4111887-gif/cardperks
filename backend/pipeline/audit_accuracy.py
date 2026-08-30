"""卡優惠 CardPerks — 資料準確度稽核（Accuracy Audit）

抽樣「已上架且附官方來源」的優惠，重新造訪來源頁面，比對關鍵事實：
- 回饋率（如 3.3%）或折扣文字（如 62折）是否仍出現在頁面
- 截止日（多種日期格式變體）是否仍出現

結論分級：
  ✅ 一致     —— 數字與日期都找得到
  ⚠️ 待人工   —— 找到部分（可能格式改變或改版）
  ❌ 疑似失效 —— 全部找不到（頁面可能已更新/活動結束，建議人工查核後下架）

用法：
    cd backend && python pipeline/audit_accuracy.py [--sample 8]
輸出：pipeline/out/accuracy_report.md
法遵：與爬蟲同一組 UA／robots.txt／限速規則。
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import get_engine, Offer, Card, Merchant  # noqa: E402
from crawler import UA, robots_allows, REQUEST_INTERVAL_SEC  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "out", "accuracy_report.md")


def rate_variants(rate: float):
    """3.3 → ['3.3%']；5.0 → ['5%', '5.0%']；20.0 → ['20%', '20.0%', '20％']"""
    out = []
    if rate == int(rate):
        out += [f"{int(rate)}%", f"{int(rate)}％", f"{int(rate)} %"]
        out += [f"{rate:.1f}%", f"{rate:.1f}％"]
    else:
        out += [f"{rate}%", f"{rate}％", f"{rate} %"]
    return out


def date_variants(ends_on: str):
    """'2026-08-31' → 常見台灣網站日期寫法變體"""
    y, m, d = ends_on.split("-")
    mi, di = str(int(m)), str(int(d))
    return [
        f"{y}/{m}/{d}", f"{y}/{mi}/{di}", f"{y}.{m}.{d}", f"{y}.{mi}.{di}",
        f"{y}-{m}-{d}", f"{y}年{m}月{d}日", f"{y}年{mi}月{di}日",
        f"{m}/{d}", f"{mi}/{di}", f"{m}.{d}", f"{mi}.{di}",
    ]


def _norm(s: str) -> str:
    return re.sub(r"[$,，,。\s]", "", s)


def check_offer(text: str, o: Offer):
    """回傳 (等級, 細節)"""
    if not text:
        return "❌", "頁面無內容（可能已下架或改版）"
    hits, misses = [], []
    if o.reward_note:
        n = _norm(o.reward_note)
        t = _norm(text)
        nums = re.findall(r"\d+", n)
        found = (n in t) or (nums and all(x in t for x in nums))
        (hits if found else misses).append(f"note:{o.reward_note}")
    else:
        found = any(v in text for v in rate_variants(float(o.reward_rate)))
        (hits if found else misses).append(f"rate:{float(o.reward_rate)}%")
    found_d = any(v in text for v in date_variants(o.ends_on.isoformat()))
    (hits if found_d else misses).append(f"end:{o.ends_on}")
    if hits and not misses:
        return "✅", "、".join(hits)
    if hits:
        return "⚠️", f"找到 {'、'.join(hits)}；未見 {'、'.join(misses)}（格式改變？）"
    return "❌", "關鍵事實皆未出現於頁面（疑似已失效）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=8)
    args = ap.parse_args()

    engine = get_engine()
    with Session(engine) as db:
        rows = (db.query(Offer, Card, Merchant)
                .join(Card, Offer.card_id == Card.id)
                .outerjoin(Merchant, Offer.merchant_id == Merchant.id)
                .filter(Offer.status == "approved",
                        Offer.source_url.isnot(None),
                        ~Offer.source_url.like("%example.com%"))
                .all())
        if not rows:
            sys.exit("沒有附官方來源的上架優惠可稽核")

        import random
        random.seed(42)  # 可重現抽樣
        sample = random.sample(rows, min(args.sample, len(rows)))
        print(f"稽核 {len(sample)} / {len(rows)} 筆（固定種子抽樣）")

        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(user_agent=UA, locale="zh-TW").new_page()
            # 同一來源頁只抓一次（避免短時間重複請求同一頁被站方限流）
            page_cache = {}
            urls = []
            for o, c, m in sample:
                if o.source_url not in page_cache:
                    urls.append(o.source_url)
                    page_cache[o.source_url] = None
            for i, url in enumerate(urls):
                if i > 0:
                    time.sleep(REQUEST_INTERVAL_SEC)
                if not robots_allows(url):
                    continue
                text = ""
                try:
                    for attempt in (1, 2):  # ❌ 判定前重試一次（JS 渲染/偶發限流）
                        try:
                            page.goto(url, timeout=45000, wait_until="networkidle")
                        except Exception:
                            pass  # networkidle 超時仍用已載入內容
                        page.wait_for_timeout(4000)
                        soup = BeautifulSoup(page.content(), "html.parser")
                        for tag in soup(["script", "style", "noscript"]):
                            tag.decompose()
                        text = soup.get_text(" ", strip=True)
                        if len(text) > 500:
                            break
                        if attempt == 1:
                            time.sleep(REQUEST_INTERVAL_SEC * 2)
                except Exception as e:
                    print(f"  [WARN] {url[:60]} 造訪失敗 {type(e).__name__}")
                page_cache[url] = text
            for o, c, m in sample:
                label = f"{c.name} @ {(m.name if m else '?')}"
                text = page_cache.get(o.source_url) or ""
                grade, detail = check_offer(text, o)
                results.append((label, o, grade, detail))
                print(f"  {grade} {label}（{detail[:40]}）")
            browser.close()

    ok = sum(1 for *_, g, _ in [(r[0], r[1], r[2], r[3]) for r in results] if g == "✅")
    warn = sum(1 for r in results if r[2] == "⚠️")
    bad = sum(1 for r in results if r[2] == "❌")

    lines = [
        "# 資料準確度稽核報告",
        f"時間：{datetime.now(timezone.utc).isoformat()}",
        f"抽樣：{len(results)} 筆（母體 {len(rows)} 筆附官方來源之上架優惠）",
        "",
        f"結果：✅ 一致 {ok} 筆 · ⚠️ 待人工 {warn} 筆 · ❌ 疑似失效 {bad} 筆",
        "",
        "## 明細",
    ]
    for label, o, grade, detail in results:
        lines.append(f"- {grade} **{label}**｜{float(o.reward_rate)}%"
                     f"{'（' + o.reward_note + '）' if o.reward_note else ''}｜至 {o.ends_on}｜{detail}")
        lines.append(f"  - 來源：{o.source_url}")
    lines += ["", "## 處理原則",
              "- ❌ 疑似失效 → 人工開來源頁確認，若活動已結束/改版：下架（review/DB 改 status）或更新資料",
              "- ⚠️ 待人工 → 多為日期格式差異或頁面改版，人工確認後更新查核時間",
              "- 建議排程：每天 daily.py 後跑一次，每週至少全量抽查一輪"]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n報告 → {REPORT}")
    print(f"結論：✅ {ok} / ⚠️ {warn} / ❌ {bad}")


if __name__ == "__main__":
    main()
