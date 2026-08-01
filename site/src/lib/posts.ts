import { getCollection, type CollectionEntry } from 'astro:content';
import { CATEGORIES } from '../consts';

export type Post = CollectionEntry<'posts'>;

const isProd = import.meta.env.PROD;

/** 公開記事を新しい順に返す。本番ビルドでは draft を除外する */
export async function getPosts(): Promise<Post[]> {
  const posts = await getCollection('posts', ({ data }) => !isProd || !data.draft);
  return posts.sort(
    (a, b) => b.data.publishDate.valueOf() - a.data.publishDate.valueOf(),
  );
}

export async function getPostsByCategory(category: string): Promise<Post[]> {
  const posts = await getPosts();
  return posts.filter((p) => p.data.category === category);
}

export function categoryName(slug: string): string {
  return CATEGORIES.find((c) => c.slug === slug)?.name ?? slug;
}

export function categoryDescription(slug: string): string {
  return CATEGORIES.find((c) => c.slug === slug)?.description ?? '';
}

/**
 * 関連記事。frontmatter の related を最優先し、
 * 足りない分を「同カテゴリ」→「タグ一致数が多い順」で埋める。
 * 内部リンクはクローラビリティと回遊率に効くので、必ず一定数出す。
 */
export function relatedPosts(current: Post, all: Post[], limit = 4): Post[] {
  const picked = new Map<string, Post>();

  for (const id of current.data.related) {
    const found = all.find((p) => p.id === id && p.id !== current.id);
    if (found) picked.set(found.id, found);
  }

  const candidates = all
    .filter((p) => p.id !== current.id && !picked.has(p.id))
    .map((p) => {
      const sharedTags = p.data.tags.filter((t) => current.data.tags.includes(t)).length;
      const sameCategory = p.data.category === current.data.category ? 1 : 0;
      return { post: p, score: sameCategory * 3 + sharedTags };
    })
    .filter((c) => c.score > 0)
    .sort(
      (a, b) =>
        b.score - a.score ||
        b.post.data.publishDate.valueOf() - a.post.data.publishDate.valueOf(),
    );

  for (const c of candidates) {
    if (picked.size >= limit) break;
    picked.set(c.post.id, c.post);
  }

  return [...picked.values()].slice(0, limit);
}

/** 日本語の本文からおおまかな読了時間を出す。1分あたり500文字換算 */
export function readingMinutes(body: string): number {
  const chars = body.replace(/\s+/g, '').length;
  return Math.max(1, Math.round(chars / 500));
}
