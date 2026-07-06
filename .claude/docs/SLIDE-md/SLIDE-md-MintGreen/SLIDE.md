# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 日本の上場スタートアップによるコーポレートIR（決算説明）資料。ティール／シアン系のブランドカラーを軸にした、清潔感のあるミニマルなビジネスデザイン。
**マッチするシーン：** 決算説明・IR資料・投資家向けプレゼン・経営報告・コーポレートピッチ

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ティール | #01B8C8 |
| Secondary | ブルー | #0D9ED7 |
| Background | ホワイト | #FFFFFF |
| Accent | ティール | #01B8C8 |
| Text | チャコール | #252525 |
| Text Sub | ダークグレー | #444444 |
| Text Muted | グレー | #9AA0A6 |

**グラデーション：** Primary → Secondary・135deg（斜め）— カード背景・強調要素に使用

```yaml
colors:
  primary: "#01B8C8"
  secondary: "#0D9ED7"
  background: "#FFFFFF"
  accent: "#01B8C8"
  text: "#252525"
  text_sub: "#444444"
  text_muted: "#9AA0A6"
  surface_card: "#F7F9FA"
  surface_soft: "#F4F4F4"
  hairline: "rgba(0,0,0,0.08)"
  gradient_main: "linear-gradient(135deg, #01B8C8, #0D9ED7)"
  gradient_vert: "linear-gradient(180deg, #01B8C8, #0D9ED7)"
```

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 64px | 800 |
| 見出し（H2） | Noto Sans JP | 38px | 700 |
| 本文 | Noto Sans JP | 18px | 400 |
| キャプション | Noto Sans JP | 13px | 400 |
| モノスペース | なし | - | - |

```yaml
typography:
  heading_h1:
    font: "Noto Sans JP"
    size: "64px"
    weight: "800"
  heading_h2:
    font: "Noto Sans JP"
    size: "38px"
    weight: "700"
  body:
    font: "Noto Sans JP"
    size: "18px"
    weight: "400"
  caption:
    font: "Noto Sans JP"
    size: "13px"
    weight: "400"
  mono:
    font: "なし"
    usage: "なし"
```

## Layout

- **スライドサイズ：** 16:9（幅1920px × 高さ1080px）
- **余白（上）：** 76px（ヘッダー帯の高さ分）
- **余白（下）：** 50px
- **余白（左右）：** 80px
- **テキスト整列：** 左寄せ

```yaml
layout:
  slide_size: "16:9"
  width: "1920px"
  height: "1080px"
  header_height: "76px"
  padding_vertical: "60px"
  padding_horizontal: "80px"
  text_align: "left"
```

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部に高さ76pxの帯（背景 #F4F4F4、下ボーダー rgba(0,0,0,0.08))。左寄せでスライドタイトルを表示し、右端にロゴを配置。タイトルと小見出しは「｜」で区切る。
**ページ番号：** 右下・シンプルな数字のみ（1、2、3…）・Text Mutedカラー・font-size 15px
**ブランドフッター：** 左下・「© [ブランド名]」をText Mutedカラー（font-size 13px）で表示
**背景アクセント：** なし（コンテンツスライドはクリーンな白背景）
**縦バー（セクション区切りスライド専用）：** スライド左端に固定配置。Primaryカラー・幅32px・高さ280px・縦方向の中央よりやや上（top: 270px）

```yaml
slide_frame:
  title_area:
    position: "top-left"
    text_align: "left"
    decoration: "bottom-border"
    height: "76px"
    background: "#F4F4F4"
    border_bottom: "1px solid rgba(0,0,0,0.08)"
  page_number:
    position: "bottom-right"
    format: "1"
    style: "solid"
    color: "#9AA0A6"
    font: "body"
    font_size: "15px"
  brand_footer:
    position: "bottom-left"
    content: "© ブランド名"
    color: "#9AA0A6"
    font_size: "13px"
  background_accent:
    type: "none"
  section_bar:
    style: "solid"
    color: "#01B8C8"
    width: "32px"
    height: "280px"
    top: "270px"
    left: "0"
```

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード（グラデーション型）：** border-radius: 12px・グラデーション背景（gradient-main）・白テキスト。数値強調・サービス区分カード等に使用。
**カード（ボーダー型）：** border-radius: 8px・背景 #F7F9FA・border 1px solid rgba(0,0,0,0.08)・shadow なし。テーブル・リスト等の区画に使用。
**テーブルヘッダー：** Primaryカラー背景・白テキスト・Bold。比較列（前年比・YoY等）はダークグレー（#404040）背景。
**箇条書きマーカー：** ・（中黒）または Primaryカラーの四角ドット（4px × 4px）
**番号スタイル：** テキストのみ（数字を Primaryカラーで表示）

```yaml
component_style:
  card_gradient:
    border_radius: "12px"
    background: "gradient-main"
    color: "#FFFFFF"
  card_border:
    border_radius: "8px"
    background: "#F7F9FA"
    border: "1px solid rgba(0,0,0,0.08)"
    shadow: "none"
  table_header:
    primary_col: "background #01B8C8, color #FFFFFF, font-weight 700"
    compare_col: "background #404040, color #FFFFFF, font-weight 700"
  bullet:
    color: "#01B8C8"
    shape: "square-dot"
  number:
    style: "text-only"
    color: "#01B8C8"
```

## Do / Don't

**Do（やること）**
- 重要な数値・KPIは Primaryカラー（`#01B8C8`）で色付けして強調する
- テーブルヘッダー・グラフのアクセントカラーを一貫して Primaryカラーで統一する
- 1スライド1メッセージに絞り、シンプルな構成を保つ
- ヘッダー帯・ロゴ・フッターを全スライドで統一する

**Don't（やってはいけないこと）**
- 青・ティール系以外の派手なカラーや複雑な装飾を追加しない
- 本文テキストに太字・下線を乱用しない（強調はカラーで行う）
- スライド内のテキスト量を詰め込みすぎない（1スライドあたり150字以内を目安に）
- カードの背景に白（#FFFFFF）を直接使わない（surface-card 相当の色を使う）
