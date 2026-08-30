# 部署指南

> 目標：把「API + 原型 + 每日爬蟲」搬到雲上，讓朋友用手機實測。
> 2026-08 現況：本地全功能可用（`cd backend && python app.py` → http://localhost:8000）。

## 費用比較（2026-08，依「能用」程度排序）

| 方案 | 月費 | 適合 | 限制 |
|---|---|---|---|
| **Render Free + Supabase + cron-job.org** | **$0** | 給朋友試用、驗證需求 | 15 分鐘無流量休眠（喚醒慢）；**512MB RAM 跑 Chromium 爬蟲容易 OOM**（爬蟲建議仍在本機跑）；無持久磁碟（所以配 Supabase） |
| **Fly.io 512MB** | ~US$3 | 小流量正式站 | 爬蟲記憶體緊張；需信用卡 |
| **Render Starter** | US$7 | 不休眠＋內建 Cron＋爬蟲 OK | 磁碟另計費（US$1/GB） |
| **台灣 VPS**（遠振/GCP 台灣 e2-micro） | NT$300 上下 | **解鎖台新爬蟲**（台灣 IP）、完全掌控 | 要自己管主機 |

**建議**：驗證期用 $0 方案（下面有完整設定）；開始認真推廣 → 台灣 VPS（順便解鎖台新、爬蟲記憶體充裕）。

## 選項 0：$0 方案（Render Free + Supabase + cron-job.org）

1. **Supabase**（免費 Postgres，500MB）：建專案 → Settings → Database → 複製連線字串（URI）
2. **Render**：New → Web Service（Docker）→ 環境變數：
   - `DATABASE_URL`＝Supabayse 連線字串（程式會自動換成 SQLAlchemy 格式）
   - `CRON_SECRET`＝自訂一組密語（給排程觸發用）
3. **cron-job.org**（免費）：每天 08:00 GET
   `https://你的網址/api/tasks/daily?secret=你的密語`
   （此端點會背景執行 daily.py：過期下架→爬蟲→差異報告；用 `/api/tasks/status` 查結果）
   ⚠ Render Free 的 512MB 對 Chromium 爬蟲偏緊，若 OOM：爬蟲留本機排程跑、雲端只當 API。
4. LLM 解析（選配，GLM 免費模型）：
   - 到 [open.bigmodel.cn](https://open.bigmodel.cn) 申請 **API key**（注意：GLM Coding Plan 是綁開發工具的訂閱，**不能**當 API key 用）
   - 環境變數：`LLM_PROVIDER=glm`、`LLM_API_KEY=你的key`（模型預設 glm-4-flash，免費）

## 選項 A：Render（最簡單，推薦起手）

1. 專案推上 GitHub（repo 根目錄＝`cardperks/` 的內容層級，即 Dockerfile 在根目錄）
2. Render → New → **Web Service** → 連接 repo
3. 設定：
   - Environment：**Docker**（自動用 Dockerfile）
   - Instance：Free / Starter 皆可（Free 會休眠，爬蟲排程需要 Starter）
   - 環境變數（選填）：`OPENAI_API_KEY`（LLM 自動解析用）
4. 部署完成即有 HTTPS 網址（例如 `cardperks.onrender.com`）
5. 每日更新：Render → **Cron Job**（同 repo、Docker、指令見下）

## 選項 B：Fly.io

```bash
fly launch --dockerfile Dockerfile --name cardperks --region sin
fly secrets set OPENAI_API_KEY=sk-...   # 選填
fly deploy
```

## 選項 C：台灣 VPS（GCP 台灣/遠振/竹智等，爬蟲連台新不再被擋）

```bash
scp -r ./ ubuntu@<主機>:/opt/cardperks
cd /opt/cardperks
docker build -t cardperks .
docker run -d -p 80:8000 --restart always \
  -v /opt/cardperks-data:/app/backend/cardperks.db \
  --name cardperks cardperks
# 每日 08:00 爬蟲（容器內執行）
echo '0 8 * * * docker exec cardperks python pipeline/daily.py >> /var/log/cardperks.log 2>&1' | crontab -
```

注意：SQLite 檔要掛 volume（如上）才會保留資料；正式規模化時改用 schema.sql 建 PostgreSQL。

## Cron 指令（各平台通用）

```
python pipeline/daily.py     # 過期下架 → 爬取 → 差異報告（out/diff_report.md）
```

需要 LLM 自動解析才加：
```
python pipeline/llm_parse.py  # 需環境變數 OPENAI_API_KEY
```

## 上線檢查

- [ ] HTTPS 正常（平台自動提供）
- [ ] `/api/coverage` 回傳統計
- [ ] 首頁顯示「即時資料」徽章
- [ ] Cron 隔天有 `diff_report.md` 產出
- [ ] 資料庫掛了持久 volume
- [ ] `legal/` 三份文件換上正式版（律師複核後）
