---
name: ingest-to-vault
trigger: file "vault の raw/ 配下への新規ファイル投入（現状は投入後に手動 /autopilot）"
executor: sonnet
output: vault の entities/・concepts/（新規 or 追記）
boundaries:
  allow:
    - "<vault>/entities/**"
    - "<vault>/concepts/**"
    - "<vault>/INDEX.md"
  deny:
    - raw/ への書き込み・リネーム・削除（ground truth。読み取りのみ）
    - reviews/ への書き込み
    - 既存ページの大規模書き換え（追記・リンク接続まで。再構成は memory-dream の仕事）
    - 外部送信・公開
  commit: true
  push: false
verify:
  - 新規・変更された各ページに raw/ への出典リンク（[[wikilink]] または相対パス）が 1 つ以上ある
  - 新規ページが INDEX.md に 1 行説明付きで追加されている
  - raw/ 配下のファイルに変更がない（git diff で実測）
  - 追加された [[wikilink]] のリンク先が実在する（意図的な forward reference は本文にその旨の注記がある）
---

# ingest-to-vault — 二次脳への取り込み

## 目的

raw/ に放り込んだ素材（会話エクスポート、記事、メモ）を、放置せずその日のうちに vault のコンパイル済み知識（entities / concepts）へ接続する。「保存したが二度と読まないフォルダ」を作らない。

## 手順

1. vault の場所を特定する（`notes/playbook/obsidian-vault.md` と memory-dream Skill の「作業対象の特定」と同じ解決順）。特定できなければ止めて報告。
2. `raw/` 配下で、entities/concepts のどこからもリンクされていない未取り込みファイルを列挙する（INDEX.md・既存ページからの参照を grep で実測）。
3. 未取り込みファイルごとに:
   - 内容を読み、既存の entities / concepts ページに関連があれば**追記 + 出典リンク**で接続する
   - 該当ページがなく、独立した概念・エンティティとして立つ内容なら新規ページを作る（vault playbook の書式に従う）
   - どちらにも値しない断片は取り込まず、報告に「スキップ + 理由」で列挙する
4. 新規ページを INDEX.md に 1 行説明付きで追加する。
5. 取り込み 1 件ごとを目安に論理単位で commit する。

## 補足

- 迷ったら「小さく接続」を優先する。ページの再構成・統合は週次の memory-dream に任せる。
- 同じ素材が既に取り込み済みに見える場合は上書きせず、報告で重複の可能性を指摘する。
