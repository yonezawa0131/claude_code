# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 緑・青を基調としたビジネス向けプレゼンテーションデザイン（人材・採用業界向け営業・提案資料）
**マッチするシーン：** 顧客向けサービス提案、営業資料、BtoBビジネスのプレゼンテーション、フォーマルな社外向け発表資料

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ティールグリーン | #2BB5A0 |
| Secondary | スチールブルー | #3D9BC8 |
| Background | ホワイト | #FFFFFF |
| Accent | ディープティール | #17A899 |
| Text | ダークネイビー | #1A1A2E |
| Text Sub | ネイビーグレー | #2A2A45 |
| Text Muted | ブルーグレー | #6B6B8A |

**グラデーション：** Primary → Secondary・90deg（横）、Primary → Secondary・180deg（縦）

    colors:
      primary: "#2BB5A0"
      secondary: "#3D9BC8"
      background: "#FFFFFF"
      accent: "#17A899"
      text: "#1A1A2E"
      text_sub: "#2A2A45"
      text_muted: "#6B6B8A"
      light_card: "#E8F7F5"
      gradient_main: "linear-gradient(90deg, #2BB5A0, #3D9BC8)"
      gradient_vert: "linear-gradient(180deg, #2BB5A0, #3D9BC8)"

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1）（Display） | Noto Sans JP | 80px | Bold |
| 見出し（H2）（Display） | Noto Sans JP | 48px | Bold |
| 本文（Body） | Noto Sans JP | 20px | Regular |
| キャプション | Noto Sans JP | 14px | Regular |
| モノスペース（Mono） | なし | - | - |

    typography:
      heading_h1:
        font: "Noto Sans JP"
        size: "80px"
        weight: "700"
      heading_h2:
        font: "Noto Sans JP"
        size: "48px"
        weight: "700"
      body:
        font: "Noto Sans JP"
        size: "20px"
        weight: "400"
      caption:
        font: "Noto Sans JP"
        size: "14px"
        weight: "400"
      mono:
        font: "なし"
        usage: "なし"

## Layout

- **スライドサイズ：** 16:9（幅1920px × 高さ1080px）
- **余白（上下）：** 80px
- **余白（左右）：** 120px
- **テキスト整列：** 左寄せ

    layout:
      slide_size: "16:9"
      width: "1920px"
      height: "1080px"
      padding_vertical: "80px"
      padding_horizontal: "120px"
      text_align: "left"

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部左寄せ。スライドタイトルの左に幅6px・タイトルと同じ高さのティールグリーン（#2BB5A0）縦アクセントバーを配置。サブタイトル（例：セクション番号や補足）はアクセントカラー（#17A899）で表示。
**ページ番号：** なし
**ページ番号スタイル：** なし
**ブランドフッター：** なし
**背景アクセント：** なし（白背景のシンプルデザイン。下部全幅グラデーションバーが主要装飾）
**縦バー：** あり（単色 #2BB5A0、幅6px）。タイトル左側に配置。

    slide_frame:
      title_area:
        position: "top-left"
        text_align: "left"
        decoration: "accent-bar"
        accent_bar:
          width: "6px"
          color: "#2BB5A0"
      page_number:
        position: "none"
        format: "none"
        style: "none"
        font: "none"
      brand_footer:
        position: "none"
        content: "なし"
      background_accent:
        type: "none"
        note: "下部全幅グラデーションバー（#2BB5A0 → #3D9BC8、高さ36px）を全ページ配置"
      section_bar:
        style: "solid"
        color: "#2BB5A0"
        width: "6px"

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** 薄いティール背景（#E8F7F5）または白背景・border-radius: 8px・影なし
**箇条書きマーカー：** Primaryカラー（#2BB5A0）の単色丸ドット
**番号スタイル：** Primaryカラー（#2BB5A0）の塗りつぶし円に白数字

    component_style:
      card:
        border_radius: "8px"
        shadow: "none"
        border: "none"
        background: "#E8F7F5"
      bullet:
        color: "Primary"
        shape: "circle"
      number:
        style: "solid-circle"
        color: "#2BB5A0"

## Do / Don't

**Do（やること）**
- ティールグリーン（#2BB5A0）とスチールブルー（#3D9BC8）のグラデーションで統一感を出す
- タイトル左のアクセントバーを必ず配置し、セクションの区切りを明確にする
- 強調ポイントはティールカラーのバッジ・枠・太字で視覚的に際立たせる
- 1スライドに1メインメッセージを配置し、見出し文でそのスライドの結論を伝える
- カードやボックスは薄いティール（#E8F7F5）またはホワイトで統一する

**Don't（やってはいけないこと）**
- 赤・オレンジ・紫など、ティール系と相反する派手な原色を使わない
- 下部グラデーションバーを省略したり変色させない
- テキストを詰め込みすぎず、1スライドあたりの箇条書きは5項目以内に抑える
- 背景に柄・テクスチャ・写真を使用しない（白背景を維持する）
