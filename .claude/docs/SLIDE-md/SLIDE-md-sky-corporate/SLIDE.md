# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 日本国内上場企業の統合報告書（メディア・コンテンツ・放送持株会社）
**マッチするシーン：** 統合報告書・IR資料・コーポレートレポート・アニュアルレポート・株主向けプレゼンテーション

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | スカイブルー | #3DAED8 |
| Secondary | ディープスカイブルー | #2B8BBD |
| Background | ホワイト | #FFFFFF |
| Accent | スカイブルー | #3DAED8 |
| Text | ほぼブラック | #1A1A1A |
| Text Sub | ダークグレー | #444444 |
| Text Muted | ミディアムグレー | #888888 |

**グラデーション：** なし（コンポーネント用グラデーションは使用しない）。表紙の背景装飾のみ「ラベンダー → スカイブルー → ローズ」の縦方向パステルグラデーションを右端に使用。

    colors:
      primary: "#3DAED8"
      secondary: "#2B8BBD"
      background: "#FFFFFF"
      accent: "#3DAED8"
      text: "#1A1A1A"
      text_sub: "#444444"
      text_muted: "#888888"
      gradient_main: "none"
      gradient_vert: "none"
      cover_gradient: "ラベンダー(#DDD8F0) → スカイブルー(#C8E6F5) → ローズ(#F0D0D8) 縦方向・右端ぼかし"

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 72px | 700 |
| 見出し（H2） | Noto Sans JP | 36px | 700 |
| 本文 | Noto Sans JP | 18px | 400 |
| キャプション | Noto Sans JP | 13px | 400 |
| モノスペース | なし | - | - |

    typography:
      heading_h1:
        font: "Noto Sans JP"
        size: "72px"
        weight: "700"
      heading_h2:
        font: "Noto Sans JP"
        size: "36px"
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
- **余白（上下）：** 72px
- **余白（左右）：** 100px
- **テキスト整列：** 左寄せ

    layout:
      slide_size: "16:9"
      width: "1920px"
      height: "1080px"
      padding_vertical: "72px"
      padding_horizontal: "100px"
      text_align: "left"

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部左寄せ。コンテンツページは左上にセクション名を小さなText Mutedカラーのテキストで配置する。
**ページ番号：** 右下・「01」形式のPrimaryカラーテキスト。フッター文字列の末尾に含める形式（例：「ブランド名 ANNUAL REPORT 2025 | 01」）。
**ページ番号スタイル：** 単色テキスト（Primaryカラー）・本文フォント使用。
**ブランドフッター：** 右下・「ブランド名 ANNUAL REPORT 2025 | XX」の形式で非常に小さく（13px）表示。
**背景アクセント（表紙）：** 右端に縦長パステルグラデーション帯（ラベンダー → スカイブルー → ローズ）を配置し、左側（白側）に向けて自然にぼかす。
**背景アクセント（コンテンツページ）：** 右上隅に薄い水色の斜線ハッチングパターン（細い斜線繰り返し・装飾帯）を配置する。
**縦バー：** なし。

    slide_frame:
      title_area:
        position: "top-left"
        text_align: "left"
        decoration: "section-label"
      page_number:
        position: "bottom-right"
        format: "01"
        style: "solid"
        font: "body"
      brand_footer:
        position: "bottom-right"
        content: "ブランド名 ANNUAL REPORT 2025 | XX"
      background_accent:
        type: "cover-pastel-gradient + content-diagonal-hatching"
        placement: "right-edge（表紙）/ top-right-corner（コンテンツページ）"
        color: "ラベンダー→スカイブルー→ローズ（表紙）/ Primary薄め斜線（コンテンツページ）"
      section_bar:
        style: "none"
        width: "-"

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** border-radius: 4px、影なし、border: 1px solid rgba(61,174,216,0.15)。背景は白またはごく薄いブルーグレー（#F5F8FA）。テーブル形式が主体で、ヘッダー行にはPrimaryカラーの薄いグレー（#EAF5FB）を使用。
**箇条書きマーカー：** Primaryカラー単色の丸ドット。
**番号スタイル：** テキストのみ（Primaryカラー・太字）。

    component_style:
      card:
        border_radius: "4px"
        shadow: "none"
        border: "1px solid rgba(61,174,216,0.15)"
      bullet:
        color: "Primary"
        shape: "circle"
      number:
        style: "text-only"
        color: "Primary"

## Do / Don't

**Do（やること）**
- スカイブルー1色をアクセントに絞り、白背景とのコントラストを最大限に活かす
- 数値・ページ番号・強調テキストにはPrimaryカラーを使い、視線誘導を明確にする
- テキスト情報を整理し、段組みとテーブルレイアウトで読みやすさを優先する
- 余白を十分取り、フォーマルなコーポレートの清潔感を保つ

**Don't（やってはいけないこと）**
- スカイブルー以外の派手なアクセントカラー（オレンジ・レッド・グリーン等）を追加しない
- コンテンツエリアに装飾グラフィックや過剰なグラデーションを使用しない
- フォントウェイトを多用せず、Bold（700）と Regular（400）の2段階に留める
- 1ページに情報を詰め込みすぎず、日本語テキストの密度に注意する
