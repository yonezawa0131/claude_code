import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
// astro:content の再エクスポートは Astro 7 で非推奨になったので zod から直接使う
import * as z from 'zod';

/** 記事内で紹介する商品・サービス1件分 */
const productSchema = z.object({
  name: z.string(),
  /** 表内での短縮名。省略時は name を使う */
  shortName: z.string().optional(),
  /** アフィリエイトリンク。未取得の間は空にしておき、リンクは出さない */
  url: z.string().optional(),
  /** 参考価格の表示用文字列（「12,800円」「月額1,078円」など） */
  price: z.string().optional(),
  /** 5点満点 */
  rating: z.number().min(0).max(5).optional(),
  pros: z.array(z.string()).default([]),
  cons: z.array(z.string()).default([]),
  /** 比較表に出す任意の属性 */
  specs: z.record(z.string(), z.string()).default({}),
  /** 実際に自分で使ったか。E-E-A-T の表示に使う */
  tested: z.boolean().default(false),
});

const faqSchema = z.object({
  q: z.string(),
  a: z.string(),
});

const posts = defineCollection({
  loader: glob({ base: './src/content/posts', pattern: '**/*.{md,mdx}' }),
  schema: ({ image }) =>
    z.object({
      title: z.string().max(64),
      /** meta description。日本語で 80〜120 文字を目安にする */
      description: z.string().min(40).max(160),
      publishDate: z.coerce.date(),
      updatedDate: z.coerce.date().optional(),
      category: z.string(),
      tags: z.array(z.string()).default([]),
      heroImage: image().optional(),
      heroImageAlt: z.string().optional(),
      draft: z.boolean().default(false),
      /** 検索エンジンに出したくないページ（重複・薄い記事の隔離用） */
      noindex: z.boolean().default(false),
      /** アフィリエイトリンクを含むか。false なら PR 表記を出さない */
      hasAffiliate: z.boolean().default(true),
      /** 比較表・商品カードの元データ */
      products: z.array(productSchema).default([]),
      /** FAQPage 構造化データとして出力される */
      faq: z.array(faqSchema).default([]),
      /** 記事上部の要点。AI 検索に引用されやすくするための要約 */
      keyPoints: z.array(z.string()).default([]),
      /** 内部リンク用。関連させたい記事の id を明示指定できる */
      related: z.array(z.string()).default([]),
    }),
});

export const collections = { posts };
