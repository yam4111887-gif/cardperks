# 資料準確度稽核報告
時間：2026-09-23T15:42:41.812564+00:00
抽樣：6 筆（母體 21 筆附官方來源之上架優惠）

結果：✅ 一致 5 筆 · ⚠️ 待人工 1 筆 · ❌ 疑似失效 0 筆

## 明細
- ✅ **MaiCoin 聯名卡 @ 全部通路**｜4.5%｜至 2027-04-30｜rate:4.5%、end:2027-04-30
  - 來源：https://activity.ubot.com.tw/2026MaiCoinCard/index.htm
- ✅ **LINE Pay 信用卡 @ 星巴克**｜5.0%｜至 2026-12-31｜rate:5.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ✅ **玉山 Unicard @ 全台 TWQR／台灣Pay 商店**｜20.0%｜至 2026-09-30｜rate:20.0%、end:2026-09-30
  - 來源：https://www.esunbank.com/zh-tw/personal/credit-card/discount/shopInfo?sno=8095
- ✅ **LINE Pay 信用卡 @ 藏壽司**｜10.0%｜至 2026-12-31｜rate:10.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ✅ **LINE Pay 信用卡 @ 摩斯漢堡**｜10.0%｜至 2026-12-31｜rate:10.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ⚠️ **J 卡 @ J卡精選通路（餐飲/加油站/外送/購票）**｜0.0%（最高$900）｜至 2026-09-30｜找到 end:2026-09-30；未見 note:最高$900（格式改變？）
  - 來源：https://cardpromote.taipeifubon.com.tw/promotion/Type?category=A

## 處理原則
- ❌ 疑似失效 → 人工開來源頁確認，若活動已結束/改版：下架（review/DB 改 status）或更新資料
- ⚠️ 待人工 → 多為日期格式差異或頁面改版，人工確認後更新查核時間
- 建議排程：每天 daily.py 後跑一次，每週至少全量抽查一輪