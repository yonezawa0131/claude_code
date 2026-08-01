import { test } from 'node:test';
import assert from 'node:assert/strict';

import { resolveLinks, hasAnyLink, type AffiliateConfig } from './affiliate.ts';

const withTag: AffiliateConfig = {
  amazonTag: 'example-22',
  rakutenId: '1234',
  amazonUseCartLink: false,
};
const noTag: AffiliateConfig = { amazonTag: '', rakutenId: '', amazonUseCartLink: false };
const cartMode: AffiliateConfig = { ...withTag, amazonUseCartLink: true };

test('ASIN からアソシエイトタグ付きのURLを組み立てる', () => {
  const [link] = resolveLinks({ amazon: 'B00MIBN71I' }, withTag);
  assert.equal(link.href, 'https://www.amazon.co.jp/dp/B00MIBN71I/ref=nosim?tag=example-22');
  assert.equal(link.shop, 'amazon');
  assert.equal(link.sponsored, true);
});

test('タグ未設定なら ASIN からリンクを作らない', () => {
  // タグなしのリンクを出すと、成果にならないまま読者をAmazonへ送ることになる
  assert.deepEqual(resolveLinks({ amazon: 'B00MIBN71I' }, noTag), []);
  assert.equal(hasAnyLink({ amazon: 'B00MIBN71I' }, noTag), false);
});

test('完全URLはタグ未設定でもそのまま使う', () => {
  // ASPが発行したリンクには既にIDが埋まっているため
  const url = 'https://www.amazon.co.jp/dp/B00MIBN71I?tag=other-22';
  const [link] = resolveLinks({ amazon: url }, noTag);
  assert.equal(link.href, url);
});

test('カートリンクモードでは add.html 形式になる', () => {
  const [link] = resolveLinks({ amazon: 'B00MIBN71I' }, cartMode);
  assert.equal(
    link.href,
    'https://www.amazon.co.jp/gp/aws/cart/add.html?AssociateTag=example-22&ASIN.1=B00MIBN71I&Quantity.1=1',
  );
});

test('ASINでもURLでもない文字列はリンクにしない', () => {
  assert.deepEqual(resolveLinks({ amazon: 'エルゴトロンLX' }, withTag), []);
  assert.deepEqual(resolveLinks({ amazon: 'B00MIBN' }, withTag), []);
});

test('タグに含まれる記号をエスケープする', () => {
  const [link] = resolveLinks({ amazon: 'B00MIBN71I' }, { ...withTag, amazonTag: 'a b&c' });
  assert.equal(link.href, 'https://www.amazon.co.jp/dp/B00MIBN71I/ref=nosim?tag=a%20b%26c');
});

test('楽天・Yahoo はURLのときだけ通す', () => {
  const rakuten = 'https://hb.afl.rakuten.co.jp/hgc/xxxx/';
  assert.equal(resolveLinks({ rakuten }, withTag)[0].href, rakuten);
  assert.deepEqual(resolveLinks({ rakuten: '商品コード' }, withTag), []);
});

test('公式サイトには sponsored を付けない', () => {
  const [link] = resolveLinks({ official: 'https://www.flexispot.jp/' }, withTag);
  assert.equal(link.shop, 'official');
  assert.equal(link.sponsored, false);
});

test('ボタンの並び順は Amazon → 楽天 → Yahoo → 公式', () => {
  const links = resolveLinks(
    {
      official: 'https://example.com/',
      yahoo: 'https://shopping.yahoo.co.jp/x',
      rakuten: 'https://hb.afl.rakuten.co.jp/x',
      amazon: 'B00MIBN71I',
    },
    withTag,
  );
  assert.deepEqual(
    links.map((l) => l.shop),
    ['amazon', 'rakuten', 'yahoo', 'official'],
  );
});

test('links が未定義・空でも落ちない', () => {
  assert.deepEqual(resolveLinks(undefined, withTag), []);
  assert.deepEqual(resolveLinks({}, withTag), []);
  assert.equal(hasAnyLink(undefined, withTag), false);
});
