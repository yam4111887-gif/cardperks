"""卡優惠 CardPerks — 爬蟲 v2（Playwright 無頭瀏覽器版）

台灣銀行官網多為 JS 動態渲染，requests 抓不到內容，故改用 Chromium 渲染後解析。

用法：
    cd backend
    python pipeline/crawler.py                    # 抓總覽頁 + 前 4 條活動明細
    python pipeline/crawler.py --banks esun,cathay
    python pipeline/crawler.py --details 6 --limit 12

輸出：
    out/crawled_items.jsonl   每條含 title/url/detail_text（供 LLM 解析）
    out/snapshots/*.html      頁面快照（法遵存證：資料爭議時證明來源當時內容）

法遵三原則（不變）：遵守 robots.txt、每站限速 3 秒、自識別 UA、只抓公開頁面。
"""
import argparse
import json
import os
import re
import time
import urllib.robotparser
from datetime import datetime, timezone

import requests as rq
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SNAP_DIR = os.path.join(OUT_DIR, "snapshots")
OUT_FILE = os.path.join(OUT_DIR, "crawled_items.jsonl")

# 業界標準自識別格式（Googlebot 風格）；備註：含 +@; 組合的 UA 會觸發部分銀行 WAF 回 400
UA = "Mozilla/5.0 (compatible; CardPerksBot/0.1; +https://cardperks.example.com/bot)"
REQUEST_INTERVAL_SEC = 3
RENDER_WAIT_MS = 2500  # 等 JS 渲染

# 2026-08-16 查證過的官方優惠頁（頁面會搬家，需定期人工複查）
BANK_SOURCES = [
    {"bank": "esun", "name": "玉山銀行",
     "url": "https://www.esunbank.com.tw/bank/personal/credit-card/discount/shops"},
    {"bank": "cathay", "name": "國泰世華",
     "url": "https://www.cathay-cube.com.tw/cathaybk/personal/event/overview"},
    {"bank": "ctbc", "name": "中國信託",
     # 活動登錄頁有應用層防護（APP-1053），改抓靜態的 LINE Pay 卡優惠一覽
     "url": "https://www.ctbcbank.com/content/dam/minisite/long/creditcard/LINEPay/store.html"},
    {"bank": "fubon", "name": "台北富邦",
     "url": "https://cardpromote.taipeifubon.com.tw/"},
    {"bank": "fubon", "name": "台北富邦(美食)", "url": "https://cardpromote.taipeifubon.com.tw/promotion/Type?category=A"},
    {"bank": "fubon", "name": "台北富邦(旅遊)", "url": "https://cardpromote.taipeifubon.com.tw/promotion/Type?category=B"},
    {"bank": "fubon", "name": "台北富邦(購物)", "url": "https://cardpromote.taipeifubon.com.tw/promotion/Type?category=C"},
    {"bank": "fubon", "name": "台北富邦(數位)", "url": "https://cardpromote.taipeifubon.com.tw/promotion/Type?category=D"},
    {"bank": "hsbc", "name": "滙豐銀行", "url": "https://shop.hsbc.com.tw/"},
    {"bank": "sinopac", "name": "永豐銀行",
     "url": "https://bank.sinopac.com/sinopacBT/personal/credit-card/discount/list.html"},
    # 台新：robots.txt 連線失敗（本地環境連不上），部署到台灣主機後再啟用
    # {"bank": "taishin", "name": "台新銀行", "url": "https://card.taishinbank.com.tw/TSDIB1C_11/"},
]

KEYWORDS = ("優惠", "回饋", "活動", "刷卡", "登錄", "里程", "折扣", "首刷", "滿額", "現折")
SKIP_URL = ("javascript:", "mailto:", "tel:", "#")


def robots_allows(url: str) -> bool:
    """依 RFC 9309 檢查 robots.txt（用 requests 避開 urllib SSL 憑證鏈問題）
    - 404/410 無 robots.txt → 允許
    - 5xx / 連線失敗 → 保守不爬
    - 200 → 依規則判斷
    """
    root = "/".join(url.split("/")[:3])
    r = None
    for _ in range(2):  # 網路偶發逾時重試一次，避免誤判
        try:
            r = rq.get(root + "/robots.txt", headers={"User-Agent": UA}, timeout=15)
            break
        except Exception:
            time.sleep(2)
    if r is None:
        return False
    if r.status_code in (404, 410):
        return True
    if r.status_code != 200:
        return False
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    return rp.can_fetch(UA, url)


def clean_text(s: str, limit=4000) -> str:
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()[:limit]


