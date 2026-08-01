import rss from '@astrojs/rss';
import type { APIRoute } from 'astro';

import { getPosts } from '../lib/posts';
import { SITE } from '../consts';

export const GET: APIRoute = async (context) => {
  const posts = await getPosts();

  return rss({
    title: SITE.name,
    description: SITE.description,
    site: context.site ?? SITE.url,
    customData: `<language>ja</language>`,
    items: posts
      .filter((post) => !post.data.noindex)
      .map((post) => ({
        title: post.data.title,
        description: post.data.description,
        pubDate: post.data.publishDate,
        link: `/posts/${post.id}`,
        categories: [post.data.category, ...post.data.tags],
      })),
  });
};
