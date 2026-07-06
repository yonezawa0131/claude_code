# 書き込み境界

raw/ は人間(と取込スクリプト)の不可侵な地層、entities/ concepts/ reviews/ NOW.md は AI が書く層。この線引きが最重要の設計原則。

#type/concept #domain/vault #layer/rule

## 主張

書き込み権限をフォルダで固定する。raw/ はエージェントが読むだけ、compiled 層(entities/ concepts/ reviews/ NOW.md)だけを書き換える。境界が曖昧だとエージェントは「改善」ではなく「どこに何を書くべきかの解釈」にコストを費やす。線が明確なら即座に作業へ入れる。

## なぜ raw を書き換えないか

- **磨耗**: 同じノートを読んで書き直すサイクルを繰り返すと詳細が磨耗する。
- **複利誤り**: 書き換えのたびに紛れた誤りが次サイクルの入力になり、複利で増える。
- **再コンパイル保険**: compiled 側が壊れても、無加工の raw から再コンパイルできる。3 年後に「システムが解釈した内容」ではなく「自分が実際に言ったこと」を読み返せる。

raw の清書版が要るなら raw/ を触らず compiled 側へ書く。

## 関連

[[playbook-obsidian-vault]] / [[pay-per-read]] / [[capture-friction]] / [[single-source-dedup]] / [[script-export-to-obsidian]]

[出典](../raw/source-snapshot/notes/playbook/obsidian-vault.md)
