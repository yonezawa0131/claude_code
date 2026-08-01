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
    '掲載している評価は、記載のない限り運営者が実際に購入・使用した上での一次情報です。',
    '広告収益を得ているリンクを含みますが、評価内容は広告出稿の有無に影響されません。',
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
