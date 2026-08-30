"""卡優惠 CardPerks — 商家地理編碼（Nominatim / OpenStreetMap）

對「實體型但沒有座標」的商家查詢座標並寫入 merchant_locations，
讓地圖模式顯示爬蟲抓到的真實商家。

Nominatim 使用政策：自識別 UA、每秒最多 1 請求（本腳本間隔 1.2 秒）。
用法：cd backend && python pipeline/geocode.py [--city 台北]
"""
import argparse
import os
import sys
import time

import requests
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import get_engine, Merchant, MerchantLocation

UA = "Mozilla/5.0 (compatible; CardPerksBot/0.1; +https://cardperks.example.com/bot)"
BASE = "https://nominatim.openstreetmap.org/search"


def geocode(query, city):
    params = {"q": f"{query} {city}", "format": "json", "limit": 1, "countrycodes": "tw"}
    r = requests.get(BASE, params=params, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="台北")
    args = ap.parse_args()

    engine = get_engine()
    with Session(engine) as db:
        have = {l.merchant_id for l in db.query(MerchantLocation).all()}
        targets = [m for m in db.query(Merchant).all()
                   if not m.is_online and m.id not in have]
        print(f"待編碼商家 {len(targets)} 家（城市基準：{args.city}）")
        added = 0
        for m in targets:
            time.sleep(1.2)  # Nominatim 政策：≤1 req/s
            try:
                res = geocode(m.name, args.city)
            except Exception as e:
                print(f"  [FAIL] {m.name}: {type(e).__name__}")
                continue
            if res:
                lat, lng, disp = res
                db.add(MerchantLocation(merchant_id=m.id, name=disp[:40], lat=lat, lng=lng))
                added += 1
                print(f"  [OK  ] {m.name} → ({lat:.5f}, {lng:.5f}) {disp[:40]}")
            else:
                print(f"  [MISS] {m.name}：查無結果")
        db.commit()
        print(f"\n新增 {added} 筆座標，重啟 app.py 後 /api/merchants 即帶座標")


if __name__ == "__main__":
    main()
