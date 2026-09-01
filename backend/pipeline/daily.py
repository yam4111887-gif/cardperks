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

    # 3) 差異比對（以來源 URL 為鍵）
    crawled = {c["url"] for c in read_jsonl(CRAWLED)}
    approved = read_jsonl(APPROVED)
    approved_src = {a.get("source_url") for a in approved}

    new_items = [c for c in read_jsonl(CRAWLED)
                 if c["url"] not in approved_src and c.get("detail_text")]
    gone = [a for a in approved if a.get("source_url") not in crawled]

    lines = [
        "# 每日差異報告",
        f"產出時間：{datetime.now(timezone.utc).isoformat()}",
        "",
        f"- 本次爬取連結：{len(crawled)} 條",
        f"- 已上架優惠：{len(approved)} 筆",
        "",
        f"## 🆕 新活動（{len(new_items)}，待解析審核）",
    ]
    lines += [f"- [{c['bank_name']}] {c['title']} → {c['url']}" for c in new_items] or ["- 無"]
    lines += ["", f"## ⚠️ 疑似結束（{len(gone)}，待人工確認下架）"]
    lines += [f"- [{a.get('bank_name', a.get('bank', ''))}] {a.get('card_name')} @ {a.get('merchant_name')}（來源已消失：{a.get('source_url', '')[:80]}）" for a in gone] or ["- 無"]
    lines += ["", "## 下一步", "1. `python pipeline/llm_parse.py`（或人工）解析新活動", "2. `python pipeline/review.py list` → approve", "3. 重啟 app.py 匯入"]

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n報告 → {REPORT}")
    print(f"新活動 {len(new_items)} 條 / 疑似結束 {len(gone)} 筆")


if __name__ == "__main__":
    main()
