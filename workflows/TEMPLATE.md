---
name: <一意なワークフロー名（ファイル名と一致させる）>
trigger: manual | cron "<5フィールド cron 式>" | file "<監視パス>"
executor: sonnet | opus   # 既定値。司令塔が実態で上書き判断してよい
output: <成果物の出力先パス>
boundaries:
  allow:
    - <読み書きしてよいパス（glob 可）>
  deny:
    - <禁止事項を列挙（例: raw/ への書き込み、外部送信、push）>
  commit: true | false    # 成果物を commit してよいか
  push: false             # 原則 false。true は明示的な理由がある場合のみ
verify:
  - <受け入れ基準 1（verifier が現物で機械的に確認できる表現で書く）>
  - <受け入れ基準 2>
---

# <ワークフロー名>

## 目的

<このワークフローが removing you from what work なのかを 1〜2 文で>

## 手順

<executor に渡す作業手順。自己完結で書く — executor はこのファイルと司令塔の指示以外の文脈を持たない>

1. ...
2. ...

## 補足

<エッジケース、前回からの申し送りの読み方、など>
