# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 青・シンプル・グラフ・図解のプレゼンテーション（日本語プレゼンテーション）
**マッチするシーン：** 教育・研修資料、ビジネス発表・提案資料、グラフや図解を多用した情報整理型プレゼン

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | スカイブルー | #29ABE2 |
| Secondary | ライトブルー | #A8DCF0 |
| Background | 白 | #FFFFFF |
| Accent | ほぼ黒 | #111111 |
| Text | ほぼ黒（本文） | #1A1A1A |
| Text Sub | ダークグレー | #2D2D2D |
| Text Muted | ミディアムグレー | #6B6B6B |

**グラデーション：** Primary → Secondary・90deg（横）、Primary → Secondary・180deg（縦）

    colors:
      primary: "#29ABE2"
      secondary: "#A8DCF0"
      background: "#FFFFFF"
      accent: "#111111"
      text: "#1A1A1A"
      text_sub: "#2D2D2D"
      text_muted: "#6B6B6B"
      gradient_main: "linear-gradient(90deg, #29ABE2, #A8DCF0)"
      gradient_vert: "linear-gradient(180deg, #29ABE2, #A8DCF0)"

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1）（Display） | Noto Sans JP | 80px | Bold |
| 見出し（H2）（Display） | Noto Sans JP | 42px | Bold |
| 本文（Body） | Noto Sans JP | 18px | Regular |
| キャプション | Noto Sans JP | 13px | Regular |
| モノスペース（Mono） | なし | - | - |

    typography:
      heading_h1:
        font: "Noto Sans JP"
        size: "80px"
        weight: "700"
      heading_h2:
        font: "Noto Sans JP"
        size: "42px"
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

## Layout

- **スライドサイズ：** 16:9（幅1920px × 高さ1080px）
- **余白（上下）：** 80px
- **余白（左右）：** 100px
- **テキスト整列：** セクションタイトルは中央寄せ、本文は左寄せ

    layout:
      slide_size: "16:9"
      width: "1920px"
      height: "1080px"
      padding_vertical: "80px"
      padding_horizontal: "100px"
      text_align: "left"

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部中央配置。点線（`·····`）で両側を挟んだブラケット形式で表示。例：`·············· [ グラフと図の効果的な使用法 ] ··············`。コンテンツパネルの外側・上部に配置し、パネル内には含めない。
**ページ番号：** なし
**ページ番号スタイル：** なし
**ブランドフッター：** なし
**背景アクセント：** 左上と右サイドに有機的なウェーブ形状（ブロブ）を Primary（#29ABE2）と Secondary（#A8DCF0）のグラデーションで配置。コンテンツスライドでは白いインナーパネル（border: 1.5px solid #CDD8E3）をブロブの前面に配置する。
**縦バー：** なし

    slide_frame:
      title_area:
        position: "top-center"
        text_align: "center"
        decoration: "dotted-bracket"
        format: "·· [ タイトル ] ··"
      page_number:
        position: "none"
        format: "none"
        style: "none"
        font: "none"
      brand_footer:
        position: "none"
        content: "なし"
      background_accent:
        type: "blob-wave"
        placement: "top-left, right-side"
        color: "Primary（#29ABE2）→ Secondary（#A8DCF0）グラデーション"
      section_bar:
        style: "none"
        width: "-"

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** 白背景インナーパネル・border-radius: 3px・border: 1.5px solid #CDD8E3・padding: 24px 32px
**箇条書きマーカー：** Primaryカラー（#29ABE2）の単色丸ドット
**番号スタイル：** Accentカラー（#111111）の黒丸に白数字

    component_style:
      card:
        border_radius: "3px"
        shadow: "none"
        border: "1.5px solid #CDD8E3"
      bullet:
        color: "Primary"
        shape: "circle"
      number:
        style: "solid-circle"
        color: "#111111"

## Do / Don't

**Do（やること）**
- 左上と右サイドにウェーブ形状のブルーグラデーションブロブ装飾を配置する
- セクションタイトルは `[ タイトル ]` 形式で両側に点線を添え、上部中央に配置する
- コンテンツは白いインナーパネル（細いボーダー付き）の中に整理して表示する
- グラフ・表・アイコンカードなど視覚要素を積極的に活用する
- 数字付き黒丸バッジ（セクション番号）でコンテンツ間の階層を明示する

**Don't（やってはいけないこと）**
- テキストのみのスライドを作らず、必ず図解・グラフ・アイコン等の視覚要素を使う
- ブロブ以外の派手な装飾要素を追加して画面を混雑させない
- 原色や高彩度の色を追加してブルー系の統一感を損なわない
- フォント種類を増やしてタイポグラフィの統一感を壊さない
