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
kpi_target: 5000000                    # 主KPIの与件数値（任意。あれば達成見込みチェックに使う）
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

プランの最小単位は「ライン」= 媒体 × 最適化モード（例: YouTube×リーチ最適、YouTube×視聴最適）。
モードは `config/benchmarks.yaml` の `media.<key>.modes` に定義され、目的に応じて主モード75% / 補完モード25%で配分される。

```yaml
campaign_id: 2026-08_glowlips
generated_at: "2026-07-02T10:00:00"
objective: awareness
strategy_summary: <選定ロジックの要約文>
allocations:                           # ライン（媒体×モード）ごとの配分
  - media: youtube                     # benchmarks.yaml の media key
    media_name: YouTube（Google Ads 動画/Demand Gen）
    mode: reach_opt                    # benchmarks.yaml の mode key
    optimization: リーチ最適（FQ最小化・Reach最大化）   # モードの label
    budget: 3750000
    share: 0.375                       # 予算構成比（全体比）
    score: 1.23                        # 媒体の選定スコア（objective_fit × audience_fit）
    targeting:
      age: [20, 34]
      gender: female
      segments: [美容, コスメ]
      note: デモグラ広域。セグメント最小化でFQ最小・最大リーチ   # モードの targeting_note
    operation_notes:                   # 運用手法（文字列リスト）
      - フリークエンシーキャップ 週3回
simulation:
  by_line:                             # ライン単位のフル指標
    - media: youtube
      mode: reach_opt
      budget: 3750000
      impressions: 5400000
      reach: 1730000                   # = impressions / fq
      fq: 3.12
      cpr: 2.17                        # = budget / reach
      views: 2484000                   # 媒体のView定義に基づく
      completed_views: 918000          # View(100%)
      clicks: 21600
      engagements: 16200               # engr 未定義の媒体では null
      cpm: 694.4
      cpv: 1.51
      cpc: 173.6
      cpe: 231.5                       # engagements が null なら null
      vtr: 0.46
      completion_rate: 0.17
      ctr: 0.004
  by_media:                            # 媒体単位に集約（tracker が actuals と突合する単位）
    - media: youtube
      budget: 5000000                  # ライン合計
      impressions: 6400000
      views: 2900000
      completed_views: 1200000
      reach: 2100000                   # 媒体内重複排除後
      clicks: 25000
      cpm: 781.0                       # 加重（budget/impressions×1000）
      cpv: 1.72
      vtr: 0.45
      view_definition: TrueViewビュー（30秒到達 or 完了 or 広告要素クリック）
  total:
    budget: 10000000
    impressions: 16000000
    views: 5400000
    completed_views: 2400000
    reach: 6060606                     # 純リーチ（媒体内55%/媒体間15%重複排除 + 母集団キャップ）
    clicks: 60000
    cpm: 625.0
    cpv: 1.85
    ctr: 0.0038
kpi_projection:                        # 与件達成見込み（基準6）
  kpi: reach
  target: 5000000                      # order.kpi_target（未設定なら null）
  projected: 6060606                   # 主KPIに対応するシミュレーション値
  achievement: 1.212                   # target 未設定なら null。cpm/cpv は target/projected で計算
  note: 主目的『認知/リーチ』→ 純リーチ 6,060,606人（与件 5,000,000人に対し達成見込み 121.2%）
warnings: []                           # 与件適合チェックで検知した警告（達成見込み<100% 等）
```

- 純リーチの算出モデル・モード配分比・予約型追加ルールは `config/benchmarks.yaml` 冒頭のコメントを参照。
- v1 からの変更: `instagram_reels` → `meta` に改称、`youtube_bumper` は youtube の運用ノートに統合。
  allocations は媒体単位 → ライン単位になった（tracker が使う simulation.by_media の形は維持）。

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
