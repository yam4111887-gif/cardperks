"""卡優惠 CardPerks — 全功能 E2E 自動化測試（Playwright / Chromium）

涵蓋：引導頁（完整流程＋略過）、卡簿（新增/移除/付費牆/持久化）、
搜尋（查詢/金額計算/全部卡切換）、地圖、優惠、Pro（訂閱/帳單健檢同意）、
提醒、法律頁面、即時資料載入。

用法：
    cd backend && python e2e_test.py        # 需後端已於 8000 埠運行
"""
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000/"
PASSED, FAILED = [], []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f"（{detail}）" if detail and not cond else ""))


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 400, "height": 850}, locale="zh-TW")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # ---------- 1. 首次造訪：引導頁 ----------
        page.goto(BASE, timeout=30000)
        page.wait_for_timeout(2000)
        check("首訪顯示引導頁", page.locator("#onboard.on").count() == 1)

        check("引導第1頁標題", "記下你的卡" in (page.locator(".ob-hero h2").text_content() or ""))
        page.click("text=下一步")
        page.wait_for_timeout(200)
        check("引導第2頁標題", "結帳前" in (page.locator(".ob-hero h2").text_content() or ""))
        page.click("text=下一步")
        page.wait_for_timeout(200)
        page.click("text=選擇我的卡")
        page.wait_for_timeout(300)
        check("引導選卡步出現卡片", page.locator(".pick").count() >= 8,
              f"pick={page.locator('.pick').count()}")

        # 未選卡時按鈕停用
        check("未選卡時開始鈕停用", page.locator("#obStart[disabled], .btn-w[disabled]").count() >= 1)

        # 選 3 張卡（每輪重繪後清單會變，固定點「當前第一個未選」）
        for _ in range(3):
            page.locator(".pick:not(.on)").first.click()
            page.wait_for_timeout(150)
        check("選卡後按鈕啟用並顯示數量", "3 張卡" in (page.locator(".btn-w").last.text_content() or ""))

        page.click("text=開始使用")
        page.wait_for_timeout(500)
        check("完成引導後關閉遮罩", page.locator("#onboard.on").count() == 0)
        stored = page.evaluate("localStorage.getItem('cp_myCards')")
        check("卡簿寫入 localStorage", stored is not None and len(eval(stored)) == 3, f"stored={stored}")
        check("卡簿顯示 3 張卡", page.locator("#view-cards .offerrow").count() == 3)

        # 引導完成旗標
        check("引導完成旗標", page.evaluate("localStorage.getItem('cp_onboarded')") == "1")

        # ---------- 2. 重載不再出現引導、卡簿持久 ----------
        page.reload()
        page.wait_for_timeout(1800)
        check("重載不出現引導", page.locator("#onboard.on").count() == 0)
        check("重載後卡簿保留", page.locator("#view-cards .offerrow").count() == 3)

        # ---------- 3. ？重看引導 ----------
        page.click("#helpBtn")
        page.wait_for_timeout(300)
        check("？可重看引導（直接到選卡步）", page.locator("#onboard.on").count() == 1
              and page.locator(".pick.on").count() == 3)
        page.click("text=略過")
        page.wait_for_timeout(200)

        # ---------- 4. 即時資料載入 ----------
        logo = page.locator(".logo small").text_content() or ""
        check("API 即時資料徽章", "即時資料" in logo, f"logo={logo}")

        # ---------- 5. 搜尋：我的卡有優惠的商家（Coupang，效期到 12/31）＋金額計算 ----------
        page.click('nav button[data-v="search"]')
        page.fill("input[type=text]", "Coupang")
        page.wait_for_timeout(500)
        heads = page.locator(".merchant-head").all_text_contents()
        check("搜尋 Coupang 命中", any("Coupang" in h or "酷澎" in h for h in heads), f"heads={heads}")

        rows = page.locator("#view-search .offerrow")
        r1_before = rows.first.text_content() or ""
        check("我的卡模式顯示 ✓ 你有", "你有" in r1_before)
        page.fill("input[type=number]", "2000")
        page.wait_for_timeout(400)
        r1_after = rows.first.text_content() or ""
        check("金額改變回饋估算更新", ("$100" in r1_after) or (r1_after != r1_before))

        # ---------- 6. 我的卡沒優惠的商家（星巴克）→ fallback 引導切換 ----------
        page.fill("input[type=text]", "星巴克")
        page.wait_for_timeout(500)
        check("無優惠時顯示切換引導", page.locator("text=切換看全部卡片").count() == 1)
        page.click("text=切換看全部卡片")
        page.wait_for_timeout(500)
        heads = page.locator(".merchant-head").all_text_contents()
        check("切換後命中星巴克（真資料）", any("星巴克" in h for h in heads), f"heads={heads}")
        check("全部卡模式出現辦卡鈕", page.locator("text=查看辦卡").count() >= 1)
        page.click('header .seg button[data-mode="mine"]')
        page.wait_for_timeout(300)

        # ---------- 7. 地圖（切全部卡——mine 模式優惠會隨效期波動） ----------
        page.click('header .seg button[data-mode="all"]')
        page.click('nav button[data-v="map"]')
        page.wait_for_timeout(2500)
        markers = page.locator(".leaflet-marker-icon").count()
        check("地圖標籤渲染", markers >= 5, f"markers={markers}")

        # ---------- 8. 優惠分頁排序與免責 ----------
        page.click('nav button[data-v="offers"]')
        page.wait_for_timeout(400)
        note = page.locator(".note").text_content() or ""
        check("優惠頁含來源與免責標示", "以官方公告為準" in note and "資料來源" in note)

        # 8a. 優惠詳情（來源佐證）
        page.locator("#view-offers .offerrow").first.click()
        page.wait_for_timeout(400)
        check("點優惠開啟詳情面板", page.locator("text=開啟原始資料來源").count() >= 1
              or page.locator(".sheet button:has-text('回報')").count() >= 1)
        has_src_or_demo = (page.locator("text=開啟原始資料來源").count() >= 1
                           or page.locator("text=示範資料").count() >= 1)
        check("詳情含來源佐證或示範聲明", has_src_or_demo)
        check("詳情含分享按鈕", page.locator(".sheet button:has-text('分享')").count() == 1)
        page.locator(".sheet button:has-text('關閉')").last.click()
        page.wait_for_timeout(300)

        # 8b. 資料涵蓋範圍面板
        page.click("text=資料涵蓋範圍與更新")
        page.wait_for_timeout(600)
        sheet_txt = page.locator(".sheet").text_content() or ""
        check("涵蓋範圍面板開啟", "資料涵蓋" in sheet_txt and "資料方法" in sheet_txt)
        check("涵蓋面板顯示銀行統計", "筆" in sheet_txt and ("家" in sheet_txt or "銀行" in sheet_txt))
        page.locator(".sheet button:has-text('關閉')").last.click()
        page.wait_for_timeout(300)

        # ---------- 9. 卡簿付費牆（第 6 張） ----------
        page.click('nav button[data-v="cards"]')
        page.wait_for_timeout(300)
        while page.locator("#view-cards .offerrow").count() < 5:
            page.click("text=＋ 新增卡片")
            page.wait_for_timeout(300)
            adds = page.locator(".sheet .listitem >> text=加入")
            if adds.count() == 0:
                break
            adds.first.click()
            page.wait_for_timeout(300)
        page.click("text=＋ 新增卡片")
        page.wait_for_timeout(300)
        adds = page.locator(".sheet .listitem >> text=加入")
        if adds.count():
            adds.first.click()
            page.wait_for_timeout(300)
        check("第 6 張卡觸發付費牆", page.locator("text=升級 Pro 解鎖").count() >= 1)

        # ---------- 10. 訂閱 Pro + 帳單健檢同意流程 ----------
        page.click("text=訂閱 Pro · NT$79/月（示範）")
        page.wait_for_timeout(500)
        check("訂閱後 PRO 徽章", page.locator("#proChip.on").count() == 1)
        check("Pro 後卡簿顯示無上限", "無上限" in (page.locator("#view-cards").text_content() or ""))

        page.click('nav button[data-v="pro"]')
        page.wait_for_timeout(300)
        page.click("text=模擬上傳帳單")
        page.wait_for_timeout(400)
        check("帳單健檢出現同意步驟", page.locator("text=上傳前同意").count() == 1)
        page.click("text=開始分析（模擬）")  # 未勾選 → 應被擋
        page.wait_for_timeout(300)
        check("未勾選同意被阻擋", page.locator("text=請先勾選同意才能繼續").count() == 1)
        page.check("#consentChk")
        page.click("text=開始分析（模擬）")
        page.wait_for_timeout(400)
        check("勾選後顯示健檢結果", page.locator("text=帳單健檢結果").count() == 1
              and page.locator("text=少賺").count() >= 1)
        page.click("text=了解")

        # ---------- 11. 提醒（Pro 已解鎖） ----------
        page.click("#bellBtn")
        page.wait_for_timeout(400)
        check("提醒面板開啟（Pro）", page.locator(".sheet h3").count() == 1
              and "提醒" in (page.locator(".sheet h3").text_content() or ""))
        page.click("text=關閉")

        # ---------- 12. 法律頁面 ----------
        page.click('nav button[data-v="cards"]')
        page.wait_for_timeout(300)
        page.click("text=服務條款")
        page.wait_for_timeout(400)
        check("服務條款開啟", "服務條款" in (page.locator(".sheet h3").text_content() or ""))
        page.click("text=關閉")
        page.click("text=隱私權政策")
        page.wait_for_timeout(400)
        check("隱私權政策開啟", "隱私權政策" in (page.locator(".sheet h3").text_content() or ""))
        page.click("text=關閉")

        # ---------- 13. 移除卡片與持久化 ----------
        before = page.locator("#view-cards .offerrow").count()
        page.locator("#view-cards .xbtn").first.click()
        page.wait_for_timeout(300)
        after = page.locator("#view-cards .offerrow").count()
        check("移除卡片生效", after == before - 1, f"{before}->{after}")
        page.reload()
        page.wait_for_timeout(1500)
        check("移除後持久化", page.locator("#view-cards .offerrow").count() == after)

        # ---------- 13b. 帳號：註冊 → 雲端同步 → 登出 ----------
        import random as _rnd
        em = f"e2e_{_rnd.randint(100000, 999999)}@test.local"
        page.click("#userBtn")
        page.wait_for_timeout(300)
        page.fill("#accEmail", em)
        page.fill("#accPw", "secret123")
        page.click("text=註冊新帳號")
        page.wait_for_timeout(900)
        check("註冊成功並提示雲端同步", page.locator("text=卡簿已雲端同步").count() >= 1)

        before = page.locator("#view-cards .offerrow").count()
        page.reload()
        page.wait_for_timeout(1800)
        after = page.locator("#view-cards .offerrow").count()
        check("重載後雲端卡簿同步", after == before, f"{before}->{after}")

        page.click("#userBtn")
        page.wait_for_timeout(300)
        page.click("text=登出")
        page.wait_for_timeout(400)
        check("登出清除 token（回本地模式）",
              page.evaluate("localStorage.getItem('cp_token')") is None)

        # ---------- 14. 無 JS 錯誤 ----------
        check("全程無 pageerror", len(errors) == 0, f"errors={errors[:2]}")

        browser.close()

    print(f"\n═══ 結果：{len(PASSED)} 通過 / {len(FAILED)} 失敗 ═══")
    if FAILED:
        print("失敗項目：", FAILED)
        sys.exit(1)


if __name__ == "__main__":
    run()
