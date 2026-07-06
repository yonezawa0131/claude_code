# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 官公庁・行政機関スタイルの年次報告スライド（ネイビー基調のフォーマルスタイル）
**マッチするシーン：** 行政・官公庁の公式報告、企業の年次報告・IR資料、データを重視したフォーマルなビジネスプレゼンテーション

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ネイビーブルー | #0017b6 |
| Secondary | ミディアムブルー | #505cff |
| Background | ホワイト | #ffffff |
| Accent | ライトブルー | #9bb9f8 |
| Text | ネイビー | #0017b6 |
| Text Sub | ミディアムブルー | #505cff |
| Text Muted | グレー | #757575 |

**グラデーション：** なし（フラットデザイン）

    colors:
      primary: "#0017b6"
      secondary: "#505cff"
      background: "#ffffff"
      accent: "#9bb9f8"
      text: "#0017b6"
      text_sub: "#505cff"
      text_muted: "#757575"
      background_section: "#0017b6"
      background_light: "#e0e9fc"
      gradient_main: "なし"
      gradient_vert: "なし"

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 60px | Bold (700) |
| 見出し（H2） | Noto Sans JP | 32px | Bold (700) |
| 本文 | Noto Sans JP | 18px | Regular (400) |
| キャプション | Noto Sans JP | 13px | Regular (400) |
| データ数値 | Noto Sans JP | 72px | Bold (700) |
| モノスペース | なし | - | - |

    typography:
      heading_h1:
        font: "Noto Sans JP"
        size: "60px"
        weight: "700"
      heading_h2:
        font: "Noto Sans JP"
        size: "32px"
        weight: "700"
      body:
        font: "Noto Sans JP"
        size: "18px"
        weight: "400"
      caption:
        font: "Noto Sans JP"
        size: "13px"
        weight: "400"
      data_value:
        font: "Noto Sans JP"
        size: "72px"
        weight: "700"
      mono:
        font: "なし"
        usage: "なし"

## Layout

- **スライドサイズ：** 16:9（幅1920px × 高さ1080px）
- **余白（上下）：** 100px
- **余白（左右）：** 106px
- **テキスト整列：** 左寄せ

    layout:
      slide_size: "16:9"
      width: "1920px"
      height: "1080px"
      padding_vertical: "100px"
      padding_horizontal: "106px"
      text_align: "left"

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部左寄せ。タイトルテキストの直下にPrimaryカラー（#0017b6）の水平下線（高さ2px）を配置する
**ページ番号：** なし
**ブランドフッター：** なし
**背景アクセント：** なし（フラットデザイン）
**縦バー：** なし（アンダーラインで見出しを装飾する）

**セクションページ：** Primaryカラー（#0017b6）の背景に白テキストを中央寄せで配置する特別なページタイプ

    slide_frame:
      title_area:
        position: "top-left"
        text_align: "left"
        decoration: "underline"
        underline_color: "#0017b6"
        underline_height: "2px"
      page_number:
        position: "none"
        format: "なし"
        style: "なし"
        font: "なし"
      brand_footer:
        position: "none"
        content: "なし"
      background_accent:
        type: "none"
        placement: "none"
        color: "なし"
      section_bar:
        style: "none"
        width: "-"
      section_page:
        background: "#0017b6"
        text_color: "#ffffff"
        text_align: "center"

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** 白背景・角丸なし〜小（border-radius: 4px）・枠線なし・影なし。シンプルなフラットスタイル
**データカラーバー：** ネイビー（#0017b6）・ミディアムブルー（#505cff）・ライトブルー（#9bb9f8）の矩形バーでデータを表示
**テーブル行：** 奇数行は#e0e9fc（ライトブルー）、偶数行は白のシマウマ模様

    component_style:
      card:
        border_radius: "4px"
        shadow: "none"
        border: "none"
      data_bar:
        colors: "#0017b6, #505cff, #9bb9f8, #c5d6fa"
        style: "flat-rectangle"
      table:
        odd_row: "#e0e9fc"
        even_row: "#ffffff"
        header_bg: "#0017b6"
        header_text: "#ffffff"
      bullet:
        color: "#0017b6"
        shape: "none"
      number:
        style: "text-only"
        color: "#0017b6"

## Do / Don't

**Do（やること）**
- ネイビー（#0017b6）を基調として、全ページで統一感を保つ
- データや数値は大きく（48px以上）目立たせ、情報の重点を明確にする
- 白背景・フラットデザインでシンプルに仕上げ、情報密度を高める
- セクション区切りにはネイビー背景の全面カラーページを使い、メリハリをつける

**Don't（やってはいけないこと）**
- グラデーションや鮮やかな装飾色を使う（フォーマルな雰囲気が損なわれる）
- 影や3D効果などの装飾的要素を追加する
- フォントサイズを細かく変えすぎる（H1・H2・本文の3段階で統一する）
- テキストの中央寄せをメインコンテンツページで使う（セクションページ以外は左寄せ）
