/* 卡優惠 CardPerks Service Worker
   快取策略：
   - App 殼（頁面/圖示）：cache-first（改版靠版本號快取名稱）
   - 資料（web/data/*.json）：network-first，斷網退回上次快取（離線也能查優惠） */
const VERSION = 'cp-v2';
const SHELL = `${VERSION}-shell`;
const DATA = `${VERSION}-data`;
const SHELL_ASSETS = [
  './', './index.html', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png', './icons/maskable-512.png', './icons/apple-touch-icon.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // 後端 API 與跨源請求一律放行（動態資料不進 SW 邏輯）
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname.includes('/api/')) return;

  if (url.pathname.includes('/web/data/')) {
    // 資料：network-first，離線回快取
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(DATA).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
  } else {
    // App 殼：cache-first，無快取才上網
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request))
    );
  }
});
