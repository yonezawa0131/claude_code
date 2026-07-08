# playbook-model-effort

モデル選択と effort 設定の使い分け判断手順を定めるこのデモの参照 playbook。

#type/playbook #domain/model #layer/rule

## 何をするか

Claude Code のモデル設定と effort 設定がそれぞれ実際に何を制御するか(モデル = 凍結された重み一式・能力、effort = 完了と見なすまでの徹底度)を仕組みから説明し、結果に不満なときにどちらのツマミを触るべきかの判断手順を定義する。設定を触る前にコンテキストを疑う・effort はタスク毎でなく一般的な好みとして設定する・ルーチンは小さいモデルへ落とす、といった規律を規定する。

## 入出力・使いどころ

vault 維持ループのモデル tier 分け([[maintenance-loop]] の表: compile = 安価モデル、synthesis = 上位モデル)や、チーム運用(頭脳/手足の役割分担)のモデル選択・effort 設定判断の一次情報として参照する。「うまくいかない → まず Skill / playbook / プロンプトを直す」を第一手にし、effort・モデル変更は第二手とする方針もここに定義される。

## 関連

- [[model-vs-effort]] — この playbook から抽出した設計原則
- [[playbook-obsidian-vault]] — vault 設計全体の定義元(モデル tier 分けの適用先)
- [[maintenance-loop]] — compile/synthesis のモデル tier 分けの適用例

出典: [`notes/playbook/model-effort-selection.md`](../raw/source-snapshot/notes/playbook/model-effort-selection.md)
