# playbook-memory-dream-pointer

旧 memory-dream playbook は正式な Skill に移行済み。手順の一次情報は [[skill-memory-dream]] 側。

#type/playbook #domain/memory #layer/rule

## 何をするか

`notes/playbook/memory-dream.md` はトリガー語(「記憶を整理して」「dreamして」)で自動発火させるため Skill 化され、この playbook 自体はポインタとしてのみ残る。手順・チェックリストの実体は書かず、`.claude/skills/memory-dream/SKILL.md` を参照するだけにする。

## 入出力・使いどころ

「同じ手順を 2 箇所に書かない」という単一情報源の原則を playbook レベルで体現した例。dream の対象特定や重複排除ロジックを探すときは、このページではなく [[skill-memory-dream]] を直接読む。

## 関連

- [[skill-memory-dream]] — 移行先の一次情報
- [[playbook-obsidian-vault]] — vault 設計全体の定義元
- [[single-source-dedup]] — 定義箇所を一つに保つという原則そのもの

出典: [`notes/playbook/memory-dream.md`](../raw/source-snapshot/notes/playbook/memory-dream.md)
