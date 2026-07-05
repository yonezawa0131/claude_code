#!/bin/bash
# statusLine command: モデル / ディレクトリ / context 使用率を表示しつつ、
# 使用率が閾値を超えたら compact-prep 警告 marker を書く。
#
# context 使用率は自前計算せず、statusline stdin JSON の
# context_window.used_percentage (公式フィールド) を使う。
#
# 閾値は COMPACT_WARN_THRESHOLD (settings.json の env で設定、デフォルト 60)。
# 60 は 1M context 前提の値。200K context なら 80 程度に上げること。
#
# fail-open: 解析に失敗しても表示だけは返す。

set -uo pipefail

INPUT=$(cat)

MODEL=$(printf '%s' "$INPUT" | jq -r '.model.display_name // "Claude"' 2>/dev/null)
DIR=$(printf '%s' "$INPUT" | jq -r '.workspace.current_dir // .cwd // ""' 2>/dev/null)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
PCT=$(printf '%s' "$INPUT" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)

int_pct=""
[[ -n "$PCT" ]] && int_pct=${PCT%%.*}

# 閾値超で compact-prep 警告 marker を書く（cooldown 中でなければ）
COMPACT_WARN_THRESHOLD="${COMPACT_WARN_THRESHOLD:-60}"
if [[ -n "$SESSION_ID" && -n "$int_pct" ]] && [ "$int_pct" -ge "$COMPACT_WARN_THRESHOLD" ] 2>/dev/null; then
  _warned_dir="${TMPDIR:-/tmp}/claude-compact-warned"
  if [[ ! -f "$_warned_dir/$SESSION_ID" ]]; then
    _warn_dir="${TMPDIR:-/tmp}/claude-compact-warn"
    mkdir -p "$_warn_dir" 2>/dev/null || true
    printf '%s\n' "$int_pct" > "$_warn_dir/$SESSION_ID" 2>/dev/null || true
  fi
fi

# 表示 (1 行)
CTX_LABEL=""
if [[ -n "$int_pct" ]]; then
  if [ "$int_pct" -ge "$COMPACT_WARN_THRESHOLD" ] 2>/dev/null; then
    CTX_LABEL=" | ctx ${int_pct}% ⚠ compact-prep 推奨"
  else
    CTX_LABEL=" | ctx ${int_pct}%"
  fi
fi

printf '%s | %s%s\n' "$MODEL" "$(basename "${DIR:-?}")" "$CTX_LABEL"
