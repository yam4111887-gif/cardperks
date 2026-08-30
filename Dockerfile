# 卡優惠 CardPerks — 生產映像（API + 原型 + Playwright 爬蟲環境）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Playwright 系統依賴＋Chromium（爬蟲用）
RUN pip install --no-cache-dir playwright==1.49.* && \
    playwright install --with-deps chromium

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# app 根目錄 = cardperks/（app.py 的靜態服務與 legal/ 都以此為根）
COPY backend/ backend/
COPY legal/ legal/
COPY index.html schema.sql README.md ./

WORKDIR /app/backend
EXPOSE 8000
# Render/Fly 會用 PORT 環境變數覆寫
ENV PORT=8000
CMD python -c "import os,uvicorn,app; uvicorn.run(app.app, host='0.0.0.0', port=int(os.environ.get('PORT',8000)))"
