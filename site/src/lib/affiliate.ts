/**
 * リンク組み立ての純粋ロジック。consts.ts に依存させないことで、
 * 設定を差し替えたテストが書けるようにしている。
 *
 * 商品1件あたりのショップリンク。
 *
 * 各値は「ID」か「完全なURL」のどちらでも書ける。
 * - ID を書いた場合は、consts.ts の識別子を使ってリンクを組み立てる
 * - `http` で始まる文字列を書いた場合は、それをそのまま使う
 *   （ASPが発行したリンクをそのまま貼りたいとき用）
 *
 * ID を書いたのに識別子が未設定の場合、そのリンクは出力されない。
 * タグの付いていないリンクを出しても成果にならず、読者を外に流すだけになるため。
 */
export type ShopLinks = {
  /** ASIN（英数字10桁）または完全URL */
  amazon?: string;
  /** 楽天の商品URL、またはASPが発行したリンク */
  rakuten?: string;
  /** Yahoo!ショッピングのリンク（バリューコマース経由） */
  yahoo?: string;
  /** メーカー公式。アフィリエイトでない場合もある */
  official?: string;
};

export type ShopKind = keyof ShopLinks;

export type ResolvedLink = {
  shop: ShopKind;
  /** ボタンに出す文字列 */
  label: string;
  href: string;
  /** アフィリエイトリンクか。false なら rel に sponsored を付けない */
  sponsored: boolean;
};

export type AffiliateConfig = {
  amazonTag: string;
  rakutenId: string;
  amazonUseCartLink: boolean;
};

const SHOP_LABEL: Record<ShopKind, string> = {
  amazon: 'Amazon',
  rakuten: '楽天市場',
  yahoo: 'Yahoo!ショッピング',
  official: '公式サイト',
};

const isUrl = (value: string) => /^https?:\/\//.test(value);

/** ASINは英数字10桁。B0 で始まるものが多いが、書籍のISBNなど例外もある */
const isAsin = (value: string) => /^[A-Z0-9]{10}$/i.test(value);

function amazonHref(value: string, config: AffiliateConfig): string | null {
  if (isUrl(value)) return value;
  if (!isAsin(value)) return null;
  if (!config.amazonTag) return null;

  const tag = encodeURIComponent(config.amazonTag);
  const asin = encodeURIComponent(value);

  // /ref=nosim は公式ヘルプに載っているテキストリンクの形式。
  // 付けないとワンクリック購入ページへ飛ばされることがある。
  return config.amazonUseCartLink
    ? `https://www.amazon.co.jp/gp/aws/cart/add.html?AssociateTag=${tag}&ASIN.1=${asin}&Quantity.1=1`
    : `https://www.amazon.co.jp/dp/${asin}/ref=nosim?tag=${tag}`;
}

/**
 * frontmatter の links を、実際に出力できるリンクの配列に変換する。
 * 配列の順序が、そのままボタンの並び順になる。
 */
export function resolveLinks(
  links: ShopLinks | undefined,
  config: AffiliateConfig,
): ResolvedLink[] {
  if (!links) return [];

  const resolved: ResolvedLink[] = [];

  const push = (shop: ShopKind, href: string | null, sponsored = true) => {
    if (href) resolved.push({ shop, label: SHOP_LABEL[shop], href, sponsored });
  };

  if (links.amazon) push('amazon', amazonHref(links.amazon, config));
  // 楽天・Yahoo は商品URLの形が一定でないため、ASPが発行したURLをそのまま貼る運用。
  // 発行済みリンクにはIDが埋まっているので、識別子が未設定でも使える。
  if (links.rakuten) push('rakuten', isUrl(links.rakuten) ? links.rakuten : null);
  if (links.yahoo) push('yahoo', isUrl(links.yahoo) ? links.yahoo : null);
  // 公式サイトはアフィリエイトでないことが多いので sponsored を外す
  if (links.official) push('official', isUrl(links.official) ? links.official : null, false);

  return resolved;
}

export function hasAnyLink(links: ShopLinks | undefined, config: AffiliateConfig): boolean {
  return resolveLinks(links, config).length > 0;
}
