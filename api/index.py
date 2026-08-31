"""Vercel 進入點：把所有請求交給 FastAPI（含靜態原型與 /api/*）

Vercel 是 serverless：網站＋API 在這裡跑；
爬蟲管線（Playwright）不支援 serverless，在本機執行並寫入同一個資料庫（見 DEPLOY.md）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app import app  # noqa: E402,F401
