/**
 * サイト全体の identity と設定。
 * ドメイン取得・運営者名の変更時はこのファイルだけを書き換える。
 */

export const SITE = {
  /** 本番URL。末尾スラッシュなし。独自ドメインを取ったら書き換える */
  url: 'https://rokujo-desk.pages.dev',
  name: '6畳デスク研究所',
  /** <title> の末尾に付く短縮名 */
  shortName: '6畳デスク研究所',
  description:
    '6畳ワンルームや賃貸の限られたスペースで、在宅ワーク用のデスク環境を作るための実測データと寸法ガイド。狭い部屋という制約を前提に、置けるもの・置けないものを具体的な数字で判断できるようにします。',
  lang: 'ja',
  locale: 'ja_JP',
  /** 運営者名。公開前に実際の名前・ハンドルネームに変更する */
  author: '運営者',
  /** 問い合わせ先。公開前に実在するアドレスに変更する */
  email: '',
  defaultOgImage: '/og-default.png',
  /** X(Twitter) アカウント。@ なし。未設定なら空文字 */
  twitter: '',
} as const;

/** ステマ規制（景品表示法の指定告示・2023年10月1日施行）対応の表記 */
export const PR_DISCLOSURE = {
  /** 記事のファーストビュー内に必ず出す一文 */
  short: '本ページはプロモーションを含みます',
  long: '当サイトは、Amazonアソシエイトをはじめとするアフィリエイトプログラムに参加しています。当サイトを経由して商品を購入いただくと、当サイトに紹介料が支払われる場合があります。紹介料の有無が記事内の評価や順位に影響することはありません。',
} as const;

export type NavItem = {
  label: string;
  href: string;
  /** ヘッダーに出すか（false ならフッターのみ） */
  header?: boolean;
};

/** 記事カテゴリ。記事 frontmatter の category はここの slug と一致させる */
export const CATEGORIES = [
  {
    slug: 'layout',
    name: 'レイアウト・寸法',
    description:
      '6畳・ワンルームに何をどう置けるのか。実際の畳の寸法から逆算した、置けるサイズの判断基準をまとめています。',
  },
  {
    slug: 'desk',
    name: 'デスク',
    description:
      '狭い部屋に収まる幅・奥行きのデスク選び。電動昇降デスクを狭い部屋で使えるかどうかの条件も扱います。',
  },
  {
    slug: 'monitor',
    name: 'モニター・アーム',
    description:
      '賃貸でモニターアームが使えるかの判断基準と、限られた奥行きでモニターを置くための条件をまとめています。',
  },
  {
    slug: 'chair',
    name: 'チェア',
    description:
      '狭い部屋では、椅子そのものより「引くスペース」が問題になります。必要な後方スペースから考えるチェア選び。',
  },
] as const satisfies readonly { slug: string; name: string; description: string }[];

export const NAV: NavItem[] = CATEGORIES.map((c) => ({
  label: c.name,
  href: `/category/${c.slug}`,
}));
