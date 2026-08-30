"""卡優惠 CardPerks — 人工審核 CLI（LLM 產出未經審核不得上架）

用法：
    cd backend
    python pipeline/review.py list              # 列出待審
    python pipeline/review.py show 3            # 看單筆
    python pipeline/review.py approve 3 8       # 核可（可多筆）
    python pipeline/review.py reject 5          # 退件（可多筆）

審核通過 → out/approved_offers.jsonl
之後重啟 app.py 會自動匯入資料庫（seed.load_approved）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
PENDING = os.path.join(OUT_DIR, "pending_offers.jsonl")
APPROVED = os.path.join(OUT_DIR, "approved_offers.jsonl")
REJECTED = os.path.join(OUT_DIR, "rejected_offers.jsonl")


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    pending = read_jsonl(PENDING)

    if cmd == "list":
        if not pending:
            print("沒有待審項目")
            return
        for o in pending:
            print(f"#{o.get('id', '?'):>3} [{o.get('card_name')}] @ {o.get('merchant_name')}"
                  f" | {o.get('reward_rate')}% 上限{'' if not o.get('monthly_cap') else o['monthly_cap']}"
                  f" | 到 {o.get('ends_on')} | {'需登錄' if o.get('requires_login') else ''}"
                  f" {o.get('pay_channel', 'any')} | {o.get('source_url', '')[:60]}")
        print(f"\n共 {len(pending)} 筆待審")

    elif cmd == "show":
        o = next((x for x in pending if str(x.get("id")) == sys.argv[2]), None)
        print(json.dumps(o, ensure_ascii=False, indent=2) if o else "找不到該 id")

    elif cmd in ("approve", "reject"):
        ids = set(sys.argv[2:])
        picked = [o for o in pending if str(o.get("id")) in ids]
        # 給沒有 id 的行補編號（llm_parse 產出通常無 id）
        if not picked and pending:
            for i, o in enumerate(pending, 1):
                o.setdefault("id", i)
            picked = [o for o in pending if str(o["id"]) in ids]
        if not picked:
            print("找不到指定 id（先用 list 查看編號）")
            return
        rest = [o for o in pending if o not in picked]
        target = APPROVED if cmd == "approve" else REJECTED
        write_jsonl(target, read_jsonl(target) + picked)
        write_jsonl(PENDING, rest)
        print(f"{cmd} {len(picked)} 筆 → {target}")
        if cmd == "approve":
            print("重啟 app.py（或其啟動程序）即匯入資料庫")

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
