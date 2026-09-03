# HF Spaces 專用 Dockerfile（差異：監聽 7860、非 root 使用者、不含 Playwright——每日爬蟲由 GitHub Actions 负责）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# HF Spaces 以 UID 1000 執行；建立對應使用者確保相容
RUN useradd -m -u 1000 user

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY legal/ legal/
COPY index.html schema.sql ./

RUN chown -R user:user /app
USER user

# HF Spaces 要求 0.0.0.0:7860（其他平台可用 PORT 環境變數覆寫）
ENV PORT=7860
WORKDIR /app/backend
EXPOSE 7860
CMD python -c "import os,uvicorn,app; uvicorn.run(app.app, host='0.0.0.0', port=int(os.environ.get('PORT',7860)))"
