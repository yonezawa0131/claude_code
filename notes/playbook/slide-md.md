# SLIDE.md スライド作成プレイブック

Claude 上でデザインの一貫したスライドを作るためのワークフロー。
[sho-ai-magic/slide.md](https://github.com/sho-ai-magic/slide.md) v1.2.1 のスキル一式をこのリポジトリに取り込み、
最終工程（HTMLスライド生成）を担う独自スキルを1つ追加した構成。

## 導入済みスキル（5つ）

| スキル | 役割 | 出力 |
|---|---|---|
| `slide-md-creator` | 既存スライド・画像・Webサイトからデザインシステムを抽出 | `SLIDE-md/SLIDE-md-{source}/SLIDE.md` + `sample.html` |
| `slide-pattern-creator` | スライド画像からレイアウトパターンを抽出 | `SLIDE-PATTERN/SLIDE-PATTERN-{name}/`（.md + スケルトン.html） |
| `slide-scenario-creator` | 壁打ちでシナリオ作成・3段階レビュー・ペルソナ設定 | `SLIDE-SCENARIO/SLIDE-SCENARIO-{name}.md`・`PERSONA/PERSONA-{name}.md` |
| `slide-deck-builder` | シナリオ＋デザイン＋パターンから設計書を生成 | `SLIDE-DECK/SLIDE-DECK-{name}/SLIDE-DECK-{name}.md` + `pattern-preview.html` |
| `slide-html-generator` | **（独自追加）** 設計書から完成HTMLスライドを並列生成 | `SLIDE-DECK/SLIDE-DECK-{name}/slides/`（各スライド.html + index.html + print.html） |

上流の4スキルは `.claude/skills/` に無改変で配置。パターン127種類とサンプルデザインシステム10種類は
`.claude/docs/SLIDE-PATTERN/`・`.claude/docs/SLIDE-md/` に同梱しており、カレントディレクトリに
ファイルが無くてもスキルのフォールバックがここを参照する。

## 基本ワークフロー

```
① シナリオ作成      「プレゼンのシナリオを作って」        → slide-scenario-creator
   （レビュー）      「シナリオをレビューして」            → 良い点→改善点→デビルズアドボケイト
② 設計書生成        「スライドデッキを組んで」            → slide-deck-builder
   （プレビュー）    pattern-preview.html で割り当て確認・差し替え
③ HTML生成          「スライドを生成して」                → slide-html-generator
   （修正）          「Slide 3 の見出しを○○に変えて」     → 該当スライドだけ再生成
```

デザインシステムは同梱サンプル10種類からの選択で始められる。自社・自分のデザインに合わせたい場合は
①の前に「このスライドのデザインシステムを作って」（slide-md-creator）で SLIDE.md を作っておく。

### ペルソナレビュー

レビュー精度を上げたい場合は、最初に「ペルソナを作って」（slide-scenario-creator のペルソナ設定モード）で
資料を見せる相手（上司・役員・顧客など）を `PERSONA-{name}.md` として定義しておくと、
以後のシナリオレビューでその人物視点の指摘が受けられる。

## マルチモデル運用（トークン最適化）

このリポジトリでの推奨構成：

- **司令塔（メインセッション）**：Fable。ヒアリング・壁打ち・設計判断・検品を担当
- **手足（サブエージェント）**：Sonnet。HTMLスライドの並列生成など、仕様が確定した量産作業を担当
- **昇格**：複雑なチャート・SVG を含むスライドのみ Opus に昇格

slide-html-generator はこの分担を前提に設計されており、各サブエージェントには
「デザインシステム＋担当スライドのパターン定義＋担当スライドの仕様」だけを渡すことで、
司令塔のコンテキスト肥大とサブエージェントへの重複投入を避ける。
v1.2.1 の slide-md-creator も複数ソース分析時にサブエージェント並列分析を行う。

## 上流からの更新

取り込み元：`sho-ai-magic/slide.md` コミット `e22a686`（v1.2.1、2026-07-05）。
上流が更新されたら、リポジトリを clone して以下を上書きコピーする：

- `skills/{slide-md-creator,slide-pattern-creator,slide-scenario-creator,slide-deck-builder}/` → `.claude/skills/`
- `docs/SLIDE-PATTERN/`・`docs/SLIDE-md/` → `.claude/docs/`
- `CHANGELOG.md` → `.claude/docs/SLIDE-md.CHANGELOG.md`

`slide-html-generator` は独自スキルなので上書き対象外。上流の SLIDE-DECK.md 仕様が
変わった場合のみ追従修正する。ライセンスは MIT（`.claude/docs/SLIDE-md.LICENSE`）。

## 補足

- パターンギャラリー（全127種類）：https://sho-ai-magic.github.io/slide.md/
- pattern-preview.html や slides/index.html は `file://` で開くと iframe が空白になるため、
  スキルが用意するローカルサーバー（`.claude/launch.json`）経由で開く
- PDF化：`slides/print.html` をブラウザで開き印刷 → PDF保存
