"""種子資料：示範資料（與原型一致）＋ 匯入管線審核通過的優惠"""
import json
import os
from datetime import date, datetime

from models import Base, Bank, Card, Merchant, MerchantLocation, Offer, User, UserCard


def to_date(s):
    """ISO 字串 → date（容忍 None / date）"""
    if s is None or isinstance(s, date):
        return s
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None

DEMO_VERIFIED_AT = "2026-08-16T09:00:00"

BANKS = [
    ("taishin", "台新銀行", "台新"),
    ("cathay", "國泰世華", "國泰"),
    ("esun", "玉山銀行", "玉山"),
    ("fubon", "富邦銀行", "富邦"),
    ("sinopac", "永豐銀行", "永豐"),
    ("ctbc", "中國信託", "中信"),
    ("tfb", "台北富邦", "北富邦"),
]

CARDS = [
    ("gogo", "taishin", "@GoGo icash 聯名卡", 1.0, "一般 1%．數位帳戶加碼"),
    ("cube", "cathay", "CUBE 卡", 3.3, "App 切換方案最高 3.3%"),
    ("ubear", "esun", "U Bear 卡", 1.0, "一般 1%．網購/行動支付加碼"),
    ("pi", "esun", "Pi 拍錢包信用卡", 4.5, "Pi 支付 4.5% 起跳"),
    ("jcard", "fubon", "J 卡", 1.0, "國內 1% 無上限"),
    ("dabao", "sinopac", "幣倍卡", 3.0, "指定數位通路 3%"),
    ("linect", "ctbc", "LINE Pay 信用卡", 2.8, "LINE Pay 一般 2.8%"),
    ("momoca", "tfb", "momo 聯名卡", 5.0, "momo 網購 5%（有上限）"),
]

MERCHANTS = [
    # slug, name, category, is_online, aliases, locations[(name, lat, lng)]
    ("pxmart", "全聯福利中心", "超市", False, "全聯,pxmart",
     [("南京建國店", 25.0522, 121.5470), ("信義莊敬店", 25.0337, 121.5605)]),
    ("seven", "7-ELEVEN", "超商", False, "7-11,統一超商", [("市府門市", 25.0406, 121.5645)]),
    ("family", "全家便利商店", "超商", False, "全家,familymart", [("統領店", 25.0443, 121.5438)]),
    ("carr", "家樂福", "量販", False, "carrefour", [("桂林店", 25.0330, 121.5060)]),
    ("momo", "momo 購物網", "網購", True, "momo", []),
    ("pchome", "PChome 24h", "網購", True, "pchome", []),
    ("fpanda", "foodpanda", "外送", True, "熊貓", []),
    ("ueats", "Uber Eats", "外送", True, "uber eats", []),
    ("gas", "全國加油站", "加油", False, "加油站", [("民權站", 25.0610, 121.5210)]),
    ("vie", "威秀影城", "娛樂", False, "威秀,電影", [("信義威秀", 25.0341, 121.5655)]),
    ("waca", "瓦城泰國料理", "餐廳", False, "瓦城", [("統一時代店", 25.0449, 121.5646)]),
]

# card_slug, merchant_slug, rate, cap, login, pay, end, note
OFFERS = [
    ("ubear", "pxmart", 3.8, 300, True, "any", "2026-08-31", "限指定門市"),
    ("cube", "pxmart", 5.0, 200, True, "any", "2026-08-20", "需於國泰 App 登錄"),
    ("linect", "pxmart", 2.8, 0, False, "line_pay", "2026-09-30", ""),
    ("pi", "seven", 4.5, 200, False, "pi_wallet", "2026-08-31", ""),
    ("gogo", "seven", 3.8, 300, True, "tap", "2026-08-31", "限定行動支付"),
    ("gogo", "family", 3.8, 300, True, "tap", "2026-08-31", "限定行動支付"),
    ("dabao", "family", 3.0, 0, False, "any", "2026-09-30", "數位帳戶加碼"),
    ("cube", "carr", 5.0, 300, True, "any", "2026-08-31", "需於國泰 App 登錄"),
    ("momoca", "momo", 5.0, 500, False, "any", "2026-09-30", "momo 會員限定"),
    ("ubear", "momo", 3.8, 300, False, "any", "2026-08-31", ""),
    ("ubear", "pchome", 3.8, 300, False, "any", "2026-08-31", ""),
    ("gogo", "pchome", 3.8, 300, True, "any", "2026-08-31", ""),
    ("gogo", "fpanda", 3.8, 300, True, "any", "2026-08-31", "外送平台加碼"),
    ("cube", "fpanda", 3.3, 0, False, "any", "2026-08-31", "美食外送方案"),
    ("linect", "ueats", 3.5, 0, False, "line_pay", "2026-09-30", ""),
    ("ubear", "ueats", 3.8, 300, False, "any", "2026-08-31", ""),
    ("jcard", "gas", 1.0, 0, False, "any", "2026-12-31", "基本回饋"),
    ("dabao", "gas", 3.0, 300, False, "any", "2026-09-30", ""),
    ("cube", "vie", 5.0, 300, True, "any", "2026-08-31", "影音娛樂方案"),
    ("jcard", "vie", 1.0, 0, False, "any", "2026-12-31", "基本回饋"),
    ("cube", "waca", 5.0, 300, True, "any", "2026-08-31", "精選餐廳方案"),
    ("linect", "waca", 3.5, 0, False, "line_pay", "2026-09-30", ""),
    ("pi", "waca", 4.5, 200, False, "pi_wallet", "2026-08-31", ""),
]


def expire_offers(session):
    """把已過期的 approved 優惠轉為 expired（啟動時與每日執行時呼叫）"""
    today = date.today()
    n = (session.query(Offer)
         .filter(Offer.status == "approved", Offer.ends_on < today)
         .update({"status": "expired"}))
    session.commit()
    return n


