---
name: compact-prep
description: |
  Claude Code の /compact 実行前に、現セッションの作業状態（判断構造・セッション状態）を一時 state file へ保存する。
  MANDATORY TRIGGERS: /compact-prep, compact-prep, 圧縮準備, compact 準備, コンパクト準備, 圧縮前状態保存。
  DO NOT TRIGGER: compact 後の復旧、通常の進捗報告、plan 作成、context 使用率の雑談。
argument-hint: "[復旧メモ]"
allowed-tools: Read Write Bash($CLAUDE_PROJECT_DIR/scripts/get-session-id.sh *) Bash(~/.claude/scripts/get-session-id.sh *) Bash(mkdir *) Bash(date *) Bash(pwd) TaskList
---

# compact-prep

Claude Code の `/compact` 前に、圧縮サマリーへ残りにくい作業状態を
`${TMPDIR:-/tmp}/claude-compact-state/${SESSION_ID}.md` へ保存する。

標準 compact の要約は「過去の作業記録」であり「次の行動指示」ではない。
要約から落ちやすいのは判断構造（なぜ採用したか / なぜ却下したか / 今どのフェーズか）と
セッション状態（plan mode / worker 委譲 / タスクツリー）。この skill はそれだけを抜き出して保存する。

## Strict procedure profile

- Strictness: strict-procedure。圧縮前 state file の内容と保存完了報告が成果そのもの。
- Hard gate: session_id が取得できない場合は state file を推測名で作らず、取得不能として停止する。
- Forcing function: 保存先パスを固定し、保存後にファイルを読み返して必須見出しの有無を確認する。
- Completion receipt: state file パス、保存した主要項目、未確認項目、次に実行する `/compact` 案内を報告する。

## 手順

1. session_id を取得する。
   - `get-session-id.sh` を実行する（`$CLAUDE_PROJECT_DIR/scripts/get-session-id.sh`、無ければ `~/.claude/scripts/get-session-id.sh`）。
   - 取得できない場合は state file を作らず、「session_id が取得できないため準備未完了」と報告して停止する（Hard gate）。
2. 保存先を `${TMPDIR:-/tmp}/claude-compact-state/${SESSION_ID}.md` に決め、ディレクトリを `mkdir -p` する。
3. 現セッションの状態を棚卸しする。
   - TaskList（あれば）で in-progress / pending タスクを確認する。
   - active plan file があれば読む（plan mode 中に作った plan、または合意済みの計画メモ）。
   - サブエージェント / worker に委譲中の作業があれば、その一覧と担当を確認する（tmux 併用時は pane / role も）。
   - 編集中・未コミット・未検証のファイルを `git status` 相当の知識と会話履歴から列挙する。
   - `$ARGUMENTS` に復旧メモが渡されていれば Recovery Notes に含める。
4. state file に以下の見出しを**この順で**すべて書く。該当なしの項目は「なし」と明記する（見出しごと省略しない）。
   - `# Compact Prep State`
   - `## Active Plan` — plan file のパスと、現在のフェーズ / ステップ
   - `## TaskList Summary` — in-progress タスク一覧と補足
   - `## Session Decisions` — 採用した案 / **却下した案とその理由** / ユーザーの選択
   - `## Constraints and Blockers` — 制約、ブロッカー、未完了の検証（「検証してからデプロイ」等の順序制約は必ずここに書く）
   - `## Worker Topology` — サブエージェント / worker への委譲状況。未使用なら「未使用」
   - `## Editing Files` — 編集中のファイルと、未保存・未コミット・未検証の注意点
   - `## Recovery Notes` — 圧縮後の自分への手紙。「次にやること」と「やってはいけないこと」を命令形で書く
5. 保存後に state file を Read で読み直し、上記見出しがすべて存在することを確認する（Forcing function）。欠落があれば書き足す。
6. ユーザーに Completion receipt を返し、「準備完了。`/compact` を実行してください。」と伝える。

## 書き方の指針

- 「作業ログ」ではなく「作業指示」として書く。圧縮後の自分は経緯を知らない前提で、命令形で書く。
- 却下案は「試した」ではなく「**却下した。理由: X**」と書く。要約が却下案を「試みた手順」として残すと再実行事故が起きる。
- フェーズ制約（検証→デプロイの順序など）は Constraints に必ず残す。要約はフェーズ境界を溶かす。
- 「配置先を直接編集せず管理元 repo を編集して配布する」のような、セッション中に確立した設計原則も Session Decisions に残す。

## Completion receipt

完了時は次を含める。

- state file パス
- 保存した主要項目
- 未確認項目と理由
- `準備完了。/compact を実行してください。`
