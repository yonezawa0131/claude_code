---
name: autopilot
description: workflows/ に定義された自律ワークフローを「dispatch → verify → retry → log」のプロトコルで実行する。司令塔（メインセッションのモデル）はオーケストレーションに徹し、実作業は executor-sonnet / executor-opus サブエージェント、検証は verifier サブエージェントに分担する。トリガー:「/autopilot <workflow名>」「<workflow名>のワークフローを実行して」「ワークフロー一覧」（引数 list）。定義のないアドホック作業には使わない。
---

# autopilot — 自律ワークフローの実行プロトコル

あなた（このスキルを読んでいるメインセッション＝司令塔）は、以降**実作業をせず**、計画・分担・検証ゲート・報告に徹する。アーキテクチャの背景は `notes/playbook/autonomous-workflows.md`。

司令塔のモデルは問わない（cron 起動の定常運用は Sonnet を想定）。あなたが Sonnet 以下のモデルなら、このプロトコルに書かれていない即興判断をせず、迷った時点で停止してユーザーへエスカレーションする。

## 引数の解釈

- `/autopilot list` — `workflows/*.md`（TEMPLATE.md と README.md を除く）の frontmatter を読み、name / trigger / executor / 概要を表として提示して終了
- `/autopilot <name>` — 該当ワークフローを実行
- `/autopilot <name> dry-run` — Phase 1 と実行計画の提示までで止める（dispatch しない）
- 引数なし — list と同じ扱いにし、どれを実行するか確認する

## Phase 0 — 前提確認

1. `workflows/<name>.md` を読む。存在しなければ list を提示して終了。
2. **実行禁止条件**（1 つでも該当したら実行せずユーザーに報告）:
   - `verify` チェックリストが空、または実質的に検証不能（「良い感じか確認」等）
   - `boundaries` の許可パスが未定義
3. `workflows/logs/` に同名ワークフローの直近ログがあれば読み、前回の失敗・申し送りを引き継ぐ。

## Phase 1 — 計画

1. frontmatter の `executor` を既定としつつ、タスクの実態で上書き判断してよい:
   - 仕様が明確・単段 → executor-sonnet
   - 多段・判断を要する・前回 sonnet で FAIL → executor-opus
   - 大量アイテムの分類が前段にある → まず triage(haiku) に分類させ、結果で分割
2. タスクを executor への**自己完結した指示**に落とす。指示には必ず含める:
   - やること（ワークフロー本文の手順）
   - `boundaries` の全文（許可パス・禁止事項）
   - 出力先（`output` フィールド）
   - 「境界外に触る必要が出たら止めて報告」の明示

## Phase 2 — Dispatch

- Agent ツールで executor を起動する（`subagent_type: general-purpose` ではなく、必ず `executor-sonnet` / `executor-opus` を指名）。
- **フォールバック**: エージェント定義はセッション開始時に読み込まれるため、定義直後のセッション等で `not found` になる場合がある。その場合は `subagent_type: general-purpose` + `model` パラメータでモデルを指定し、`.claude/agents/<name>.md` の本文（行動規範・報告フォーマット）を指示の冒頭に全文転記して代替する。verifier の代替時は「書き込みツールを使わない」旨を指示に明記する。
- 独立したサブタスクが複数あるなら並列に dispatch してよい。依存があるものは直列。
- executor の報告から「未処理・懸念・気づき」を回収し、最終報告に反映する。

## Phase 3 — Verify（省略禁止）

1. ワークフローに機械的チェック（テスト、lint、スクリプト）が定義されていれば先に実行する。失敗はその時点で差し戻し理由になる。
2. `verifier` サブエージェントを起動し、次を渡す:
   - `verify` チェックリスト全文
   - `boundaries` 全文
   - executor が報告した成果物パス一覧
3. verifier の 1 行目判定（PASS/FAIL）で分岐する。**自分（司令塔）が verifier を代行して PASS を出すことは禁止。**

## Phase 4 — Retry / Escalate

- FAIL → verifier の「差し戻し指示」を添えて同じ executor に**1 回だけ**再 dispatch し、Phase 3 をやり直す。
- 2 回目の FAIL → リトライせず停止。ユーザーに「何が起きたか・何を試したか・何を決めてほしいか」を報告する。成果物は消さず残す（ログに場所を記す）。

## Phase 5 — Log & Report

1. `workflows/logs/YYYY-MM-DD-<name>.md` を作成（同日複数回は `-2` 等を付す）:

   ```markdown
   # <name> — YYYY-MM-DD
   - 判定: PASS / FAIL(escalated)
   - executor: <使ったエージェントとリトライ回数>
   - 成果物: <パス一覧>
   - verifier の所見: <基準外の気づき>
   - 申し送り: <次回実行への引き継ぎ>
   ```

2. `boundaries` が commit を許可していれば、成果物とログを論理単位で commit する。push は `boundaries` が明示的に許可している場合のみ。
3. ユーザーへ結果を報告する。FAIL 時は隠さず生の判定を伝える。

## 不変条件（このスキル自身のリファクタでも変えない）

- verifier に書き込みツールを与えない／司令塔が検証を代行しない
- verify が空のワークフローを実行しない
- 外部公開（送信・投稿・PR 作成）は draft 止まり。実行はユーザーの明示承認後
- 自動リトライは 1 回まで
