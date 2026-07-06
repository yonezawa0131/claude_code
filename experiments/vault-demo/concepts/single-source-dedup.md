# 定義は 1 箇所(重複排除)

各情報は定義箇所を一つに保つ。上位レイヤが定めるルールを下位で再掲しない。

#type/concept #domain/memory #layer/rule

## 主張

記憶階層は局所的に追記されるため、放置すると階層を跨いで同じ定義が重複する。重複は「思い出す助け」を「混乱させるノイズ」へ転落させる。

- **定義は 1 箇所**: 各情報の定義箇所を一つに保つ。上位(世界のルール)が定めるものは下位から単に消し、そのレイヤ固有の知見だけ残す。必要なら手順の所在を 1 句で指すに留める。
- **修正は下位側**: 重複は常に「下位 → 上位」方向で発生する。修正は下位レイヤで行い、最上位の自己整合な層は触らない。
- **メタを残さない**: 「ここでは再掲しない」等の重複回避の注記自体も成果ファイルに書かない。重複は黙って消す。理由が行動を変える技術的因果(A だと B が壊れるので C する)だけは知見として残してよい。

raw/ は素材の ground truth なので dedup の対象外([[write-boundary]])。

## 関連

[[playbook-memory-dream-pointer]] / [[skill-memory-dream]] / [[write-boundary]] / [[backlink-discipline]]

[出典](../raw/source-snapshot/dot-claude/skills/memory-dream/SKILL.md)
