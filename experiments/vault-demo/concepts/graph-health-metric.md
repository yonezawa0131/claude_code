# グラフのリンク密度が唯一の健全性メトリクス

vault が生きているかはファイル数ではなくグラフで測る。1 ノートあたりの接続数(リンク密度)が上がり続けていれば生きている。

#type/concept #domain/vault #layer/rule

## 主張

健全性の指標を 1 つに絞る: **リンク密度**。ファイルは増えるのに接続が増えないなら、それは second brain ではなく倉庫。星屑だけの美しいグラフは死んでいる。星が増えているだけか、星座が結ばれているかを見る。

- **定点観測**: 月に一度 5 分、Obsidian のグラフビューを見る。孤立ノートの増加は倉庫化の兆候。
- **lint と対で運用**: [[skill-memory-dream]] の lint(孤立ノート検出)と対にし、リンク密度が前回から下がっていないか点検する。
- **繋ぐ規律が支える**: この指標は [[backlink-discipline]](最低 3 本・1 本は古い層)を守ることでのみ上向く。

## 関連

[[playbook-obsidian-vault]] / [[backlink-discipline]] / [[maintenance-loop]] / [[skill-memory-dream]]

[出典](../raw/source-snapshot/notes/playbook/obsidian-vault.md)
