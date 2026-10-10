# 資料準確度稽核報告
時間：2026-10-10T05:22:27.292518+00:00
抽樣：6 筆（母體 17 筆附官方來源之上架優惠）

結果：✅ 一致 5 筆 · ⚠️ 待人工 1 筆 · ❌ 疑似失效 0 筆

## 明細
- ✅ **LINE Pay 信用卡 @ Uber Eats**｜5.0%｜至 2026-12-31｜rate:5.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ⚠️ **玉山 Unicard @ 福容大飯店**｜20.0%｜至 2026-12-31｜找到 rate:20.0%；未見 end:2026-12-31（格式改變？）
  - 來源：https://www.esunbank.com/zh-tw/personal/credit-card/discount/shopInfo?sno=8095
- ✅ **台北富邦信用卡（全卡別） @ 肯德基 KFC**｜0.0%（62折起）｜至 2026-11-30｜note:62折起、end:2026-11-30
  - 來源：https://cardpromote.taipeifubon.com.tw/promotion/Type?category=A
- ✅ **LINE Pay 信用卡 @ LOPIA**｜10.0%｜至 2026-12-31｜rate:10.0%、end:2026-12-31
  - 來源：https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html
- ✅ **MaiCoin 聯名卡 @ 全部通路**｜4.5%｜至 2027-04-30｜rate:4.5%、end:2027-04-30
  - 來源：https://activity.ubot.com.tw/2026MaiCoinCard/index.htm
- ✅ **台北富邦信用卡（全卡別） @ 必勝客 Pizza Hut**｜0.0%（38折起）｜至 2026-11-30｜note:38折起、end:2026-11-30
  - 來源：https://cardpromote.taipeifubon.com.tw/promotion/Type?category=A

## 處理原則
- ❌ 疑似失效 → 人工開來源頁確認，若活動已結束/改版：下架（review/DB 改 status）或更新資料
- ⚠️ 待人工 → 多為日期格式差異或頁面改版，人工確認後更新查核時間
- 建議排程：每天 daily.py 後跑一次，每週至少全量抽查一輪