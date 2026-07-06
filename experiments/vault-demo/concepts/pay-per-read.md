# 読み取りコスト管理(pay-per-read)

読む量そのものがコスト。必要なページだけを開き、フォルダ全読みは日常セッションでは禁じ手にする。

#type/concept #domain/vault #layer/rule

## 主張

context window は有限の固定税なので、読み取りを設計対象にする。

- **CLAUDE.md は指すだけ**: vault の内容を貼り込まず vault を参照させる(200 行未満)。貼り込むと毎セッション自動ロードされる固定税になる。可変の現在文脈は [[now-md-context-load]] に外出しする。
- **INDEX → リンク → grep の順で絞る**: INDEX.md で存在を知り、`[[wikilink]]` を辿り、grep で絞り、必要なページだけ開く。
- **subagent に読ませ結論だけ受け取る**: 大きい問いは別コンテキストで 50 ページ読ませ、結論の 1 段落だけを受け取る。メインには決定を置き、図書館は置かない。
- **例外は全体横断パス**: lint / synthesis はタグ体系・リンク構造の全景が一度に文脈へ入るほど精度が上がるため、subagent に vault を広く読ませてよい。日常の pay-per-read と混同しない。

## 関連

[[playbook-obsidian-vault]] / [[now-md-context-load]] / [[write-boundary]] / [[maintenance-loop]] / [[skill-vault-synthesis]]

[出典](../raw/source-snapshot/notes/playbook/obsidian-vault.md)
