# vault-demo — claude_code を模した Obsidian Vault(実験)

このリポジトリ(playbook / Skill / script 置き場)の中身を、`notes/playbook/obsidian-vault.md` が定める Vault 構造(raw / entities / concepts / INDEX.md / NOW.md)へ移行できるかを検証する実験。**プロダクションの記憶階層でも Skill 定義でもない。** 消したければ `experiments/vault-demo/` を丸ごと削除すれば元に戻る。

## 「同じ GitHub 上に作ると汚染されるか」への答え

**隔離すれば汚染されない。** 汚染経路は 3 つに限られ、いずれもこの配置で塞いである:

1. **自動ロード汚染**: Claude Code が毎セッション読むのはプロジェクトルート/ホームの `CLAUDE.md` `AGENTS.md`。このデモはトップレベルにそれらを置かず、`NOW.md` `INDEX.md` もサブフォルダ内に閉じ込めた。リポジトリのルートで作業する限り、デモの中身はロードされない。
2. **Skill トリガー汚染**: Skill は `.claude/skills/` にしか無い。デモは `.md` の集合で Skill を増やさないので、`vault-compile` 等が誤発火する余地は無い。
3. **記憶/履歴汚染**: このリポジトリを `memory-dream` の対象と見なす場合でも、`experiments/` は `specs/` や `raw/` と同格の **dream 対象外**(素材・実験の地層)として扱う。git 的には 1 フォルダなので、実験コミットは後から綺麗に revert / 削除できる。

守るべき 3 条件(このデモが従っているもの): ①専用サブフォルダに隔離、②トップレベルに `CLAUDE.md`/`AGENTS.md`/`INDEX.md`/`NOW.md` を置かない、③実験と分かるコミット単位で、いつでも削除可能に保つ。

## この Vault の構成

```
vault-demo/
├── raw/source-snapshot/   # 元リポジトリ 9 ファイルの無加工スナップショット(ground truth。触らない)
├── entities/              # 成果物 1 つ 1 ページ(Skill / script / hook / playbook)
├── concepts/              # 設計原則 1 つ 1 ページ(playbook から抽出)
├── NOW.md                 # 現在の焦点(20 行以内)
├── INDEX.md               # 玄関 + タグ固定スキーマ
└── verify_links.py        # wikilink 健全性・INDEX 同期・孤立ノート・リンク密度の検証
```

移行の検証観点(playbook の書き込み/健全性ルールに対応): 全ソースが raw/ に入る・entities/concepts へコンパイルできる・`[[wikilink]]` が全解決する・INDEX が実ファイルと同期・タグが固定スキーマに収まる・リンク密度が測れる。

検証結果は本ファイル末尾「検証結果」に記録する。
