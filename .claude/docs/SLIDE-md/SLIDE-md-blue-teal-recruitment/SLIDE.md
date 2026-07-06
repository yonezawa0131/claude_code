# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** AIテックスタートアップ向けコーポレートリクルートデッキ
**マッチするシーン：** 採用・企業紹介プレゼン、スタートアップのカンファレンス発表、コーポレートブランディング。ウルトラミニマルで余白を活かした清潔感のある設計。

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ブルー | #167DE4 |
| Secondary | ティール/シアン | #14BECE |
| Background | クールホワイト | #F7F8FA |
| Accent | ラベンダー | #7278FF |
| Text | チャコール | #2E3133 |
| Text Sub | ミディアムグレー | #5C6266 |
| Text Muted | ライトグレー | #838789 |

**グラデーション：** Mint(#9FEDF5) → Blue(#7FC5FF) → Lavender(#7278FF)・135deg（斜め）および180deg（縦）。スライド上では放射状グラデーションの「Blob」として背景装飾に使用する。

    colors:
      primary: "#167DE4"
      secondary: "#14BECE"
      background: "#F7F8FA"
      accent: "#7278FF"
      text: "#2E3133"
      text_sub: "#5C6266"
      text_muted: "#838789"
      gradient_main: "linear-gradient(135deg, #9FEDF5, #7FC5FF, #7278FF)"
      gradient_vert: "linear-gradient(180deg, #9FEDF5, #7FC5FF, #7278FF)"

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Inter, Noto Sans JP | 96px | 800 |
| 見出し（H2） | Inter, Noto Sans JP | 56px | 700 |
| 本文 | Inter, Noto Sans JP | 18px | 400 |
| キャプション | Inter, Noto Sans JP | 13px | 400 |
| モノスペース | なし | - | - |

    typography:
      heading_h1:
        font: "Inter, 'Noto Sans JP', system-ui, sans-serif"
        size: "96px"
        weight: "800"
      heading_h2:
        font: "Inter, 'Noto Sans JP', system-ui, sans-serif"
        size: "56px"
        weight: "700"
      body:
        font: "Inter, 'Noto Sans JP', system-ui, sans-serif"
        size: "18px"
        weight: "400"
      caption:
        font: "Inter, 'Noto Sans JP', system-ui, sans-serif"
        size: "13px"
        weight: "400"
      mono:
        font: "なし"
        usage: "なし"

## Layout

- **スライドサイズ：** 16:9（幅1920px × 高さ1080px）
- **余白（上下）：** 上60px・下40px
- **余白（左右）：** 100px
- **テキスト整列：** 左寄せ（表紙スライドのみ中央寄せ）

    layout:
      slide_size: "16:9"
      width: "1920px"
      height: "1080px"
      padding_vertical: "60px"
      padding_horizontal: "100px"
      text_align: "left"

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部左寄せ、ごく小さいセクションブレッドクラムテキスト（13px、ラベングレー、letterSpacing: 0.05em）。装飾なし。例：「01  Z E N K I G E N と は」形式の広いトラッキング
**ページ番号：** なし
**ページ番号スタイル：** -
**ブランドフッター：** 右下・「© サンプル株式会社」形式・Text Mutedカラー・13px
**背景アクセント：** 放射状グラデーションBlob（Mint/Teal/Blue/Lavenderの組み合わせ）を2〜3個、スライド端に overflow:hidden で配置。透明度60〜80%のソフトな発光感。主に左上・右上・右中に配置。
**縦バー：** なし

    slide_frame:
      title_area:
        position: "top-left"
        text_align: "left"
        decoration: "none"
      page_number:
        position: "none"
        format: "-"
        style: "-"
        font: "-"
      brand_footer:
        position: "bottom-right"
        content: "© [ブランド名]"
      background_accent:
        type: "radial-gradient-circle"
        placement: "left-top, right-top, right-center"
        color: "Mint(#9FEDF5)・Blue(#7FC5FF)・Lavender(#7278FF)の放射状blob、各opacity 0.6〜0.8"
      section_bar:
        style: "none"
        width: "-"

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** border-radius: 14px、非常に薄い影（box-shadow: 0 1px 3px rgba(0,0,0,0.06)）、border: 1px solid rgba(0,0,0,0.06)。背景は白またはBackground色。
**箇条書きマーカー：** テキストのみ（・ または — などの最小限の記号）または非表示
**番号スタイル：** テキストのみ（例：01、02、03 形式）
**チップ/タグ：** Primary（#167DE4）背景に白テキスト、border-radius: 4px、font-weight: 700、font-size: 14px

    component_style:
      card:
        border_radius: "14px"
        shadow: "0 1px 3px rgba(0,0,0,0.06)"
        border: "1px solid rgba(0,0,0,0.06)"
      bullet:
        color: "text_muted"
        shape: "minimal（テキスト記号）"
      number:
        style: "text-only"
        color: "text_sub"

## Do / Don't

**Do（やること）**
- 白・クールホワイトの余白を大胆に使い、コンテンツを「呼吸」させる
- 背景Blobグラデーションをスライドごとに配置する（全スライドの統一感の源）
- 見出しは短く・大きく・太く（情報量を絞って、1スライド1メッセージ）
- セクション見出しには広いletter-spacing（0.05〜0.15em）を使う

**Don't（やってはいけないこと）**
- 原色・高彩度の単色をベタ塗りで使わない（Blobグラデーションの繊細さを損なう）
- カードに濃い影や濃いボーダーを使わない（ウルトラミニマルな雰囲気を壊す）
- 1スライドにテキストを詰め込まない（余白がこのデザインの本質）
- 太字・大きなフォントを過剰に使わない（コントラストが薄れる）
