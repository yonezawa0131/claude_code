# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** ブランドガイドライン資料（PDFより抽出）
**マッチするシーン：** BtoBビジネス発表・社内共有・パートナー向けプレゼン。温かみのあるゴールデンイエローを基調にした、フレンドリーかつプロフェッショナルな雰囲気。

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ゴールデンイエロー | #FFCA28 |
| Secondary | クリームイエロー | #FFF9C4 |
| Background | オフホワイト | #FEFDF7 |
| Accent | アンバーオレンジ | #DD8C00 |
| Text | チャコール | #1E1E1E |
| Text Sub | ダークグレー | #3D3D3D |
| Text Muted | ミディアムグレー | #666666 |

**グラデーション：** なし（単色使用）

    colors:
      primary: "#FFCA28"
      secondary: "#FFF9C4"
      background: "#FEFDF7"
      accent: "#DD8C00"
      text: "#1E1E1E"
      text_sub: "#3D3D3D"
      text_muted: "#666666"
      gradient_main: "なし"
      gradient_vert: "なし"

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 64px | 900（Black） |
| 見出し（H2） | Noto Sans JP | 44px | 700（Bold） |
| 本文 | Noto Sans JP | 22px | 400（Regular） |
| キャプション | Noto Sans JP | 14px | 400（Regular） |
| モノスペース | なし | - | - |

    typography:
      heading_h1:
        font: "Noto Sans JP"
        size: "64px"
        weight: "900"
      heading_h2:
        font: "Noto Sans JP"
        size: "44px"
        weight: "700"
      body:
        font: "Noto Sans JP"
        size: "22px"
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
- **余白（上下）：** 60px
- **余白（左右）：** 80px
- **テキスト整列：** 左寄せ（セクションスライドのみ中央寄せ）

    layout:
      slide_size: "16:9"
      width: "1920px"
      height: "1080px"
      padding_vertical: "60px"
      padding_horizontal: "80px"
      text_align: "left"

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部に全幅のPrimaryカラーバー（高さ50px）を配置。バー内左側に「セクション番号（bold） セクション名 ｜ サブタイトル」をTextカラーで表示。
**ページ番号：** 右下、形式「| XX」（縦線＋2桁数字）、Text Mutedカラー
**ページ番号スタイル：** 単色テキスト（Text Mutedカラー）、モノスペースフォント不使用
**ブランドフッター：** 中央下、「Copyright」相当の細いキャプションテキスト
**背景アクセント：** 通常スライドは左右端に大きな半円形の装飾（Primary / Secondaryカラーの薄め）。セクションスライドは背景全面をPrimaryカラーで塗りつぶし、中央に大きな角丸白カードを配置。
**縦バー：** なし（ヘッダーバーで代替）

    slide_frame:
      title_area:
        position: "top-full-width"
        text_align: "left"
        decoration: "full-width-primary-bar"
      page_number:
        position: "bottom-right"
        format: "| 01"
        style: "solid"
        font: "body"
      brand_footer:
        position: "bottom-center"
        content: "キャプションテキスト"
      background_accent:
        type: "half-circle-sides"
        placement: "left-edge, right-edge"
        color: "Primaryカラー薄め・Secondaryカラー"
      section_bar:
        style: "none"
        width: "-"

## Component Style

スライド内で使用するコンポーネントの基本スタイルを定義します。

**カード：** border-radius 20px、背景はSecondaryカラー（#FFF9C4）、枠線なし、影なし
**番号バッジ：** Primaryカラー（#FFCA28）の正方形（border-radius 8px）に黒テキスト（font-weight 700）
**箇条書きマーカー：** Primaryカラーの丸ドット
**番号スタイル：** 番号バッジ形式（Primary色正方形 / border-radius 8px）

    component_style:
      card:
        border_radius: "20px"
        shadow: "none"
        border: "none"
        background: "#FFF9C4"
      bullet:
        color: "Primary"
        shape: "circle"
      number:
        style: "solid-square-badge"
        color: "#FFCA28"

## Do / Don't

**Do（やること）**
- ゴールデンイエローを主役に、温かみと明るさを前面に出す
- セクション区切りはPrimaryカラーの全幅バーでメリハリをつける
- フォントウェイトの差（900 vs 400）でヒエラルキーを明確にする
- カードの背景にはSecondaryカラー（クリームイエロー）を使い、柔らかさを保つ

**Don't（やってはいけないこと）**
- 純粋な白（#FFFFFF）を背景やカードに使わない（クリーム系を使う）
- 青・赤・紫など寒色系の色をメインカラーとして使わない
- 派手なグラデーションや複数の差し色を混在させない
- 重い影（box-shadow）やボーダーをカードに加えない
