"""卡優惠 CardPerks — FastAPI 後端

啟動：
    cd backend
    pip install -r requirements.txt
    python app.py            # http://localhost:8000 （/ 直接服務原型 index.html）
"""
import hashlib
import os
import secrets
import subprocess
import sys
import threading
from datetime import date

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (Base, get_engine, Bank, Card, Merchant, MerchantLocation,
                    Offer, User, UserCard, AuthToken)
from seed import ensure_seed, load_approved, expire_offers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # cardperks/
engine = get_engine()
Base.metadata.create_all(engine)

# 輕量遷移：既有 SQLite 補新欄位（create_all 不會 ALTER 舊表）
from sqlalchemy import text  # noqa: E402
with engine.connect() as conn:
    cols = [r[1] for r in conn.execute(text("PRAGMA table_info(offers)"))]
    if "reward_note" not in cols:
        conn.execute(text("ALTER TABLE offers ADD COLUMN reward_note VARCHAR"))
    ucols = [r[1] for r in conn.execute(text("PRAGMA table_info(users)"))]
    for col in ("password_hash", "display_name"):
        if col not in ucols:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR"))
    conn.commit()

app = FastAPI(title="CardPerks API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

with Session(engine) as db:
    if ensure_seed(db):
        print("已建立示範資料")
    n = load_approved(db)
    if n:
        print(f"已匯入 {n} 筆審核通過優惠")
    x = expire_offers(db)
    if x:
        print(f"已將 {x} 筆過期優惠下架（status=expired）")

DEMO_USER_EMAIL = "demo@cardperks.app"


def offer_to_dict(o: Offer, card_d: dict, merch_d: dict | None) -> dict:
    days_left = (o.ends_on - date.today()).days
    return {
        "id": o.id,
        "card": card_d,
        "merchant": merch_d,
        "reward_rate": float(o.reward_rate),
        "reward_note": o.reward_note,
        "monthly_cap": float(o.monthly_cap or 0),
        "requires_login": bool(o.requires_login),
        "pay_channel": o.pay_channel,
        "terms": o.terms,
        "starts_on": o.starts_on.isoformat() if o.starts_on else None,
        "ends_on": o.ends_on.isoformat(),
        "days_left": days_left,
        "status": o.status,
        "source_url": o.source_url,
        "verified_at": o.verified_at.isoformat() if o.verified_at else None,
    }


def card_to_dict(c: Card) -> dict:
    return {
        "slug": c.slug, "name": c.name,
        "bank": {"code": c.bank.code, "name": c.bank.name, "short_name": c.bank.short_name},
        "base_reward": float(c.base_reward or 0), "base_note": c.base_note,
    }


# ---------- 基礎資料 ----------

@app.get("/api/cards")
def list_cards():
    with Session(engine) as db:
        return [card_to_dict(c) for c in db.query(Card).filter_by(is_active=True).all()]


@app.get("/api/merchants")
def list_merchants():
    with Session(engine) as db:
        locs = {}
        for l in db.query(MerchantLocation).all():
            locs.setdefault(l.merchant_id, []).append(
                {"name": l.name, "lat": float(l.lat), "lng": float(l.lng)})
        return [{
            "slug": m.slug, "name": m.name, "category": m.category,
            "is_online": m.is_online, "aliases": (m.aliases or "").split(","),
            "locations": locs.get(m.id, []),
        } for m in db.query(Merchant).all()]


@app.get("/api/offers")
def list_offers(
    merchant: str | None = Query(None, description="商家 slug，如 pxmart"),
    cards: str | None = Query(None, description="卡片 slug 逗號分隔，如 gogo,ubear（過濾『我的卡』）"),
    category: str | None = None,
):
    q = select(Offer).where(Offer.status == "approved")
    with Session(engine) as db:
        if merchant:
            q = q.where(Offer.merchant_id.in_(
                select(Merchant.id).where(Merchant.slug == merchant)))
        if category:
            q = q.where(Offer.merchant_id.in_(
                select(Merchant.id).where(Merchant.category == category)))
        if cards:
            slugs = [s.strip() for s in cards.split(",") if s.strip()]
            my_cards = db.query(Card).filter(Card.slug.in_(slugs)).all()
            # 「我的卡」自動涵蓋該行「全卡別」優惠（虛擬卡 bank:<code>）
            slugs += [f"bank:{c.bank.code}" for c in my_cards]
            q = q.where(Offer.card_id.in_(select(Card.id).where(Card.slug.in_(slugs))))
        rows = db.execute(q).scalars().all()
        card_map = {c.id: card_to_dict(c) for c in db.query(Card).all()}
        merch_map = {m.id: m for m in db.query(Merchant).all()}
        out = []
        for o in rows:
            md = None
            if o.merchant_id and o.merchant_id in merch_map:
                m = merch_map[o.merchant_id]
                md = {"slug": m.slug, "name": m.name, "category": m.category}
            out.append(offer_to_dict(o, card_map[o.card_id], md))
        out.sort(key=lambda x: (-x["days_left"], -x["reward_rate"]))
        return {"count": len(out), "items": out, "disclaimer": "資料僅供參考，實際以各發卡銀行官方公告為準"}


@app.get("/api/search")
def search(q: str = Query(..., min_length=1, description="商家名稱或別名關鍵字")):
    """模糊搜尋商家，回傳商家列表與各商家有效優惠數"""
    kw = f"%{q.strip()}%"
    with Session(engine) as db:
        rows = db.query(Merchant).filter(
            (Merchant.name.like(kw)) | (Merchant.aliases.like(kw))
        ).all()
        result = []
        for m in rows:
            cnt = db.query(Offer).filter_by(merchant_id=m.id, status="approved").count()
            result.append({"slug": m.slug, "name": m.name, "category": m.category,
                           "is_online": m.is_online, "active_offers": cnt})
        return {"query": q, "merchants": result}


# ---------- 帳號系統（email 註冊/登入＋token；正式版可再加 LINE Login） ----------

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex(),
        digest)


