// 組裝 www/（Capacitor 打包用）：複製網頁殼＋靜態資料，不含後端/管線/開發檔
import { cpSync, rmSync, mkdirSync } from 'node:fs';

rmSync('www', { recursive: true, force: true });
mkdirSync('www', { recursive: true });

for (const item of ['index.html', 'icons', 'web', 'legal']) {
  cpSync(item, `www/${item}`, { recursive: true });
}
console.log('www/ 組裝完成（index.html + icons + web/data + legal）');
