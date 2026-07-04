# 過去のプランニング知識の取り込み手順

この手順は Claude Code の Skill に移行した（発見可能性のため）。
正: [`.claude/skills/knowledge-intake/SKILL.md`](../.claude/skills/knowledge-intake/SKILL.md)

Claude に「inbox の知識を取り込んで」と依頼すれば上記 Skill が発火する。
人間向けの要点: 取り込みたいファイルを `knowledge/inbox/` に置く → Claude が差分を提案 → 承認後に反映・`knowledge/archive/YYYY-MM/` へ移動。反映先は `config/benchmarks.yaml` と `.claude/agents/media-planner.md` の2ヶ所のみ。