def crawl(banks_filter, link_limit, details_n, dry_run, max_pages=3):
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SNAP_DIR, exist_ok=True)
    items_all = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="zh-TW",
                                  viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        for i, src in enumerate(BANK_SOURCES):
            if banks_filter and src["bank"] not in banks_filter:
                continue
            if i > 0:
                time.sleep(REQUEST_INTERVAL_SEC)
            if not robots_allows(src["url"]):
                print(f"[SKIP] {src['name']}：robots.txt 不允許/無法確認，略過")
                continue
            if dry_run:
                print(f"[DRY ] {src['name']} robots OK：{src['url']}")
                continue

            print(f"[GET ] {src['name']} {src['url']}")
            try:
                page.goto(src["url"], timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(RENDER_WAIT_MS)
                html = page.content()
            except Exception as e:
                print(f"[FAIL] {src['name']}: {type(e).__name__}: {str(e)[:100]}")
                continue

            # 快照存證
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
            snap_path = os.path.join(SNAP_DIR, f"{src['bank']}_{stamp}.html")
            with open(snap_path, "w", encoding="utf-8") as f:
                f.write(html)

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            root_domain = "/".join(src["url"].split("/")[:3])
            seen, items = set(), []
            for a in soup.find_all("a", href=True):
                text = a.get_text(" ", strip=True)
                if len(text) < 6 or not any(k in text for k in KEYWORDS):
                    continue
                href = a["href"]
                if href.startswith("/"):
                    href = root_domain + href
                if not href.startswith("http") or href.startswith(SKIP_URL) or href in seen:
                    continue
                seen.add(href)
                items.append({"bank": src["bank"], "bank_name": src["name"],
                              "title": text, "url": href})
                if len(items) >= link_limit:
                    break

            print(f"       收集 {len(items)} 條活動連結")

            # 「一覽表」型頁面（優惠直接列在頁面上，無活動連結）：
            # 把頁面主內容當作一條待解析項目，並跟隨分頁（navigation-N-pageLink）
            if not items:
                body_text = clean_text(soup.get_text("\n"), 6000)
                # 偵測分頁連結（相對 URL，如 ./Type?0-1.-fmList-...-navigation-1-pageLink&category=A）
                page_nums = set()
                for a in soup.find_all("a", href=True):
                    m = re.search(r"navigation-(\d+)-pageLink", a["href"])
                    if m:
                        page_nums.add(int(m.group(1)) + 1)  # navigation-1 = 第 2 頁
                max_page = min(max(page_nums) if page_nums else 1, max_pages)
                for pg in range(2, max_page + 1):
                    time.sleep(REQUEST_INTERVAL_SEC)
                    try:
                        # 用上一頁解析出的分頁 URL 模式直接導航
                        page_links = [a for a in soup.find_all("a", href=True)
                                      if f"navigation-{pg - 1}-pageLink" in a["href"]]
                        if not page_links:
                            break
                        href = page_links[0]["href"]
                        if href.startswith("./"):
                            href = root_domain + href[1:]
                        elif href.startswith("/"):
                            href = root_domain + href
                        page.goto(href, timeout=45000, wait_until="domcontentloaded")
                        page.wait_for_timeout(RENDER_WAIT_MS)
                        psoup = BeautifulSoup(page.content(), "html.parser")
                        for tag in psoup(["script", "style", "noscript"]):
                            tag.decompose()
                        ptext = clean_text(psoup.get_text("\n"), 6000)
                        body_text += f"\n\n===== 第 {pg} 頁 =====\n{ptext}"
                        print(f"       ↳ 分頁 {pg}/{max_page}（+{len(ptext)} 字）")
                        soup = psoup  # 下一頁的連結從本頁找
                    except Exception as e:
                        print(f"       ↳ 分頁 {pg} 失敗 {type(e).__name__}")
                        break
                if len(body_text) > 200:
                    items.append({"bank": src["bank"], "bank_name": src["name"],
                                  "title": soup.title.get_text(strip=True) if soup.title else src["name"],
                                  "url": src["url"], "detail_text": body_text[:14000],
                                  "fetched_at": datetime.now(timezone.utc).isoformat(),
                                  "page_url": src["url"]})
                    print(f"       ↳ 一覽頁模式：主內容＋分頁共 {len(body_text)} 字")

            # 抓前 N 條明細頁文字（供 LLM 解析）
            for it in items[:details_n]:
                if it.get("detail_text"):
                    items_all.append(it)
                    continue
                time.sleep(REQUEST_INTERVAL_SEC)
                try:
                    page.goto(it["url"], timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(RENDER_WAIT_MS)
                    dhtml = page.content()
                    dsoup = BeautifulSoup(dhtml, "html.parser")
                    for tag in dsoup(["script", "style", "noscript"]):
                        tag.decompose()
                    it["detail_text"] = clean_text(dsoup.get_text("\n"))
                    print(f"       ↳ 明細：{it['title'][:36]}（{len(it['detail_text'])} 字）")
                except Exception as e:
                    it["detail_text"] = ""
                    print(f"       ↳ 明細失敗 {type(e).__name__}")
                it["fetched_at"] = datetime.now(timezone.utc).isoformat()
                it["page_url"] = src["url"]
                items_all.append(it)

        browser.close()

    # 與既有結果合併（同 URL 覆蓋舊資料），重新編號
    merged = {}
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    old = json.loads(line)
                    merged[old["url"]] = old
    for it in items_all:
        it["id"] = 0
        merged[it["url"]] = it
    rows = sorted(merged.values(), key=lambda x: (x["bank"], x["url"]))
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for idx, it in enumerate(rows, 1):
            it["id"] = idx
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"\n完成：本次 {len(items_all)} 條，累計 {len(rows)} 條 → {OUT_FILE}")
    print("下一步：python pipeline/llm_parse.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--banks", default="", help="逗號分隔 bank code，如 esun,cathay")
    ap.add_argument("--limit", type=int, default=10, help="每站收集連結上限")
    ap.add_argument("--details", type=int, default=4, help="每站抓取明細頁數")
    ap.add_argument("--max-pages", type=int, default=3, help="一覽頁型分頁最多跟幾頁")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    crawl(set(filter(None, args.banks.split(","))), args.limit, args.details,
         args.dry_run, args.max_pages)
