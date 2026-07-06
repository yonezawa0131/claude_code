# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** AIプロダクト系デザインシステム（トリコロール・グラデーション型）
**マッチするシーン：** AI系カンファレンス・テクノロジー系プレゼン・社内の技術共有・プロダクト紹介

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ブルー | #4285F4 |
| Secondary | パープル | #9168C0 |
| Background | ほぼ白（青みがかった） | #F8FAFD |
| Accent | ピンク/レッド | #D96570 |
| Text | ほぼ黒 | #1F1F1F |
| Text Sub | 濃いグレー | #444746 |
| Text Muted | グレー | #5E5E5E |

**拡張カラー（参考）**

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Surface Card | 薄いブルーグレー | #F0F4F9 |
| Surface Soft | 極薄ブルーグレー | #EAF1FE |
| Border / Hairline | ライトグレー | #DADCE0 |
| On Muted | ミディアムグレー | #9AA0A6 |
| Success | グリーン | #34A853 |
| Error | レッド | #EA4335 |

**グラデーション：** Primary → Secondary → Accent・90deg（横）/ 135deg（斜め）/ 180deg（縦）

```yaml
colors:
  primary: "#4285F4"
  secondary: "#9168C0"
  background: "#F8FAFD"
  accent: "#D96570"
  text: "#1F1F1F"
  text_sub: "#444746"
  text_muted: "#5E5E5E"
  surface_card: "#F0F4F9"
  surface_soft: "#EAF1FE"
  border: "#DADCE0"
  on_muted: "#9AA0A6"
  success: "#34A853"
  error: "#EA4335"
  gradient_main: "linear-gradient(90deg, #4285F4, #9168C0, #D96570)"
  gradient_diag: "linear-gradient(135deg, #4285F4 0%, #9168C0 50%, #D96570 100%)"
  gradient_vert: "linear-gradient(180deg, #4285F4, #9168C0, #D96570)"
```

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Manrope | 54〜96px | 800 |
| 見出し（H2） | Manrope | 28〜38px | 700〜800 |
| 本文 | Manrope | 18〜22px | 400〜500 |
| キャプション | Manrope | 12〜13px | 500 |
| モノスペース | Roboto Mono | 12〜19px | 700 |

```yaml
typography:
  heading_h1:
    font: "Manrope"
    size: "54〜96px"
    weight: "800"
  heading_h2:
    font: "Manrope"
    size: "28〜38px"
    weight: "700"
  body:
    font: "Manrope"
    size: "18〜22px"
    weight: "400"
  caption:
    font: "Manrope"
    size: "12〜13px"
    weight: "500"
  mono:
    font: "Roboto Mono"
    usage: "ページ番号・数値・データ表示"
```

## Layout

- **スライドサイズ：** 16:9（幅1920px × 高さ1080px）
- **余白（上下）：** 96px
- **余白（左右）：** 140px
- **テキスト整列：** 左寄せ

```yaml
layout:
  slide_size: "16:9"
  width: "1920px"
  height: "1080px"
  padding_vertical: "96px"
  padding_horizontal: "140px"
  text_align: "left"
```

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部左寄せ。見出し左側にグラデーション縦バー（Primary→Secondary→Accent）を配置
**ページ番号：** 右下・「01 / 6」形式・グラデーションテキスト・Roboto Monoフォント使用
**ページ番号スタイル：** グラデーションテキスト（Primary→Secondary→Accent）・Roboto Mono使用
**ブランドフッター：** 左下・デザインシステム名をText Mutedカラー（#9AA0A6）で表示
**背景アクセント：** 右上にSecondaryカラー12〜16%透明の半透明グラデーション円・左下にPrimaryカラー8〜13%透明の半透明グラデーション円
**縦バー：** 見出し左側にグラデーション縦バーあり・幅8px × 高さ40px・Primary→Secondary→Accent

```yaml
slide_frame:
  title_area:
    position: "top-left"
    text_align: "left"
    decoration: "gradient-vertical-bar"
  page_number:
    position: "bottom-right"
    format: "01 / 6"
    style: "gradient-text"
    font: "mono"
  brand_footer:
    position: "bottom-left"
    content: "デザインシステム名"
  background_accent:
    type: "radial-gradient-circle"
    placement: "right-top, left-bottom"
    color: "Secondary 12〜16%透明, Primary 8〜13%透明"
  section_bar:
    style: "gradient-vertical"
    color: "Primary → Secondary → Accent"
    width: "8px"
    height: "40px"
```

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** border-radius: 22px・薄い影（0 1px 2px rgba(60,64,67,0.06), 0 2px 7px rgba(60,64,67,0.04)）・border: 1px solid #DADCE0。背景はSurface Card（#F0F4F9）
**箇条書きマーカー：** Primary / Secondary / Accentの3色丸ドット（色を交互に使用）
**番号スタイル：** グラデーション円（Primary→Secondary→Accent）に白数字

```yaml
component_style:
  card:
    border_radius: "22px"
    shadow: "0 1px 2px rgba(60,64,67,0.06),0 2px 7px rgba(60,64,67,0.04)"
    border: "1px solid #DADCE0"
    background: "#F0F4F9"
  bullet:
    color: "Primary / Secondary / Accent（3色交互）"
    shape: "circle"
  number:
    style: "gradient-circle"
    color: "gradient-main（Primary→Secondary→Accent）"
```

## Do / Don't

**Do（やること）**
- グラデーション（Primary→Secondary→Accent）を見出し・ボタン・縦バー・ページ番号など要所に使う
- 見出し左に縦バーを置き、階層と視認性を明確にする
- フォントはManrope一本に統一し、数値・コードのみRoboto Monoを使い分ける
- 背景アクセント円は控えめな透明度（8〜16%）に保ち、コンテンツの邪魔をしない

**Don't（やってはいけないこと）**
- グラデーションをすべての要素に適用しない（過剰な派手さを避ける）
- 白（#FFFFFF）をカード背景に直接使わない（Surface Card #F0F4F9 を使う）
- セリフ体フォントや細いウェイト（300以下）は使わない
- テキスト色にPrimary/Secondaryなど彩度の高い色を使わない（Text #1F1F1F を基本とする）
