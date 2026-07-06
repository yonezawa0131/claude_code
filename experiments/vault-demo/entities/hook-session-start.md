# hook-session-start

Claude Code on the web のリモート環境で個人 Skill を毎セッション上書き恒久化する SessionStart フック。

#type/hook #domain/infra #layer/tool

## 何をするか

`.claude/settings.json` の `hooks.SessionStart` から `sync-personal-skills.sh` を起動する。リモート実行環境(`CLAUDE_CODE_REMOTE=true`)のときだけ動作し、`.claude/hooks/assets/session-start-hook.SKILL.md`(監査済みの正版)を `~/.claude/skills/session-start-hook/SKILL.md` へコピーする。コンテナが揮発性で個人 Skill が古いストック版に戻される問題への対策。

## 入出力・使いどころ

入力は `CLAUDE_CODE_REMOTE` 環境変数と `.claude/hooks/assets/` 配下の正版ファイル。出力は各ホーム(`/root` `/home/claude` `$HOME`)配下の `skills/session-start-hook/SKILL.md`。ローカル実行時は即 exit するため副作用がない。

## 関連

- [[playbook-obsidian-vault]] — 「維持を意志力でなくスケジュールに乗せる」設計思想の定義元
- [[maintenance-loop]] — 手動介入なしで自動的に状態を修復する維持ループの原則
- [[skill-vault-compile]] — 同様にスケジューラ起動で人手を介さず回る自動化の一例

出典: [`.claude/hooks/sync-personal-skills.sh`](../raw/source-snapshot/dot-claude/hooks/sync-personal-skills.sh)
