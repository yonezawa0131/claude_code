# model-routing

役割でモデルを分ける: Orchestrator(最上位)/ Worker(中位)/ Grader(安価)/ Fallback。上位モデルが席代を稼ぐのは蒸留と判断。

#type/concept #domain/agent #layer/rule

## 主張

全工程に最上位モデルを使わない。デフォルトではなくタスクの複雑さで振り分ける。

| 役割 | 仕事 | tier |
|---|---|---|
| Orchestrator(頭脳) | 計画・分割・subagentへの委譲・証拠からのルール蒸留・最終判断 | 最上位 |
| Worker(手足) | 定型の大量作業: compile・リファクタ・scaffold・ドキュメント更新 | 中位 |
| Grader(検証者) | 独立コンテキストでの採点・分類・lint判定 | 安価 |
| Fallback | 上位モデルが安全分類器で辞退する領域の受け皿 | 最上位 |

**上位モデルが席代を稼ぐのは「蒸留と判断」であって「大量の手」ではない。** [[maintenance-loop]]のtier分け(ルーチンは安価に、上位が席代を稼ぐのはsynthesisだけ)は、この一般則をvault作業に適用した特殊形。検証(Grader役)を安価モデルに任せる判断は[[verifier-subagent]]と表裏一体。

## 関連

[[maintenance-loop]] / [[verifier-subagent]] / [[compound-stack]] / [[playbook-self-improving-system]]

[出典](../raw/source-snapshot/notes/playbook/self-improving-system.md)
