/**
 * 公開前チェック。
 * ビルドは通るが公開すると問題になるもの（法令表記の抜け、カテゴリのtypo、
 * 使っていない製品に評価を付けている等）を機械的に拾う。
 *
 * 使い方: npm run audit:content
 */
import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(new URL('../package.json', import.meta.url)));
const postsDir = path.join(root, 'src/content/posts');

const CATEGORY_SLUGS = ['layout', 'desk', 'monitor', 'chair'];

/**
 * 薬機法・景表法で個人が踏みやすい表現。
 * デスク環境ジャンルは健康食品ほどの危険はないが、
 * 「腰痛が治る」のような身体への効果を断定する表現は同じ地雷になる。
 */
const RISKY_PHRASES = [
  { pattern: /治る|治療|完治|改善します|解消されます/, why: '身体への効果を断定する表現（薬機法・景表法のリスク）' },
  { pattern: /No\.?1|ナンバーワン|日本一|世界一/i, why: '根拠が必要な最上級表現（景表法・優良誤認）' },
  { pattern: /絶対に|必ず痩せ|永久に/, why: '断定・誇大表現' },
];

const errors = [];
const warnings = [];

const files = (await readdir(postsDir)).filter((f) => /\.mdx?$/.test(f));

if (files.length === 0) {
  console.log('記事がありません。');
  process.exit(0);
}

for (const file of files) {
  const raw = await readFile(path.join(postsDir, file), 'utf8');
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) {
    errors.push(`${file}: frontmatter が見つかりません`);
    continue;
  }
  const [, fm] = match;
  const body = raw.slice(match[0].length);
  const at = (msg) => `${file}: ${msg}`;

  const field = (name) => {
    const m = fm.match(new RegExp(`^${name}:\\s*(.*)$`, 'm'));
    return m ? m[1].trim().replace(/^['"]|['"]$/g, '') : undefined;
  };

  const category = field('category');
  if (!category) {
    errors.push(at('category が未設定です'));
  } else if (!CATEGORY_SLUGS.includes(category)) {
    errors.push(
      at(`category "${category}" は consts.ts の CATEGORIES にありません（カテゴリページが生成されません）`),
    );
  }

  const description = field('description');
  if (description) {
    if (description.length < 40) {
      errors.push(at(`description が短すぎます（${description.length}文字、40文字以上必要）`));
    } else if (description.length > 120) {
      warnings.push(
        at(`description が ${description.length} 文字あります。検索結果では120文字前後で切られます`),
      );
    }
  }

  const title = field('title');
  if (title && title.length > 32) {
    warnings.push(at(`title が ${title.length} 文字あります。検索結果では32文字前後で切られます`));
  }

  // 使っていない製品に星をつけていないか
  const productBlocks = fm.split(/^\s*-\s+name:/m).slice(1);
  for (const block of productBlocks) {
    const hasRating = /\brating:/.test(block);
    const tested = /\btested:\s*true/.test(block);
    const name = block.split('\n')[0].trim();
    if (hasRating && !tested) {
      errors.push(
        at(`製品「${name}」に rating がありますが tested: false です。使っていない製品に評価を付けないでください`),
      );
    }
  }

  if (/hasAffiliate:\s*false/.test(fm) && /amzn\.to|amazon\.co\.jp|a8\.net|af\.moshimo/.test(raw)) {
    errors.push(at('hasAffiliate: false ですがアフィリエイトらしきリンクがあります（PR表記が出ません）'));
  }

  for (const { pattern, why } of RISKY_PHRASES) {
    const found = body.match(pattern);
    if (found) warnings.push(at(`「${found[0]}」— ${why}`));
  }

  const h2Count = (body.match(/^##\s/gm) ?? []).length;
  if (h2Count < 2) warnings.push(at(`見出し(h2)が ${h2Count} 個です。構成が浅い可能性があります`));

  if (!/^keyPoints:/m.test(fm)) {
    warnings.push(at('keyPoints が未設定です。冒頭の要点はAI検索の引用と直帰率の両方に効きます'));
  }
}

if (warnings.length > 0) {
  console.log(`\n警告 (${warnings.length})`);
  for (const w of warnings) console.log(`  - ${w}`);
}

if (errors.length > 0) {
  console.log(`\nエラー (${errors.length})`);
  for (const e of errors) console.log(`  - ${e}`);
  console.log('');
  process.exit(1);
}

console.log(`\n${files.length} 記事をチェックしました。エラーはありません。\n`);
