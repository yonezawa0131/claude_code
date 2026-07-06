# script-export-to-obsidian

claude.ai の会話エクスポート(zip/conversations.json)を vault の raw/ClaudeChat Memory/ へ変換するスクリプト。

#type/script #domain/import #layer/tool

## 何をするか

`scripts/claude_export_to_obsidian.py <export.zip|conversations.json> --vault <path>` で実行する。1 会話 = 1 Markdown(frontmatter に title/uuid/created/updated/messages/tags)を `raw/ClaudeChat Memory/` に生成し、全会話への索引 `_Index.md` を月別に再生成する。照合キーは uuid のため再実行は冪等(同一会話は上書き、タイトル変更時は旧ファイルを差し替え)。標準ライブラリのみで動作。

## 入出力・使いどころ

入力は claude.ai の「設定 → プライバシー → データをエクスポート」の zip または展開済み JSON。出力先の `raw/ClaudeChat Memory/` は raw/ の一部(無加工の ground truth)であり、本スクリプトだけが上書き管理する — 人間の手編集やエージェントの書き換えは対象外。生成物は [[skill-vault-compile]] が読む素材になる。

## 関連

- [[playbook-obsidian-vault]] — raw/ の書き込み境界(この場所だけ取込スクリプトが書く)の定義元
- [[skill-vault-compile]] — この出力を読んで entities/concepts へコンパイルする側
- [[single-source-dedup]] — uuid 照合による冪等性・重複防止の設計
- [[capture-friction]] — エクスポートを自動変換することで capture 摩擦を下げる経路

出典: [`scripts/claude_export_to_obsidian.py`](../raw/source-snapshot/scripts/claude_export_to_obsidian.py)
