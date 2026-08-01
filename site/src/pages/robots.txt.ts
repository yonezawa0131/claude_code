import type { APIRoute } from 'astro';
import { SITE } from '../consts';

/**
 * AIクローラーの方針:
 * 検索・回答時に参照する系（OAI-SearchBot / PerplexityBot / ChatGPT-User）は許可する。
 * これらを止めると AI 検索での引用機会そのものを失うため。
 * 学習専用（GPTBot / ClaudeBot / Google-Extended 等）はブロックしても引用は止まらないので、
 * ここでは許可したままにしている。方針を変える場合は下の disallowTrainingBots を true にする。
 */
const disallowTrainingBots = false;

const trainingBots = ['GPTBot', 'ClaudeBot', 'Google-Extended', 'Applebot-Extended', 'CCBot'];

export const GET: APIRoute = () => {
  const lines = [
    'User-agent: *',
    'Allow: /',
    '',
    '# AI検索の回答生成時に参照するクローラーは明示的に許可',
    'User-agent: OAI-SearchBot',
    'Allow: /',
    '',
    'User-agent: ChatGPT-User',
    'Allow: /',
    '',
    'User-agent: PerplexityBot',
    'Allow: /',
    '',
  ];

  if (disallowTrainingBots) {
    lines.push('# 学習目的のクローラーは拒否');
    for (const bot of trainingBots) {
      lines.push(`User-agent: ${bot}`, 'Disallow: /', '');
    }
  }

  lines.push(`Sitemap: ${new URL('/sitemap-index.xml', SITE.url).href}`, '');

  return new Response(lines.join('\n'), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
