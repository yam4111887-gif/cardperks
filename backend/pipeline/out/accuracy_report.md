# 資料準確度稽核報告
時間：2026-10-23T16:04:09.158290+00:00
抽樣：6 筆（母體 23 筆附官方來源之上架優惠）

結果：✅ 一致 3 筆 · ⚠️ 待人工 2 筆 · ❌ 疑似失效 1 筆

## 明細
- ⚠️ **玉山銀行信用卡（全卡別） @ 百貨週年慶（指定百貨）**｜0.0%（專屬回饋）｜至 2026-12-31｜找到 note:專屬回饋；未見 end:2026-12-31（格式改變？）
  - 來源：https://www.esunbank.com.tw/bank/personal/credit-card/discount/shops
- ✅ **LINE Pay 信用卡 @ Uber Eats**｜5.0%｜至 2026-12-31｜rate:5.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ⚠️ **玉山 Unicard @ 福容大飯店**｜20.0%｜至 2026-12-31｜找到 rate:20.0%；未見 end:2026-12-31（格式改變？）
  - 來源：https://www.esunbank.com/zh-tw/personal/credit-card/discount/shopInfo?sno=8095
- ✅ **LINE Pay 信用卡 @ 蝦皮購物**｜5.0%｜至 2026-12-31｜rate:5.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ✅ **LINE Pay 信用卡 @ 藏壽司**｜10.0%｜至 2026-12-31｜rate:10.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ❌ **玉山銀行信用卡（全卡別） @ 雙十購物季（指定購物平台）**｜0.0%（最高5,700）｜至 2026-10-31｜頁面無內容（可能已下架或改版）
  - 來源：https://event.esunbank.com.tw/credit/1100225e/index.html

## 處理原則
- ❌ 疑似失效 → 人工開來源頁確認，若活動已結束/改版：下架（review/DB 改 status）或更新資料
- ⚠️ 待人工 → 多為日期格式差異或頁面改版，人工確認後更新查核時間
- 建議排程：每天 daily.py 後跑一次，每週至少全量抽查一輪