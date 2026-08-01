import { chromium } from 'playwright-core';
const dir = '/tmp/claude-0/-home-user-claude-code/a53fc67c-2e27-576c-9f16-30dfbab0b0e6/scratchpad';
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const p = await b.newPage({ viewport: { width: 1200, height: 1900 } });
await p.goto('http://localhost:4340/', { waitUntil: 'networkidle' });
await p.screenshot({ path: `${dir}/home8.png`, fullPage: false });
const scroll = await p.evaluate(() => { window.scrollTo(9999,0); const x = window.scrollX; window.scrollTo(0,0); return x; });
console.log('横スクロール量:', scroll);
await b.close();
