// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap, { ChangeFreqEnum } from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

import { SITE } from './src/consts';

export default defineConfig({
  site: SITE.url,
  trailingSlash: 'ignore',
  build: {
    format: 'directory',
  },
  prefetch: {
    prefetchAll: true,
    defaultStrategy: 'viewport',
  },
  integrations: [
    mdx(),
    sitemap({
      filter: (page) => !page.includes('/thanks') && !page.includes('/404'),
      serialize(item) {
        // 記事は更新頻度が高い扱い、規約系の固定ページは低い扱いにする
        if (item.url.includes('/posts/')) {
          item.changefreq = ChangeFreqEnum.WEEKLY;
          item.priority = 0.8;
        } else if (item.url === `${SITE.url}/`) {
          item.changefreq = ChangeFreqEnum.DAILY;
          item.priority = 1.0;
        } else {
          item.changefreq = ChangeFreqEnum.MONTHLY;
          item.priority = 0.4;
        }
        return item;
      },
    }),
  ],
  markdown: {
    shikiConfig: {
      themes: { light: 'github-light', dark: 'github-dark' },
      wrap: true,
    },
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
