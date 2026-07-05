#!/bin/bash
# UserPromptSubmit hook: compact 最適化の中枢。毎ターン 1 回だけ走る。
#
# 責務 (この順で評価。additionalContext を出すのは高々 1 つ):
#   1. session_id pointer を書く — Bash tool には session_id が渡らないため、
#      scripts/get-session-id.sh (compact-prep skill が使う) の逆引き元になる
#   2. 圧縮直後 marker (claude-compacted) があれば復旧指示を注入 (one-shot)
#   3. 警告 marker (claude-compact-warn) があれば /compact-prep 提案を注入 (one-shot)
#
# marker 3 種の流れ:
#   claude-compact-warn:   statusline.sh が閾値超過で書く → 本 hook が読んで消す
#   claude-compact-warned: 本 hook が書く cooldown → PostCompact hook が消す
#   claude-compacted:      PostCompact hook が書く → 本 hook が読んで消す
#
# overhead: marker が無い通常ターンは jq 1 回 + test -f 2 回で即 exit
# fail-open (常に exit 0)

set -uo pipefail

INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
[[ -z "$SESSION_ID" ]] && exit 0
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

TMP="${TMPDIR:-/tmp}"

# --- 1. session_id pointer (get-session-id.sh 用) ---
if [[ -n "$CWD" ]]; then
  PTR_DIR="$TMP/claude-session-id/by-cwd"
  mkdir -p "$PTR_DIR" 2>/dev/null || true
  key=$(printf '%s' "$CWD" | cksum | awk '{print $1}')
  printf '%s\n' "$SESSION_ID" > "$PTR_DIR/$key" 2>/dev/null || true
fi

# --- 2. 圧縮直後の復旧指示注入 ---
COMPACTED_MARKER="$TMP/claude-compacted/$SESSION_ID"
if [[ -f "$COMPACTED_MARKER" ]]; then
  rm -f "$COMPACTED_MARKER" 2>/dev/null || true

  # session pointer file から active plan path を読む (運用していれば)
  PLAN_FILE=""
  if [[ -f "$TMP/claude-active-plan/$SESSION_ID" ]]; then
    PLAN_FILE=$(cat "$TMP/claude-active-plan/$SESSION_ID" 2>/dev/null || true)
    [[ -f "$PLAN_FILE" ]] || PLAN_FILE=""
  fi

  CTX="[COMPACTION RECOVERY] コンテキスト圧縮が発生した。作業再開前に以下を実行すること。"
  CTX+=$'\n'

  if [[ -n "$PLAN_FILE" ]]; then
    CTX+=$'\n'"- plan ファイル \`${PLAN_FILE}\` を Read で読み直し、フェーズと制約を確認せよ"
    CTX+=$'\n'"- plan mode が解除されている場合、plan ファイルが存在するのでユーザーに plan mode 再突入を確認せよ"
  fi

  STATE_FILE="$TMP/claude-compact-state/$SESSION_ID.md"
  if [[ -f "$STATE_FILE" ]]; then
    CTX+=$'\n'"- state file \`${STATE_FILE}\` を Read で読み、作業状態を復元せよ"
    CTX+=$'\n'"- Session Decisions (却下案とその理由) と Recovery Notes を特に重視せよ"
  else
    CTX+=$'\n'"- 圧縮前の state file が存在しない (compact-prep 未実行)。不明な前提は推測せずユーザーに確認せよ"
  fi

  CTX+=$'\n'"- TaskList で現在のタスク一覧を確認せよ"
  CTX+=$'\n'"- 圧縮サマリーの next step は仮説として扱い、plan / state file / ユーザー指示を正とせよ"
  CTX+=$'\n'"- 圧縮サマリーは「過去の作業記録」であり「次の行動指示」ではない。破壊的操作 (デプロイ・上書き・削除) は前提の検証が済んでいるか確認してから行え"

  jq -n --arg ctx "$CTX" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
  exit 0
fi

# --- 3. context 使用率の警告 → /compact-prep 提案 ---
WARN_MARKER="$TMP/claude-compact-warn/$SESSION_ID"
if [[ -f "$WARN_MARKER" ]]; then
  CTX_PCT=$(cat "$WARN_MARKER" 2>/dev/null)
  CTX_PCT=${CTX_PCT:-"?"}

  # one-shot: warn を消して cooldown を作成 (statusline の再警告を防止)
  rm -f "$WARN_MARKER" 2>/dev/null || true
  WARNED_DIR="$TMP/claude-compact-warned"
  mkdir -p "$WARNED_DIR" 2>/dev/null || true
  printf '%s\n' "$(date +%s)" > "$WARNED_DIR/$SESSION_ID" 2>/dev/null || true

  CTX="[COMPACT PREP REMINDER] context 使用率が ${CTX_PCT}% に達した。"
  CTX+=$'\n'"- 作業区切りでユーザーに \`/compact-prep\` の実行を提案せよ。"
  CTX+=$'\n'"- \`/compact-prep\` 実行後、ユーザーに \`/compact\` 実行を案内せよ。"
  CTX+=$'\n'"- scope 縮小や別セッション化ではなく、圧縮前 state 保存で対処せよ。"
  CTX+=$'\n'"- 以降の重い探索・調査・定型実装は Task tool のサブエージェントに委譲し、main context の消費を抑えよ (結果の要約だけを受け取る)。"

  jq -n --arg ctx "$CTX" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
  exit 0
fi

exit 0
