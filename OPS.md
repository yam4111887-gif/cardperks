# 營運手冊（OPS）

> 給負責人的一頁說明：資料怎麼固定更新、法律上要注意什麼、你需要做哪些事。

## 一、怎麼固定更新（三種方式，擇一）

### 方式 1：Windows 工作排程器（目前本機開發用）
1. 開始 → 「工作排程器」→ 建立基本工作
2. 觸發：每天 08:00
3. 動作：啟動程式 →
   - 程式：`python`
   - 引數：`pipeline/daily.py`
   - 開始位置：`C:\Users\oxo\.zcode\workspace\default\cardperks\backend`
4. 完成。之後每天看 `backend/pipeline/out/diff_report.md` 有沒有「新活動」

### 方式 2：部署平台的 Cron（推薦上線後）
見 `DEPLOY.md`——Render Cron Job / fly cron / VPS crontab，一行指令：
```
python pipeline/daily.py
```

### 方式 3：全自動（含 LLM 解析）
排程跑 `daily.py` → `llm_parse.py` → **人工審核 `review.py list` 不可省** → 重啟 app.py。
**設計原則：LLM 只產草稿，人工審核才上架**——這是資料正確性（也是法律上「盡合理注意」）的關鍵防線。

LLM 選擇（二選一，端點相容）：
- **GLM（建議，免費）**：到 open.bigmodel.cn 申請 API key → 環境變數 `LLM_PROVIDER=glm`、`LLM_API_KEY=...`（預設模型 glm-4-flash 免費）。**注意：GLM Coding Plan 是綁開發工具的訂閱額度，不能拿來當 API key**，要另外申請平台的 API key。
- OpenAI：`OPENAI_API_KEY=...`（gpt-4o-mini，月費約 US$5–20）

隱私面向：本管線只解析銀行公開頁面（無任何使用者個資），用哪家 LLM 都沒有跨境個資問題；**帳單健檢**若未來真的接 LLM，才需要依隱私政策重新評估供應商。

### 每天要花的人力（現況估）
- 看 diff_report：5 分鐘
- 審核新活動：每筆 1–2 分鐘（對照來源頁確認數字）
- 有錯誤回報時：即時更正（下架或修正＋更新查核時間）

## 二、固定更新的法律問題（簡答）

**定時爬蟲本身合法嗎？** 我們的爬法在台灣實務上屬低風險：只抓公開頁面、遵守 robots.txt、每站 3 秒限速、自識別 UA、只取事實數據（回饋率/期間）並改寫條款不逐字複製。定時執行不會改變法律性質——風險本來就不在「爬幾次」而在「怎麼爬」。維持現有四原則即可。

**三個「如果發生」的劇本：**
1. **銀行寄存取禁止函** → 立即把該銀行從 `crawler.py` 的 `BANK_SOURCES` 移除，該來源改人工編輯；回覆說明定位（資訊整理工具）與資料來源標示方式
2. **使用者因錯誤資料受損抱怨** → 用優惠詳情裡的來源連結與查核時間對話；正確作法是立即下架或修正，不與使用者爭執條款
3. **銀行頁面改版導致爬不到** → daily 的 diff_report 會顯示「疑似結束」異常增多，人工檢查來源頁並更新 `BANK_SOURCES` 網址

**持續義務（來自 legal/LEGAL-AUDIT.md）：**
- 每筆優惠保留來源 URL＋查核日期（已內建）
- 收到錯誤回報要有更正動作（回報按鈕已內建，你要建立接收管道，見下）
- 資料來源擴充時，先 robots.txt 檢查（爬蟲已自動做）

## 三、你需要做什麼（負責人待辦）

### 立刻（本週）
- [ ] 決定部署方案並照 `DEPLOY.md` 上線（驗證期可 $0：Render Free＋Supabase＋cron-job.org；認真推廣 → 台灣 VPS 約 NT$300/月，解鎖台新爬蟲）
- [ ] 註冊網域（例如 cardperks.tw / cardperks.app）
- [ ] 建立錯誤回報接收管道：一個信箱（feedback@你的網域）或 Google Form／Line 官方帳號——App 內「回報錯誤」按鈕要指向它
- [ ] 到 open.bigmodel.cn 申請 GLM API key（免費模型 glm-4-flash 即可，Coding Plan 不能當 API key 用）

### 一個月內
- [ ] 委請台灣執業律師複核 `legal/TERMS.md`、`PRIVACY.md`（費用約 NT$30,000–80,000）
- [ ] 決定公司主體（有限公司設立約 NT$50,000 內；接廣告/分潤前建議完成）
- [ ] 把條款文件中的 `[佔位符]` 全部換成正式資訊
- [ ] 開始記錄「來源快照」（已自動存在 `backend/pipeline/out/snapshots/`，要備份不要清掉）

### 上線 App 商店前
- [ ] Apple Developer（US$99/年）＋ Google Play（US$25 一次性）
- [ ] App Store/Google Play 隱私標籤如實填寫（帳單健檢＝財務資訊，等級要選對）
- [ ] 建立帳號刪除自助功能（法遵報告檢查清單）
- [ ] 評估資安責任險（個資外洩險）

### 長期
- [ ] 與銀行談官方資料合作（有流量後）——終極解法
- [ ] 資料庫從 SQLite 遷移 PostgreSQL（schema.sql 已備好）
