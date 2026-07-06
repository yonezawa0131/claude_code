# skill-vault-synthesis

過去 7 日分の vault を横断し「今週の意味」を 1 ページに書く週次 synthesis Skill。上位モデル専任。

#type/skill #domain/vault #layer/procedure

## 何をするか

`raw/daily/` 直近 7 日・`reviews/` の日次ダイジェスト・`entities/concepts` の 7 日差分(git log で特定)を横断読みする。横断パスなので subagent に広く読ませてよく、メインには結論のみ返す。出力は `reviews/YYYY-Www.md`(ISO 週番号)で、繰り返しテーマ・矛盾・やりかけの約束・ドリフト・来週注目の 5 項目を出典リンク付きで書く。矛盾は指摘のみで解消しない(解消は [[skill-memory-dream]] かユーザー判断)。

## 入出力・使いどころ

入力は vault 全体(横断読みの例外規定)。出力は reviews/ の週次ページと NOW.md。raw/ と過去の reviews/ は書き換えない。維持ループの中で唯一上位モデル(Opus 級)を使うパス。

## 関連

- [[playbook-obsidian-vault]] — 読み取りルールの横断パス例外・維持ループ表の定義元
- [[skill-vault-compile]] — 日次側の対、synthesis は週次で意味を凝縮する
- [[skill-memory-dream]] — 矛盾の解消先(synthesis は指摘のみ)
- [[pay-per-read]] — 日常の読み方との対比原則

出典: [`.claude/skills/vault-synthesis/SKILL.md`](../raw/source-snapshot/dot-claude/skills/vault-synthesis/SKILL.md)
