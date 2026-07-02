# adops — ブランディング動画広告の運用ワークフロー自動化

認知目的のデジタル動画プロモーションについて、(1) プランニング/シミュレーション作成 と (5) 結果レポート作成 を自動化・効率化するリポジトリ。1案件 = `campaigns/<campaign_id>/`（スキーマは `docs/SCHEMAS.md` が正）。

## コマンド

```bash
python3 -m adops plan campaigns/<id>    # order.yaml → plan.yaml（媒体選定+シミュレーション）
python3 -m adops status                 # 全案件横断: 実績 vs シミュ進捗
python3 -m adops status campaigns/<id>  # 1案件の媒体別詳細
python3 -m adops report campaigns/<id>  # report.md 生成（集計表+考察素案）
python3 -m pytest -q                    # テスト
```

## エージェントへの委譲ルール（推論コスト最適化）

メイン会話では自分で作業せず、必ず該当サブエージェントに委譲し、返ってきた成果物の品質を確認して要点だけ報告すること:

| 依頼内容 | 委譲先 |
|---|---|
| 新規案件のプランニング、シミュレーション作成・引き直し | media-planner |
| 進捗確認、乖離分析、チューニング提案 | performance-analyst |
| 実績数値の actuals.csv への転記・整形 | actuals-entry |
| 終了後レポートの作成・考察/NEXT ACTIONの文章化 | report-writer |

品質確認の観点: 数値の整合（予算合計・達成率の計算）、スキーマ準拠、媒体間で視聴定義を混同した比較をしていないか、事実と仮説の書き分け。

## 設計上の前提

- シミュレーション数値は `config/benchmarks.yaml` のプランニング用参考値に基づく。案件実績が溜まったらベンチマークを実勢値に更新していく運用（更新は人間の承認を経ること）。
- 媒体ごとに視聴（view）の定義が異なる。視聴数・VTRの媒体間直接比較は禁止。シミュ比でのみ評価する。
- (2)入稿・(3)チューニング実施は人間が管理画面で行う。このリポジトリは判断材料と成果物の生成を担う。
- 依存は Python 3.11+ / pyyaml / pytest のみ。この構成を維持する。
