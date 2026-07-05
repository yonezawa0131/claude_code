#!/bin/bash
# 現セッションの session_id を標準出力へ出す。
#
# Claude Code は Bash tool に session_id を環境変数で渡さない
# (CLAUDE_SESSION_ID は存在しない。公式の推奨は hook stdin JSON の session_id)。
# そのため UserPromptSubmit hook (userpromptsubmit-compact.sh) が毎ターン
# ${TMPDIR}/claude-session-id/by-cwd/<cksum(cwd)> へ書く pointer file から逆引きする。
#
# 解決順:
#   1. カレントディレクトリをキーにした pointer file
#   2. 最新の pointer file (単一セッション運用時のフォールバック)
# 解決できなければ何も出力せず exit 1 (呼び出し側の Hard gate 用)。

set -uo pipefail

PTR_DIR="${TMPDIR:-/tmp}/claude-session-id/by-cwd"
[[ -d "$PTR_DIR" ]] || exit 1

key=$(printf '%s' "$PWD" | cksum | awk '{print $1}')
if [[ -f "$PTR_DIR/$key" ]]; then
  sid=$(cat "$PTR_DIR/$key" 2>/dev/null)
  if [[ -n "$sid" ]]; then
    printf '%s\n' "$sid"
    exit 0
  fi
fi

# フォールバック: 直近に書かれた pointer (並行セッションがあると誤る可能性あり)
latest=$(ls -t "$PTR_DIR" 2>/dev/null | head -1)
if [[ -n "$latest" ]]; then
  sid=$(cat "$PTR_DIR/$latest" 2>/dev/null)
  if [[ -n "$sid" ]]; then
    printf '%s\n' "$sid"
    exit 0
  fi
fi

exit 1
