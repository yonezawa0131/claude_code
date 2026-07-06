# workflows/ — 自律ワークフロー定義

`/autopilot <name>` で実行されるワークフローの置き場。1 ファイル = 1 ワークフロー。

- 実行プロトコル: `.claude/skills/autopilot/SKILL.md`
- アーキテクチャ: `notes/playbook/autonomous-workflows.md`
- 新規作成: `TEMPLATE.md` をコピーして埋める。**verify と boundaries が空の定義は実行されない**
- 実行記録: `workflows/logs/`（autopilot が自動生成）

| ワークフロー | トリガー | executor | 何をするか |
|---|---|---|---|
| `ingest-to-vault` | 手動（raw/ 投入後） | sonnet | vault の raw/ 新着を entities/concepts へ取り込み |
| `repo-sweep` | cron 週次想定 | sonnet | リポジトリ衛生（リンク切れ・索引同期・陳腐化検出） |
| `daily-briefing` | cron 朝想定 | sonnet | カレンダー・未読メールから朝のブリーフィング生成 |
