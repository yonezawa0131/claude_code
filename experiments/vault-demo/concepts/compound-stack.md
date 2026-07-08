# compound-stack

複利スタック: Primitives→Orchestration→Memory→Self-improvement の4層1ループ。層4が層1の出力を採点・蒸留し層3へ書き戻すことで複利が閉じる。

#type/concept #domain/agent #layer/rule

## 主張

自己改善システムは下から積む4層でできている。

| 層 | 中身 |
|---|---|
| 1. Primitives | モデル・subagent・worktree・ツール |
| 2. Orchestration | 自己修正ループ・スケジュール起動 |
| 3. Memory | 状態ファイル・Skill・教訓の蓄積 |
| 4. Self-improvement | 独立検証・eval・ルール蒸留・書き戻し |

複利になる理由はただ一つ: 層1の出力が層4で採点・蒸留され、層3に書き戻される。翌日の層1は昨日より鋭い記憶とSkillを継承して走る。**モデルはステートレスだが、システムはステートフル。** どれか1層が欠けるとループが閉じない — 特に層3への書き戻しが無いと、毎セッションが「再開」ではなく「再出発」になる。

層4の実体は独立検証([[verifier-subagent]])と5段階記憶の蒸留([[five-stage-memory]])、書き戻し先はSkill([[skill-compounding]])と状態ファイル([[state-file-discipline]])。層2のスケジュール起動は[[maintenance-loop]]がvaultへ適用した形。

## 関連

[[verifier-subagent]] / [[five-stage-memory]] / [[state-file-discipline]] / [[skill-compounding]] / [[maintenance-loop]] / [[playbook-self-improving-system]]

[出典](../raw/source-snapshot/notes/playbook/self-improving-system.md)
