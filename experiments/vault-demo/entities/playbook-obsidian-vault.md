# playbook-obsidian-vault

Obsidian vault(second brain)の構造・書き込み境界・維持ループを定めるこのデモの設計元 playbook。

#type/playbook #domain/vault #layer/rule

## 何をするか

vault を raw/(人間が書く ground truth)・entities/concepts(AI が整理する compiled 層)・reviews/(AI が書く日付付き記録)・NOW.md・INDEX.md に分ける構造を定義する。書き込みルール(1 ファイル 1 教訓・重複禁止・タグ固定スキーマ・バックリンク最低 3 本・出典規律)と、日次 compile → 週次 lint → 週次 synthesis の維持ループ、健全性指標(リンク密度)を規定する。

## 入出力・使いどころ

このデモの entities/concepts ページはすべてこの playbook のルールに従って作られる。実行主体は [[skill-vault-compile]](日次)・[[skill-memory-dream]](週次 lint)・[[skill-vault-synthesis]](週次 synthesis)。

## 関連

- [[write-boundary]] — raw/ と compiled 層の書き込み境界の原則
- [[maintenance-loop]] — 日次/週次の自動維持ループの原則
- [[graph-health-metric]] — リンク密度による健全性測定の原則
- [[backlink-discipline]] — バックリンク最低本数規律の原則

出典: [`notes/playbook/obsidian-vault.md`](../raw/source-snapshot/notes/playbook/obsidian-vault.md)
