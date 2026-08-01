/**
 * favicon と OGP デフォルト画像を生成する。
 * サイト名やブランドカラーを変えたら `npm run assets` で作り直す。
 */
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import sharp from 'sharp';

const root = path.dirname(fileURLToPath(new URL('../package.json', import.meta.url)));
const publicDir = path.join(root, 'public');

const BRAND = '#2f7d55';
const BRAND_DARK = '#1e5638';
const INK = '#1a1a1a';

/** 部屋の枠の中にデスクとモニターが収まっている、という記号 */
const mark = (size) => `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="${size}" height="${size}">
  <rect width="64" height="64" rx="12" fill="${BRAND}"/>
  <g fill="none" stroke="#ffffff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="13" y="13" width="38" height="38" rx="3"/>
    <path d="M19 39h26"/>
    <path d="M22 39v7M42 39v7"/>
    <rect x="26" y="24" width="15" height="10" rx="1.5"/>
  </g>
</svg>`;

const ogImage = `
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#eef5f0"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="0" y="0" width="1200" height="14" fill="${BRAND}"/>

  <g transform="translate(96, 150)">
    <g transform="scale(1.5)">
      <rect width="64" height="64" rx="12" fill="${BRAND}"/>
      <g fill="none" stroke="#ffffff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="13" y="13" width="38" height="38" rx="3"/>
        <path d="M19 39h26"/>
        <path d="M22 39v7M42 39v7"/>
        <rect x="26" y="24" width="15" height="10" rx="1.5"/>
      </g>
    </g>
  </g>

  <text x="96" y="330" font-family="IPAPGothic, sans-serif" font-size="76" font-weight="bold" fill="${INK}">
    6畳デスク研究所
  </text>
  <text x="96" y="400" font-family="IPAPGothic, sans-serif" font-size="34" fill="${BRAND_DARK}">
    狭い部屋で、ちゃんと働ける机をつくる
  </text>

  <g font-family="IPAPGothic, sans-serif" font-size="26" fill="#5b6b62">
    <text x="96" y="470">実測と寸法から、置けるかどうかを判断する</text>
  </g>

  <rect x="96" y="512" width="150" height="6" rx="3" fill="${BRAND}"/>
</svg>`;

await mkdir(publicDir, { recursive: true });

await writeFile(path.join(publicDir, 'favicon.svg'), `${mark(64).trim()}\n`, 'utf8');

await sharp(Buffer.from(mark(180)))
  .png()
  .toFile(path.join(publicDir, 'apple-touch-icon.png'));

await sharp(Buffer.from(ogImage))
  .png({ quality: 90 })
  .toFile(path.join(publicDir, 'og-default.png'));

console.log('生成しました: favicon.svg / apple-touch-icon.png / og-default.png');