def ensure_seed(session):
    """建立示範資料（僅當資料庫為空時）"""
    if session.query(Bank).count() > 0:
        return False

    bank_ids = {}
    for code, name, short in BANKS:
        b = Bank(code=code, name=name, short_name=short)
        session.add(b)
        session.flush()
        bank_ids[code] = b.id

    card_ids = {}
    for slug, bank_code, name, base, note in CARDS:
        c = Card(bank_id=bank_ids[bank_code], slug=slug, name=name,
                 base_reward=base, base_note=note)
        session.add(c)
        session.flush()
        card_ids[slug] = c.id

    merch_ids = {}
    for slug, name, cat, online, aliases, locs in MERCHANTS:
        m = Merchant(slug=slug, name=name, category=cat, is_online=online, aliases=aliases)
        session.add(m)
        session.flush()
        merch_ids[slug] = m.id
        for lname, lat, lng in locs:
            session.add(MerchantLocation(merchant_id=m.id, name=lname, lat=lat, lng=lng))

    for card_slug, m_slug, rate, cap, login, pay, end, note in OFFERS:
        session.add(Offer(
            card_id=card_ids[card_slug], merchant_id=merch_ids[m_slug],
            reward_rate=rate, monthly_cap=cap, requires_login=login,
            pay_channel=pay, terms=note or None, ends_on=to_date(end),
            source_url="https://example.com/bank-official-page",  # 示範來源
            status="approved", verified_at=datetime.fromisoformat(DEMO_VERIFIED_AT),
        ))

    # 示範使用者與卡簿
    u = User(email="demo@cardperks.app")
    session.add(u)
    session.flush()
    for slug in ("gogo", "ubear", "linect", "jcard"):
        session.add(UserCard(user_id=u.id, card_id=card_ids[slug]))

    session.commit()
    return True


def load_approved(session, path=None):
    """匯入管線產出（pipeline/out/approved_offers.jsonl）的審核通過優惠"""
    path = path or os.path.join(os.path.dirname(__file__), "pipeline", "out", "approved_offers.jsonl")
    if not os.path.exists(path):
        return 0

    cards = {c.slug: c.id for c in session.query(Card).all()}
    merches = {m.slug: m.id for m in session.query(Merchant).all()}
    banks = {b.code: b.id for b in session.query(Bank).all()}

    def get_or_create_bank_card(bank_code, display_name=None):
        """全卡別優惠的建模：掛在 slug='bank:<code>' 的虛擬卡上（適用該行全部信用卡）"""
        slug = f"bank:{bank_code}"
        if slug not in cards:
            bank_id = banks.get(bank_code)
            if not bank_id:  # 銀行也不存在 → 自動建立
                b = Bank(code=bank_code, name=bank_code, short_name=bank_code[:3])
                session.add(b)
                session.flush()
                banks[b.code] = b.id
                bank_id = b.id
            c = Card(bank_id=bank_id, slug=slug,
                     name=display_name or f"{bank_code} 全卡別",
                     base_note="適用此銀行全部信用卡")
            session.add(c)
            session.flush()
            cards[slug] = c.id
        return cards[slug]
    # 冪等：已存在相同（卡+商家+截止日+來源）的優惠不重複匯入
    existing = {
        (o.card_id, o.merchant_id, o.ends_on, o.source_url)
        for o in session.query(Offer).all()
    }
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            slug = item.get("card_slug", "")
            if slug in ("*", "all", "") and item.get("bank"):
                # 全卡別活動 → 該行虛擬卡
                cid = get_or_create_bank_card(
                    item["bank"], f"{item.get('bank_name', item['bank'])}信用卡（全卡別）")
            else:
                cid = cards.get(slug)
            if not cid:
                # 未登錄的卡 → 依 bank 欄位自動建卡（銀行不存在也自動建）
                bank_id = banks.get(item.get("bank", ""))
                if not bank_id and item.get("bank"):
                    b = Bank(code=item["bank"],
                             name=item.get("bank_name") or item["bank"],
                             short_name=(item.get("bank_name") or item["bank"])[:3])
                    session.add(b)
                    session.flush()
                    banks[b.code] = b.id
                    bank_id = b.id
                if not bank_id:
                    continue
                c = Card(bank_id=bank_id, slug=item["card_slug"],
                         name=item.get("card_name") or item["card_slug"],
                         base_note=item.get("card_note"))
                session.add(c)
                session.flush()
                cards[c.slug] = c.id
                cid = c.id
            mid = merches.get(item.get("merchant_slug", ""))
            if not mid:  # 未知商家 → 自動建立（網購/外送為線上型，不進地圖）
                is_online = item.get("category") in ("網購", "外送")
                m = Merchant(slug=item["merchant_slug"], name=item.get("merchant_name") or item["merchant_slug"],
                             category=item.get("category") or "其他", is_online=is_online)
                session.add(m); session.flush()
                merches[m.slug] = m.id
                mid = m.id
            key = (cid, mid, to_date(item.get("ends_on")), item.get("source_url"))
            if key in existing:
                continue
            session.add(Offer(
                card_id=cid, merchant_id=mid,
                reward_rate=item["reward_rate"], reward_note=item.get("reward_note"),
                monthly_cap=item.get("monthly_cap", 0),
                requires_login=item.get("requires_login", False),
                pay_channel=item.get("pay_channel", "any"),
                terms=item.get("terms"), ends_on=to_date(item.get("ends_on")),
                source_url=item.get("source_url"),
                status="approved", verified_at=datetime.utcnow(),
            ))
            count += 1
    session.commit()
    return count
