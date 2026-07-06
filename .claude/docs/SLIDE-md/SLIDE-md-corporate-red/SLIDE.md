# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 日本国内上場企業のIR決算説明資料（DX・AIインテグレーション企業、コーポレートレッド × モノクロ・クリーンデザイン）
**マッチするシーン：** 決算説明会・IR資料・DX提案書・テクノロジー企業向けプレゼンテーション・コーポレートレポート

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | コーポレートレッド | #CC0000 |
| Secondary | ニアブラック | #1A1A1A |
| Background | ホワイト | #FFFFFF |
| Accent | コーポレートレッド | #CC0000 |
| Text | ニアブラック | #1A1A1A |
| Text Sub | ミディアムグレー | #555555 |
| Text Muted | ライトグレー | #888888 |

**グラデーション：** Primary (#CC0000) → Primary Light (#FF6060)・90deg（横）および 180deg（縦）— 背景装飾の円形要素・装飾的な強調要素に限定使用

    colors:
      primary: "#CC0000"
      secondary: "#1A1A1A"
      background: "#FFFFFF"
      accent: "#CC0000"
      text: "#1A1A1A"
      text_sub: "#555555"
      text_muted: "#888888"
      gradient_main: "linear-gradient(90deg, #CC0000, #FF6060)"
      gradient_vert: "linear-gradient(180deg, #CC0000, #FF6060)"

### カラー拡張（デザインシステム内で使用するトーン）

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary Light | ライトレッド | #FF6060 |
| Primary Soft | ソフトピンク | #FFCCCC |
| Surface | ライトグレー | #F5F5F5 |
| Header BG | ヘッダーバー背景 | #F2F2F2 |
| Border | ボーダー | rgba(0,0,0,0.10) |

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 64px | 700 |
| 見出し（H2） | Noto Sans JP | 40px | 700 |
| 本文 | Noto Sans JP | 20px | 400 |
| キャプション | Noto Sans JP | 13px | 400 |
| モノスペース | なし | - | - |

    typography:
      heading_h1:
        font: "Noto Sans JP"
        size: "64px"
        weight: "700"
      heading_h2:
        font: "Noto Sans JP"
        size: "40px"
        weight: "700"
      body:
        font: "Noto Sans JP"
        size: "20px"
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
- **余白（上下）：** 64px
- **余白（左右）：** 88px（左端8pxの赤バーを除いた実効余白）
- **テキスト整列：** 左寄せ

    layout:
      slide_size: "16:9"
      width: "1920px"
      height: "1080px"
      padding_vertical: "64px"
      padding_horizontal: "88px"
      text_align: "left"

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア（コンテンツページ）：** スライド上端に高さ52pxのグレーバー（#F2F2F2）を配置。左に「セクション名 ｜ サブセクション名」をグレーテキストで表示。右端にロゴ。
**タイトルエリア（表紙・セクション区切り）：** グレーバーなし。ロゴは表紙では左上、区切りページでは省略。
**ページ番号：** 右下・数字のみ・Text Mutedカラー（#888888）。表紙・セクション区切りページには表示なし。
**ブランドフッター：** なし。
**背景アクセント：** 表紙・セクション区切りページのみ、右側に淡いブルーグレーのぼかしテクスチャ（CSS radial-gradient で近似）。コンテンツページは白無地。
**縦バー：** 全スライド左端にフル高さのレッド縦バー（幅8px・Primary #CC0000・単色）。

    slide_frame:
      title_area:
        position: "top（グレーバー52px）/ 表紙はロゴのみ"
        text_align: "left"
        decoration: "gray-header-bar（コンテンツページ） / none（表紙・区切り）"
      page_number:
        position: "bottom-right"
        format: "1"
        style: "solid"
        font: "body"
        color: "#888888"
        display: "コンテンツページのみ"
      brand_footer:
        position: "none"
        content: "なし"
      background_accent:
        type: "radial-gradient-blur（表紙・区切りページのみ）"
        placement: "right-side"
        color: "rgba(195,200,215,0.65) / 淡いブルーグレー"
      section_bar:
        style: "solid"
        color: "#CC0000"
        width: "8px"
        height: "full-height（全スライド左端）"

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** border-radius: 14px、薄い影あり、border: 1px solid rgba(0,0,0,0.10)。背景は #F5F5F5（Surface）またはレッド（Primary）。
**ピル型ラベル：** border-radius: 999px。3種類のスタイルを使い分ける：赤背景（白文字）・ダーク背景（白文字）・ライトピンク背景（赤文字）。
**箇条書きマーカー：** なし（このデザインはダイアグラム主体で箇条書きドットを使わない）。
**番号スタイル：** テキストのみ（太字・Primaryカラー・大きなフォントサイズ）。

    component_style:
      card:
        border_radius: "14px"
        shadow: "0 1px 3px rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)"
        border: "1px solid rgba(0,0,0,0.10)"
        backgrounds: "Surface #F5F5F5 / Primary #CC0000 / Secondary #1A1A1A"
      pill:
        border_radius: "999px"
        variants: "red（#CC0000 bg, #fff text） / dark（#1A1A1A bg, #fff text） / light（#FFE8E8 bg, #CC0000 text）"
      bullet:
        color: "なし（ダイアグラム主体）"
        shape: "なし"
      number:
        style: "text-only"
        color: "Primary #CC0000"
        weight: "900"

## Do / Don't

**Do（やること）**
- レッド・ダーク・ホワイトの3色パレットを一貫して守る
- 重要メッセージは大きく太いフォントで表示し、視認性を最優先する
- 左端8pxのレッドバーで全スライドの統一感と緊張感を作る
- ダイアグラム・フロー図・ピル型ラベルで複雑な概念を視覚化する

**Don't（やってはいけないこと）**
- 3色パレット以外の明るい色（ブルー・グリーン・イエロー等）を追加しない
- コンテンツページに背景テクスチャや装飾を置かない（表紙・区切りページのみ）
- テキストだけのスライドを作らない（必ず視覚要素を加える）
- 角丸を20px以上にしない（フォーマルさを保つ）
