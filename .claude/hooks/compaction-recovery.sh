#!/bin/bash
# PostCompact hook (matcher: "" = manual/auto 両方): 圧縮発生を marker file で記録する。
# PostCompact は additionalContext 出力をサポートしないため、
# context 注入は UserPromptSubmit 側 (userpromptsubmit-compact.sh) で行う。
#
# fail-open (常に exit 0)

set -uo pipefail

INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
[[ -z "$SESSION_ID" ]] && exit 0

# marker file を書く（UserPromptSubmit が検出して context 注入→削除する）
MARKER_DIR="${TMPDIR:-/tmp}/claude-compacted"
mkdir -p "$MARKER_DIR" 2>/dev/null || true
printf '%s\n' "$(date +%s)" > "$MARKER_DIR/$SESSION_ID" 2>/dev/null || true

# compact が実行されたら閾値警告の cooldown をリセットする
WARNED_DIR="${TMPDIR:-/tmp}/claude-compact-warned"
rm -f "$WARNED_DIR/$SESSION_ID" 2>/dev/null || true
WARN_DIR="${TMPDIR:-/tmp}/claude-compact-warn"
rm -f "$WARN_DIR/$SESSION_ID" 2>/dev/null || true

exit 0