def _current_user(db: Session, authorization: str | None):
    """Bearer token → User；無 token 回 None（呼叫端自行決定是否退回示範用戶）"""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        at = db.query(AuthToken).filter_by(token=token).first()
        if at:
            return db.query(User).get(at.user_id)
    return None


class AuthIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
def register(body: AuthIn):
    email = body.email.strip().lower()
    if "@" not in email or len(body.password) < 6:
        raise HTTPException(400, "email 格式錯誤或密碼至少 6 碼")
    with Session(engine) as db:
        if db.query(User).filter_by(email=email).first():
            raise HTTPException(409, "此 email 已註冊")
        u = User(email=email, password_hash=_hash_password(body.password))
        db.add(u)
        db.flush()
        token = secrets.token_urlsafe(32)
        db.add(AuthToken(token=token, user_id=u.id))
        db.commit()
        return {"ok": True, "token": token, "email": email}


@app.post("/api/auth/login")
def login(body: AuthIn):
    email = body.email.strip().lower()
    with Session(engine) as db:
        u = db.query(User).filter_by(email=email).first()
        if not u or not u.password_hash or not _verify_password(body.password, u.password_hash):
            raise HTTPException(401, "email 或密碼不正確")
        token = secrets.token_urlsafe(32)
        db.add(AuthToken(token=token, user_id=u.id))
        db.commit()
        return {"ok": True, "token": token, "email": email}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(None)):
    with Session(engine) as db:
        u = _current_user(db, authorization)
        if not u:
            return {"ok": True}
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            db.query(AuthToken).filter_by(token=token).delete()
            db.commit()
    return {"ok": True}


@app.get("/api/me")
def me(authorization: str | None = Header(None)):
    with Session(engine) as db:
        u = _current_user(db, authorization)
        if not u:
            return {"logged_in": False}
        rows = db.execute(
            select(Card).join(UserCard, UserCard.card_id == Card.id).where(UserCard.user_id == u.id)
        ).scalars().all()
        return {"logged_in": True, "email": u.email,
                "cards": [card_to_dict(c) for c in rows]}


# ---------- 卡簿（登入者用 Bearer token；未登入退回示範用戶，相容原型本地模式） ----------

def _user_for_cards(db: Session, authorization: str | None) -> User:
    u = _current_user(db, authorization)
    if u:
        return u
    u = db.query(User).filter_by(email=DEMO_USER_EMAIL).first()
    if not u:
        u = User(email=DEMO_USER_EMAIL)
        db.add(u)
        db.commit()
    return u


@app.get("/api/me/cardwallet")
def my_cards(authorization: str | None = Header(None)):
    with Session(engine) as db:
        u = _user_for_cards(db, authorization)
        rows = db.execute(
            select(Card).join(UserCard, UserCard.card_id == Card.id).where(UserCard.user_id == u.id)
        ).scalars().all()
        return {"cards": [card_to_dict(c) for c in rows]}


class CardIn(BaseModel):
    card_slug: str


