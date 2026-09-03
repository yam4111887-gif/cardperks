"""匯出靜態資料檔（供純靜態站使用）：DB → web/data/*.json

GitHub Actions 每日執行後提交回 repo，靜態託管（Vercel/GitHub Pages）
即自動取得最新資料，無需任何後端。
"""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import get_engine, Bank, Card, Merchant, MerchantLocation, Offer  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "web", "data")


def card_to_dict(c):
    return {"slug": c.slug, "name": c.name,
            "bank": {"code": c.bank.code, "name": c.bank.name, "short_name": c.bank.short_name},
            "base_reward": float(c.base_reward or 0), "base_note": c.base_note}


def main():
    os.makedirs(OUT, exist_ok=True)
    with Session(get_engine()) as db:
        cards = [card_to_dict(c) for c in db.query(Card).filter_by(is_active=True).all()]

        locs = {}
        for l in db.query(MerchantLocation).all():
            locs.setdefault(l.merchant_id, []).append(
                {"name": l.name, "lat": float(l.lat), "lng": float(l.lng)})
        merchants = [{"slug": m.slug, "name": m.name, "category": m.category,
                      "is_online": m.is_online, "aliases": (m.aliases or "").split(","),
                      "locations": locs.get(m.id, [])}
                     for m in db.query(Merchant).all()]

        PAY = {"any": "不限", "line_pay": "LINE Pay", "pi_wallet": "Pi 拍錢包",
               "tap": "行動支付", "other": "限特定支付"}
        card_by_id = {c.id: c for c in db.query(Card).all()}
        merch_by_id = {m.id: m for m in db.query(Merchant).all()}
        offers = []
        for o in db.query(Offer).filter_by(status="approved").all():
            c = card_by_id[o.card_id]
            m = merch_by_id.get(o.merchant_id)
            if not m:
                continue
            offers.append({
                "card": {"slug": c.slug, "name": c.name,
                         "bank": {"code": c.bank.code, "name": c.bank.name, "short_name": c.bank.short_name}},
                "merchant": {"slug": m.slug, "name": m.name, "category": m.category},
                "reward_rate": float(o.reward_rate),
                "reward_note": o.reward_note,
                "monthly_cap": float(o.monthly_cap or 0),
                "requires_login": bool(o.requires_login),
                "pay_channel": PAY.get(o.pay_channel, "不限"),
                "terms": o.terms,
                "starts_on": o.starts_on.isoformat() if o.starts_on else None,
                "ends_on": o.ends_on.isoformat(),
                "days_left": (o.ends_on - date.today()).days,
                "source_url": o.source_url,
                "verified_at": o.verified_at.isoformat() if o.verified_at else None,
            })

        bank_stat = {}
        for o in offers:
            code = o["card"]["bank"]["code"]
            st = bank_stat.setdefault(code, {"code": code, "name": o["card"]["bank"]["name"], "offers": 0})
            st["offers"] += 1
        coverage = {
            "total_offers": len(offers),
            "official_sourced_offers": sum(1 for o in offers
                                           if o["source_url"] and "example.com" not in o["source_url"]),
            "banks": sorted(bank_stat.values(), key=lambda b: -b["offers"]),
            "last_verified_at": max((o["verified_at"] for o in offers if o["verified_at"]), default=None),
            "update_frequency": "每日自動爬取（GitHub Actions），人工審核後上架",
            "generated_at": date.today().isoformat(),
            "methodology": "資料整理自各發卡銀行官方網站公開頁面，每筆優惠保留原始來源連結與查核時間供使用者驗證；發現缺漏或錯誤可透過「回報錯誤」通知我們修正。",
        }

    datasets = {"cards": cards, "merchants": merchants, "offers": offers, "coverage": coverage}
    for name, data in datasets.items():
        path = os.path.join(OUT, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"{name}.json: {len(data)} 筆")


if __name__ == "__main__":
    main()
