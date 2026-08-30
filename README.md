# 卡優惠 CardPerks — 互動原型 + 資料庫 Schema

信用卡優惠聚合 App 的第一版可點擊原型（單一 HTML 檔，免安裝、免建置），加上對應的 PostgreSQL schema。

## 快速開始

直接用瀏覽器打開 `index.html` 即可（地圖分頁需網路連線載入 Leaflet 與 OpenStreetMap 圖資）。

或本機起個伺服器：

```bash
cd cardperks
python -m http.server 8080
# 開啟 http://localhost:8080
```

建議用瀏覽器開發者工具切到手機尺寸（寬度 ≤ 430px）體驗最佳，桌機會自動呈現手機框樣式。

## 示範操作腳本（照著走一遍最能感受產品）

1. **卡簿**：首頁是你已登錄的 4 張卡（免費版上限 5 張）。點卡片看個別優惠；點「＋ 新增卡片」加第 5 張——再想加第 6 張就會觸發**付費牆**。
2. **全域過濾**：頂部「只看我的卡 / 顯示全部卡」切換——這個開關同時影響搜尋、地圖、優惠三個分頁。
3. **搜尋**：輸入「全聯」或點分類 chip，輸入消費金額（預設 $1,000），結果會按**實際回饋金額**排序，標示「綁定支付 / 需登錄 / 月上限 / 達上限」，你沒有的卡會出現「查看辦卡」（示意 affiliate）。
4. **地圖**：台北市實體商家標籤顯示優惠筆數（隨全域過濾變動），點標籤看該店可用卡別。網購／外送商家不進地圖。
5. **優惠**：依到期日排序的優惠牆，切過濾看「全部卡」會冒出你沒有的卡。
6. **提醒 🔔**：右上角鈴鐺——免費版看到的是模糊鎖定內容＋升級按鈕（Pro 功能）。
7. **Pro 分頁**：比較表＋「模擬上傳帳單」——免費版先跳付費牆；訂閱後（示範可直接開通）顯示帳單健檢結果：實拿 $393 vs 可拿 $1,240，**少賺 $847**——這是核心付費說服邏輯。

## 檔案說明

| 檔案 | 內容 |
|---|---|
| `index.html` | 單檔互動原型（HTML + CSS + 原生 JS，資料內嵌；含法律頁面與個資同意流程） |
| `schema.sql` | PostgreSQL schema（正式版）：含資料管線欄位（status: pending→approved、offer_revisions 審計） |
| `backend/` | FastAPI + SQLite 後端（`pip install -r requirements.txt && python app.py` → http://localhost:8000，`/` 直接服務原型） |
| `backend/pipeline/` | 資料管線：`crawler.py`（守 robots.txt/限速）→ `llm_parse.py`（LLM 結構化，產 pending）→ `review.py`（人工審核 approved → 重啟自動匯入 DB） |
| `legal/LEGAL-AUDIT.md` | 法遵審查報告（嚴格標準）：風險等級、逐法規分析、上線前檢查清單 |
| `legal/TERMS.md` | 使用者服務條款草稿（含免責、affiliate 揭露、自動續約） |
| `legal/PRIVACY.md` | 隱私權政策草稿（含帳單健檢特別規則、跨境 LLM 揭露） |

## API 端點（backend）

```
GET  /api/cards                     # 全部卡片
GET  /api/merchants                 # 全部商家
GET  /api/offers?merchant=pxmart&cards=gogo,ubear   # 優惠查詢（可過濾我的卡）
GET  /api/search?q=pxmart           # 商家模糊搜尋（名稱/別名）
GET/POST/DELETE /api/me/cards       # 卡簿（示範單一使用者）
GET  /api/legal/terms|privacy|audit # 法律文件
```

## 資料管線（法遵三原則：robots.txt / 限速 / 自識別 UA）

```bash
cd backend
python pipeline/crawler.py --dry-run   # 先檢查 robots.txt
python pipeline/crawler.py             # Playwright 抓取（JS 渲染頁）→ out/crawled_items.jsonl
python pipeline/llm_parse.py           # 需設 OPENAI_API_KEY → out/pending_offers.jsonl
python pipeline/review.py list         # 人工審核
python pipeline/review.py approve 1    # 核可 → approved_offers.jsonl（重啟 app.py 自動入庫）
python pipeline/daily.py               # 每日執行器：爬取＋差異報告 → out/diff_report.md
python pipeline/geocode.py             # 商家地理編碼（Nominatim）→ 進地圖
python e2e_test.py                     # 全功能 E2E 自動化測試（34 項）
```

## ⚠️ 法律重要聲明

`legal/` 內文件為**工程草稿，非法律意見**；正式上線前必須委請台灣執業律師複核。優惠資料一律標示來源與「以發卡銀行官方公告為準」，LLM 產出未經人工審核（status=pending）不得上架。

## ⚠️ 資料免責聲明

原型內所有銀行、卡片、優惠、回饋率、門市座標皆為**示範資料**，非即時資訊，實際內容請以各銀行官方公告為準。

## 設計決策摘要（對應競品拆解結論）

- **地圖模式**：全台競品（iCard.AI / Card4u / Money101）皆無，列為核心功能
- **手動加卡、不連銀行**：採 CardPointers 模式，化解隱私疑慮（台灣也無開放銀行 API 可用）
- **「用 X 卡綁 Y 支付」推薦**：所有台灣競品的共同盲點，offer 一律帶 pay_channel
- **訂閱主打帳單健檢**：「少賺 $847」> 訂閱費的說服邏輯（CardPointers 驗證過）
- **雙引擎變現**：訂閱（用戶付費）＋ 辦卡 affiliate（Money101 驗證過的市場，schema 已建 affiliate_clicks 表）

## 下一步建議順序

1. 資料管線 MVP：爬蟲抓 3–5 家銀行優惠頁 → LLM 解析成 offers（status=pending）→ 簡易審核後台上架
2. 把原型的內嵌資料換成 API（FastAPI + 上述 schema）
3. React Native / Flutter 出真 App 殼，推播（到期／額度／登錄提醒）是 App 相對網頁競品的殺手級差異
