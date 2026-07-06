# skill-memory-dream

記憶階層(MEMORY.md/auto-memory/notes)と vault(entities/concepts/INDEX.md)の重複・矛盾・陳腐化を除去する週次 consolidation Skill。

#type/skill #domain/memory #domain/vault #layer/procedure

## 何をするか

Anthropic Managed Agents の Dreams を手動・git ベースで再現する。4 フェーズ(Mine → Consolidate → Dedup & Resolve → Prune & Index)で、相対日付を絶対化し、矛盾を最新値で解決し、階層をまたぐ重複は下位側から削る。vault 対象では追加で lint を行う: `[[wikilink]]` 切れの精査(仮リンクと腐敗の区別)、孤立ノート検出、タグのスキーマ適合、`INDEX.md` の実ファイル同期、raw/ 出典リンク欠落ページのフラグ、リンク密度の低下点検。

## 入出力・使いどころ

入力は記憶階層全体と vault の compiled 層。raw/ は読むだけで書き換えない。出力は entities/concepts/INDEX.md への commit(論理単位ごと、push は保留)。トリガーは大規模リファクタ直後・20〜30 セッション蓄積時・ユーザー指示。安価〜中位モデルで回す(上位モデルは [[skill-vault-synthesis]] に温存)。

## 関連

- [[playbook-obsidian-vault]] — 維持ループでの位置づけ(週次 lint)の定義元
- [[skill-vault-compile]] — 日次 compile の出力を週次で lint する関係
- [[graph-health-metric]] — リンク密度点検の指標定義
- [[single-source-dedup]] — 重複排除の判定原則

出典: [`.claude/skills/memory-dream/SKILL.md`](../raw/source-snapshot/dot-claude/skills/memory-dream/SKILL.md)
