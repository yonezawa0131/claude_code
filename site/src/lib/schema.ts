import { SITE } from '../consts';

/**
 * JSON-LD の組み立て。
 * AI 検索（AI Overviews / ChatGPT Search など）に拾わせることと、
 * リッチリザルトの両方を狙って Article / Product / FAQ / Breadcrumb を出す。
 */

type Thing = Record<string, unknown>;

const abs = (path: string) => new URL(path, SITE.url).href;

export function organization(): Thing {
  return {
    '@type': 'Organization',
    '@id': abs('/#organization'),
    name: SITE.name,
    url: SITE.url,
    ...(SITE.twitter ? { sameAs: [`https://x.com/${SITE.twitter}`] } : {}),
  };
}

export function website(): Thing {
  return {
    '@type': 'WebSite',
    '@id': abs('/#website'),
    url: SITE.url,
    name: SITE.name,
    description: SITE.description,
    inLanguage: SITE.lang,
    publisher: { '@id': abs('/#organization') },
  };
}

export function person(): Thing {
  return {
    '@type': 'Person',
    '@id': abs('/#author'),
    name: SITE.author,
    url: abs('/about'),
  };
}

export function breadcrumbs(
  trail: { name: string; href?: string }[],
): Thing {
  return {
    '@type': 'BreadcrumbList',
    itemListElement: trail.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.name,
      ...(item.href ? { item: abs(item.href) } : {}),
    })),
  };
}

export function article(input: {
  title: string;
  description: string;
  url: string;
  image?: string;
  publishDate: Date;
  updatedDate?: Date;
}): Thing {
  return {
    '@type': 'Article',
    '@id': `${abs(input.url)}#article`,
    headline: input.title,
    description: input.description,
    inLanguage: SITE.lang,
    mainEntityOfPage: { '@type': 'WebPage', '@id': abs(input.url) },
    datePublished: input.publishDate.toISOString(),
    dateModified: (input.updatedDate ?? input.publishDate).toISOString(),
    author: { '@id': abs('/#author') },
    publisher: { '@id': abs('/#organization') },
    ...(input.image ? { image: [abs(input.image)] } : {}),
  };
}

export function faqPage(faq: { q: string; a: string }[]): Thing | null {
  if (faq.length === 0) return null;
  return {
    '@type': 'FAQPage',
    mainEntity: faq.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  };
}

/**
 * レビュー付き商品。
 * 自分で使っていない商品に Review を付けるとガイドライン違反になりうるので、
 * tested な商品だけ Review を出す。
 */
export function itemList(
  products: {
    name: string;
    url?: string;
    rating?: number;
    tested: boolean;
  }[],
  pageUrl: string,
): Thing | null {
  if (products.length === 0) return null;
  return {
    '@type': 'ItemList',
    '@id': `${abs(pageUrl)}#itemlist`,
    itemListElement: products.map((p, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: p.name,
      ...(p.url ? { url: p.url } : {}),
    })),
  };
}

export function graph(nodes: (Thing | null | undefined)[]): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@graph': nodes.filter((n): n is Thing => Boolean(n)),
  });
}
