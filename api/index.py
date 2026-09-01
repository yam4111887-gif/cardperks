"""Vercel 進入點（Python serverless）。

⚠️ 2026-09 實測：Vercel Hobby 的 Python runtime 為社群維護，函數調用固定失敗
（FUNCTION_INVOCATION_FAILED，與 vercel.json 寫法、requirements 位置無關）。
此檔保留給未來 Vercel 修復時使用；目前正式部署走 Docker（HF Spaces / Render / VPS）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app import app  # noqa: E402,F401
