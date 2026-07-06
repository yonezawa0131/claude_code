# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** Anthropic 公式サイト（https://www.anthropic.com/）
**マッチするシーン：** AI・テクノロジー系カンファレンス、投資家向けプレゼン、製品紹介、研究発表。ウォームトーンのミニマルデザインで信頼感と先進性を両立するフォーマルな資料全般。

## Colors

### ブランドカラー・テキスト・ボーダー

| 役割 | トークン名 | HEXコード |
|---|---|---|
| Primary | primary | #cc785c |
| Primary Active | primary-active | #a9583e |
| Primary Disabled | primary-disabled | #e6dfd8 |
| Text（インク） | ink | #141413 |
| Text Body | body | #3d3d3a |
| Text Body Strong | body-strong | #252523 |
| Text Muted | muted | #6c6a64 |
| Text Muted Soft | muted-soft | #8e8b82 |
| Border | hairline | #e6dfd8 |
| Border Soft | hairline-soft | #ebe6df |

### サーフェスカラー

| 役割 | トークン名 | HEXコード |
|---|---|---|
| Background（キャンバス） | canvas | #faf9f5 |
| Surface Soft | surface-soft | #f5f0e8 |
| Surface Card | surface-card | #efe9de |
| Surface Cream Strong | surface-cream-strong | #e8e0d2 |
| Surface Dark | surface-dark | #181715 |
| Surface Dark Elevated | surface-dark-elevated | #252320 |
| Surface Dark Soft | surface-dark-soft | #1f1e1b |
| On Primary | on-primary | #ffffff |
| On Dark | on-dark | #faf9f5 |
| On Dark Soft | on-dark-soft | #a09d96 |

### アクセント・ステータスカラー

| 役割 | トークン名 | HEXコード |
|---|---|---|
| Accent Teal | accent-teal | #5db8a6 |
| Accent Amber | accent-amber | #e8a55a |
| Success | success | #5db872 |
| Warning | warning | #d4a017 |
| Error | error | #c64545 |

**グラデーション：** なし（フラットカラーが基調。Primaryカラーをポイントとして使う）

```yaml
colors:
  primary: "#cc785c"
  primary_active: "#a9583e"
  primary_disabled: "#e6dfd8"
  ink: "#141413"
  body: "#3d3d3a"
  body_strong: "#252523"
  muted: "#6c6a64"
  muted_soft: "#8e8b82"
  hairline: "#e6dfd8"
  hairline_soft: "#ebe6df"
  canvas: "#faf9f5"
  surface_soft: "#f5f0e8"
  surface_card: "#efe9de"
  surface_cream_strong: "#e8e0d2"
  surface_dark: "#181715"
  surface_dark_elevated: "#252320"
  surface_dark_soft: "#1f1e1b"
  on_primary: "#ffffff"
  on_dark: "#faf9f5"
  on_dark_soft: "#a09d96"
  accent_teal: "#5db8a6"
  accent_amber: "#e8a55a"
  success: "#5db872"
  warning: "#d4a017"
  error: "#c64545"
  gradient_main: "なし"
  gradient_vert: "なし"
```

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Plus Jakarta Sans | 80px | 800 |
| 見出し（H2） | Plus Jakarta Sans | 54px | 700 |
| 本文 | DM Sans | 20px | 400 |
| キャプション | DM Sans | 13px | 500 |
| モノスペース | DM Mono | - | 700 |

```yaml
typography:
  heading_h1:
    font: "Plus Jakarta Sans"
    size: "80px"
    weight: "800"
  heading_h2:
    font: "Plus Jakarta Sans"
    size: "54px"
    weight: "700"
  body:
    font: "DM Sans"
    size: "20px"
    weight: "400"
  caption:
    font: "DM Sans"
    size: "13px"
    weight: "500"
  mono:
    font: "DM Mono"
    usage: "ページ番号・数値・データラベル"
```

## Layout

- **スライドサイズ：** 16:9（幅1920px × 高さ1080px）
- **余白（上下）：** 80px
- **余白（左右）：** 120px
- **テキスト整列：** 左寄せ

```yaml
layout:
  slide_size: "16:9"
  width: "1920px"
  height: "1080px"
  padding_vertical: "80px"
  padding_horizontal: "120px"
  text_align: "left"
```

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-*.md はコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。

**タイトルエリア：** 上部左寄せ、装飾なし（余白のみで区切る）
**ページ番号：** 右下・「01 / 6」形式・Primaryカラー（#cc785c）でページ数を表示、DM Mono使用
**ページ番号スタイル：** 単色テキスト（Primaryカラー）、モノスペースフォント使用
**ブランドフッター：** 左下・「ANTHROPIC」をMutedカラー（#6c6a64）で表示
**背景アクセント：** なし（ミニマルデザインのため装飾なし）
**縦バー：** なし（Anthropicデザインは装飾を最小限に抑える）

```yaml
slide_frame:
  title_area:
    position: "top-left"
    text_align: "left"
    decoration: "none"
  page_number:
    position: "bottom-right"
    format: "01 / 6"
    style: "solid"
    color: "#cc785c"
    font: "mono"
  brand_footer:
    position: "bottom-left"
    content: "ANTHROPIC"
    color: "#6c6a64"
  background_accent:
    type: "none"
  section_bar:
    style: "none"
```

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** border-radius: 12px、border: 1px solid #e6dfd8（hairline）、背景は surface-card（#efe9de）、影は極めて控えめ
**箇条書きマーカー：** Primaryカラー（#cc785c）の単色丸ドット
**番号スタイル：** Primaryカラーの塗りつぶし円に白数字（シンプル・単色）

```yaml
component_style:
  card:
    border_radius: "12px"
    background: "#efe9de"
    shadow: "0 1px 2px rgba(0,0,0,0.04),0 2px 8px rgba(0,0,0,0.03)"
    border: "1px solid #e6dfd8"
  bullet:
    color: "primary"
    shape: "circle"
  number:
    style: "solid-circle"
    color: "#cc785c"
```

## Do / Don't

**Do（やること）**
- 1スライド1メッセージを徹底し、余白を広くとる
- Primary（テラコッタ #cc785c）はアクセントとして絞って使う
- 見出しは大きく・力強く表示し、視覚的なヒエラルキーを明確にする
- ウォームトーン（オフホワイト・テラコッタ・ウォームグレー）のパレットを守る
- 純粋な黒は避け、ウォームブラック（#141413）を使う

**Don't（やってはいけないこと）**
- 派手なグラデーションや原色・蛍光色を使わない
- 背景に模様・パターン・過剰な装飾を置かない
- 1スライドに情報を詰め込みすぎない
- 複数のフォントファミリーを混在させない
