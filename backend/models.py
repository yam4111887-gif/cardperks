"""卡優惠 CardPerks — 資料模型（對應 ../schema.sql 的 MVP 子集，SQLite 可跑）"""
import os
from datetime import datetime, date

from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Numeric, Boolean,
    Date, DateTime, ForeignKey, Text, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

DB_PATH = "cardperks.db"  # 相對 backend/ 目錄


class Bank(Base):
    __tablename__ = "banks"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)   # 'taishin'
    name = Column(String, nullable=False)                # '台新銀行'
    short_name = Column(String, nullable=False)          # '台新'
    official_site = Column(String)


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    slug = Column(String, unique=True, nullable=False)   # 'gogo'（對應原型 CARDS[].id）
    name = Column(String, nullable=False)
    base_reward = Column(Numeric(4, 2))
    base_note = Column(String)
    source_url = Column(String)
    is_active = Column(Boolean, default=True)
    bank = relationship("Bank")


class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)   # 'pxmart'
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    is_online = Column(Boolean, default=False)
    aliases = Column(String, default="")                 # 逗號分隔別名


class MerchantLocation(Base):
    __tablename__ = "merchant_locations"
    id = Column(Integer, primary_key=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    name = Column(String)
    lat = Column(Numeric(10, 7), nullable=False)
    lng = Column(Numeric(10, 7), nullable=False)


class Offer(Base):
    __tablename__ = "offers"
    # SQLite 需要 INTEGER 主鍵才會自動編號；PostgreSQL 正式版見 ../schema.sql（bigserial）
    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    merchant_id = Column(Integer, ForeignKey("merchants.id"))
    reward_rate = Column(Numeric(5, 2), nullable=False)   # %；折扣/贈禮型為 0
    reward_note = Column(String)                          # 非回饋型顯示文字，如「62折」「最高$4,800」
    monthly_cap = Column(Numeric(10, 2), default=0)       # 0 = 無上限
    requires_login = Column(Boolean, default=False)
    pay_channel = Column(String, default="any")
    terms = Column(String)
    starts_on = Column(Date)
    ends_on = Column(Date, nullable=False)
    source_url = Column(String)
    status = Column(String, default="pending")           # pending/approved/rejected/expired
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    card = relationship("Card")
    merchant = relationship("Merchant")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True)
    password_hash = Column(String)   # salt$pbkdf2 hex；示範用戶為 NULL（不可登入）
    display_name = Column(String)


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    token = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserCard(Base):
    __tablename__ = "user_cards"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id"), primary_key=True)
    added_at = Column(DateTime, default=datetime.utcnow)


def get_engine(path=None):
    """有 DATABASE_URL（例如 Supabase/Postgres）就用它，否則本機 SQLite"""
    url = os.environ.get("DATABASE_URL")
    if url:
        # Supabase 給的是 postgres:// 前綴，SQLAlchemy 需要 postgresql+psycopg2://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return create_engine(url, echo=False)
    return create_engine(f"sqlite:///{path or DB_PATH}", echo=False)
