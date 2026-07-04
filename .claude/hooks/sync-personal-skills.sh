#!/bin/bash
set -euo pipefail

# リモート実行環境（Claude Code on the web）のコンテナは揮発性で、
# 個人Skill ~/.claude/skills/session-start-hook はセッションごとに
# 古いストック版（name不一致・description衝突あり）が再配備される。
# Skill監査で修正した版をセッション開始時に上書きして恒久化する。
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

SRC="$CLAUDE_PROJECT_DIR/.claude/hooks/assets/session-start-hook.SKILL.md"
[ -f "$SRC" ] || exit 0

for home in /root /home/claude "$HOME"; do
  dst="$home/.claude/skills/session-start-hook"
  [ -d "$dst" ] || continue
  cp "$SRC" "$dst/SKILL.md"
done
