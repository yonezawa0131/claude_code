# データスキーマ定義

本システムでは 1案件 = `campaigns/<campaign_id>/` ディレクトリで管理する。

```
campaigns/<campaign_id>/
├── order.yaml    # (1) オーダー入力（人間が書く）
├── plan.yaml     # (1) 生成物: 媒体プラン + シミュレーション（`adops plan` が生成）
├── actuals.csv   # (3)(4) 実績（管理画面からエクスポート/転記）
└── report.md     # (5) 生成物: レポート（`adops report` が生成）
```

## order.yaml（入力）

```yaml
campaign_id: 2026-08_glowlips          # ディレクトリ名と一致させる
advertiser: 株式会社サンプル
product: グロウリップス（リップ美容液）
objective: awareness                   # awareness | reach | video_views | consideration
kpi: reach                             # 主KPI: reach | impressions | views | completed_views | cpm | cpv
period:
  start: 2026-08-01
  end: 2026-08-31
budget_total: 10000000                 # 円（税抜グロス）
target:
  age: [20, 34]                        # [min, max]
  gender: female                       # male | female | all
  interests: [美容, コスメ]             # 興味関心（任意）
  area: 全国                            # 任意
preferred_media: [youtube]             # 希望媒体（media keyのリスト、空なら自動選定）
excluded_media: []                     # 除外媒体
notes: 新商品ローンチに合わせて認知最大化   # 任意
```

## plan.yaml（`adops plan` の生成物）

```yaml
campaign_id: 2026-08_glowlips
generated_at: "2026-07-02T10:00:00"
objective: awareness
strategy_summary: <選定ロジックの要約文>
allocations:                           # 媒体別配分
  - media: youtube                     # benchmarks.yaml の media key
    media_name: YouTube（スキッパブルインストリーム）
    budget: 5000000
    share: 0.5                         # 予算構成比
    score: 1.23                        # 選定スコア（objective_fit × audience_fit）
    optimization: 目標インプレッション単価（tCPM）
    targeting:
      age: [20, 34]
      gender: female
      segments: [美容, コスメ]
    operation_notes:                   # 運用手法（文字列リスト）
      - フリークエンシーキャップ 週3回
simulation:
  total:
    budget: 10000000
    impressions: 18181818
    views: 5454545                     # 媒体ごとに視聴定義が異なる点に注意
    completed_views: 3636363
    reach: 6060606                     # 重複控除後のユニークリーチ推定
    cpm: 550.0
    cpv: 1.83
  by_media:
    - media: youtube
      budget: 5000000
      impressions: 9090909
      views: 3181818
      completed_views: 2272727
      reach: 3030303
      cpm: 550.0
      cpv: 1.57
      vtr: 0.35
      view_definition: 30秒視聴 or 完全視聴
```

## actuals.csv（実績入力）

1行 = 1日 × 1媒体。ヘッダ必須。reach など取得できない列は空欄可。

```csv
date,media,cost,impressions,views,completed_views,clicks,reach
2026-08-01,youtube,161290,310000,108000,72000,450,
2026-08-01,tiktok,96774,160000,64000,20000,600,
```

- `media` は plan.yaml の allocations の media key と一致させる
- `cost` は円
- 数値列は整数（reach のみ空欄可・媒体レポートで取れる場合のみ）

## ステータス dict（tracker.campaign_status の返り値）

```python
{
  "campaign_id": str,
  "period": {"start": date, "end": date},
  "days_total": int,
  "days_elapsed": int,          # 期間内経過日数（実績データの最終日基準）
  "pace": float,                # days_elapsed / days_total
  "total": {
     "budget": int, "cost": int, "spend_ratio": float,   # cost / budget
     "impressions": int, "sim_impressions": int, "imp_ratio": float,  # 実績/シミュ（期間按分なしの対全体比）
     "views": int, "sim_views": int, "view_ratio": float,
     "completed_views": int, "sim_completed_views": int,
     "cpm": float, "sim_cpm": float, "cpm_ratio": float,  # 実績CPM / シミュCPM（1超え=割高）
     "cpv": float, "sim_cpv": float,
     "vtr": float, "sim_vtr": float,
  },
  "by_media": [ {"media": str, "media_name": str, ...totalと同じキー...} ],
}
```

比率系は分母 0 のとき `None`。`imp_ratio` 等はシミュレーション全体値に対する到達率（進捗率と比較して読む）。