@app.post("/api/me/cards")
def add_my_card(body: CardIn, authorization: str | None = Header(None)):
    with Session(engine) as db:
        u = _user_for_cards(db, authorization)
        c = db.query(Card).filter_by(slug=body.card_slug).first()
        if not c:
            raise HTTPException(404, "card not found")
        exists = db.query(UserCard).filter_by(user_id=u.id, card_id=c.id).first()
        if not exists:
            db.add(UserCard(user_id=u.id, card_id=c.id))
            db.commit()
        return {"ok": True, "card": card_to_dict(c)}


@app.delete("/api/me/cards/{card_slug}")
def remove_my_card(card_slug: str, authorization: str | None = Header(None)):
    with Session(engine) as db:
        u = _user_for_cards(db, authorization)
        c = db.query(Card).filter_by(slug=card_slug).first()
        if not c:
            raise HTTPException(404, "card not found")
        db.query(UserCard).filter_by(user_id=u.id, card_id=c.id).delete()
        db.commit()
        return {"ok": True}


# ---------- 資料覆蓋透明度 ----------
@app.get("/api/coverage")
def coverage():
    """資料涵蓋範圍與更新狀態（透明度面板用）"""
    with Session(engine) as db:
        offers = db.query(Offer).filter_by(status="approved").all()
        card_bank = {c.id: (c.bank.code, c.bank.name) for c in db.query(Card).all()}
        banks_stat = {}
        real = 0
        last_verified = None
        for o in offers:
            code, name = card_bank.get(o.card_id, ("?", "未知"))
            st = banks_stat.setdefault(code, {"code": code, "name": name, "offers": 0})
            st["offers"] += 1
            if o.source_url and "example.com" not in o.source_url:
                real += 1
            if o.verified_at and (last_verified is None or o.verified_at > last_verified):
                last_verified = o.verified_at
        return {
            "total_offers": len(offers),
            "official_sourced_offers": real,
            "banks": sorted(banks_stat.values(), key=lambda b: -b["offers"]),
            "last_verified_at": last_verified.isoformat() if last_verified else None,
            "update_frequency": "每日自動爬取，人工審核後上架",
            "methodology": "資料整理自各發卡銀行官方網站公開頁面，每筆優惠保留原始來源連結與查核時間供使用者驗證；發現缺漏或錯誤可透過「回報錯誤」通知我們修正。",
        }


# ---------- 排程觸發（供 Render Free + cron-job.org 等免費排程服務呼叫） ----------
TASK_STATE = {"running": False, "last": None, "started_at": None}


@app.get("/api/tasks/daily")
def trigger_daily(secret: str = "", request: Request = None):
    want = os.environ.get("CRON_SECRET", "")
    client_host = request.client.host if request and request.client else ""
    if want:
        if secret != want:
            raise HTTPException(403, "secret 不正確")
    elif client_host not in ("127.0.0.1", "::1", "testclient"):
        # 未設密鑰時僅允許本機（部署時請設定 CRON_SECRET）
        raise HTTPException(403, "未設定 CRON_SECRET，僅限本機觸發")

    if TASK_STATE["running"]:
        return {"ok": True, "status": "already_running"}

    def _run():
        TASK_STATE["running"] = True
        try:
            r = subprocess.run(
                [sys.executable, os.path.join("pipeline", "daily.py")],
                capture_output=True, text=True, encoding="utf-8",
                cwd=os.path.dirname(os.path.abspath(__file__)), timeout=1800,
            )
            TASK_STATE["last"] = {
                "code": r.returncode,
                "tail": ((r.stdout or "") + (r.stderr or ""))[-600:],
            }
        except Exception as e:
            TASK_STATE["last"] = {"code": -1, "tail": f"{type(e).__name__}: {e}"}
        finally:
            TASK_STATE["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    TASK_STATE["started_at"] = date.today().isoformat()
    return {"ok": True, "status": "started", "note": "背景執行中，用 /api/tasks/status 查看結果"}


@app.get("/api/tasks/status")
def tasks_status():
    return {"running": TASK_STATE["running"], "last": TASK_STATE["last"],
            "started_at": TASK_STATE["started_at"]}


# ---------- 法律文件 ----------

LEGAL_DOCS = {"terms": "TERMS.md", "privacy": "PRIVACY.md", "audit": "LEGAL-AUDIT.md"}


@app.get("/api/legal/{doc}")
def legal(doc: str):
    fname = LEGAL_DOCS.get(doc)
    if not fname:
        raise HTTPException(404, "unknown doc; use terms|privacy|audit")
    path = os.path.join(ROOT, "legal", fname)
    with open(path, encoding="utf-8") as f:
        return {"doc": doc, "updated_at": "2026-08-16", "content": f.read()}


# ---------- 靜態原型（/ 即 index.html） ----------
app.mount("/", StaticFiles(directory=ROOT, html=True), name="prototype")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
