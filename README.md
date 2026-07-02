# adops — ブランディング動画広告 プランニング&レポーティング自動化

認知目的のデジタル動画プロモーション運用のうち、負荷の大きい2工程を自動化するツールキットです。

- **(1) プランニング**: オーダー（商品/ターゲット/希望媒体/予算/目的）→ 媒体選定・最適化設定・ターゲティング・運用手法・シミュレーションを自動生成
- **(5) レポーティング**: 実績集計 → シミュレーション比の達成率算出 → 考察・NEXT ACTION 素案つきレポートを自動生成

途中の (2)入稿 (3)チューニング (4)実績記録 は人間が行い、実績は CSV で記録するだけで、並行案件の「想定比」を横断管理できます。

## セットアップ

```bash
pip install pyyaml pytest
```

## 使い方（案件のライフサイクル）

### 1. 案件を作る → プラン生成

```bash
mkdir campaigns/2026-08_glowlips
$EDITOR campaigns/2026-08_glowlips/order.yaml   # スキーマは docs/SCHEMAS.md 参照
python3 -m adops plan campaigns/2026-08_glowlips
```

→ `plan.yaml` が生成されます（媒体別の予算配分・最適化設定・ターゲティング・運用ノート・シミュレーション）。

### 2. 配信中: 実績を記録して進捗確認

管理画面の日次実績を `actuals.csv` に追記（1行 = 1日×1媒体）:

```csv
date,media,cost,impressions,views,completed_views,clicks,reach
2026-08-01,youtube,161290,310000,108000,72000,450,
```

```bash
python3 -m adops status                          # 全案件横断（並行案件の想定比を一覧）
python3 -m adops status campaigns/2026-08_glowlips  # 媒体別の詳細
```

### 3. 終了後: レポート生成

```bash
python3 -m adops report campaigns/2026-08_glowlips
```

→ `report.md` が生成されます（シミュ比サマリ表・媒体別実績・ルールベースの考察素案・NEXT ACTION素案）。

## Claude Code サブエージェント

Claude Code から使う場合、工程ごとに専用エージェントに委譲されます（`.claude/agents/`）:

| エージェント | 担当 | モデル |
|---|---|---|
| media-planner | オーダー整理 → プラン生成 → プランナー観点のレビュー | sonnet |
| performance-analyst | 横断進捗チェック、乖離の切り分け、チューニング提案 | sonnet |
| actuals-entry | 管理画面の数値を actuals.csv へ整形・転記 | haiku |
| report-writer | レポートの考察・NEXT ACTION を文章化して仕上げ | sonnet |

例: 「サンプルコスメの8月案件、この内容でプランして」「全案件の進捗見て要対応だけ教えて」「6月の飲料案件のレポート仕上げて」

## リポジトリ構成

```
adops/            # エンジン（planner / tracker / reporter / CLI）
config/benchmarks.yaml  # 媒体マスタ（CPM/VTR/選定スコア/最適化設定/運用ノート）
campaigns/<id>/   # 1案件 = 1ディレクトリ（order → plan → actuals → report）
docs/SCHEMAS.md   # データスキーマ定義
.claude/agents/   # サブエージェント定義
tests/
```

## 精度を上げていくには

シミュレーション精度はすべて `config/benchmarks.yaml` に依存します。案件が終わるたびに report.md の「シミュレーション精度の振り返り」を確認し、実勢と乖離した媒体の CPM/VTR を実績値ベースで更新してください。
