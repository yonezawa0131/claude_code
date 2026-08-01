import type { APIRoute } from 'astro';

import { getPosts, categoryName } from '../lib/posts';
import { SITE, CATEGORIES } from '../consts';

/**
 * llms.txt。AI 検索側の対応状況はまちまちで効果は未知数だが、
 * 生成コストがほぼゼロなので出しておく。
 */
export const GET: APIRoute = async () => {
  const posts = await getPosts();

  const body = [
    `# ${SITE.name}`,
    '',
    `> ${SITE.description}`,
    '',
    `運営者: ${SITE.author}`,
    '',
    '## このサイトについて',
    '',
    '狭い部屋という制約のもとで、何が置けて何が置けないかを寸法から判断できるようにしています。',
    '記事中の寸法・規格の数値には出典を明記しています。',
    '実機を使用した上での記述と、公表スペックにもとづく比較は、記事内で区別して書いています。',
    '広告収益を得ているリンクを含みますが、その有無が評価や掲載順に影響することはありません。',
    '',
  ];

  for (const category of CATEGORIES) {
    const inCategory = posts.filter((p) => p.data.category === category.slug);
    if (inCategory.length === 0) continue;

    body.push(`## ${category.name}`, '');
    for (const post of inCategory) {
      const url = new URL(`/posts/${post.id}`, SITE.url).href;
      body.push(`- [${post.data.title}](${url}): ${post.data.description}`);
    }
    body.push('');
  }

  const uncategorized = posts.filter(
    (p) => !CATEGORIES.some((c) => c.slug === p.data.category),
  );
  if (uncategorized.length > 0) {
    body.push('## その他', '');
    for (const post of uncategorized) {
      const url = new URL(`/posts/${post.id}`, SITE.url).href;
      body.push(
        `- [${post.data.title}](${url}) (${categoryName(post.data.category)}): ${post.data.description}`,
      );
    }
    body.push('');
  }

  return new Response(body.join('\n'), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
