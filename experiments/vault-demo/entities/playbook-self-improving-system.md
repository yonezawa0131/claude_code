# playbook-self-improving-system

エージェントを「毎回ゼロから指示する道具」ではなく「走るたびに賢くなるシステム」として運用するための8原則を定める新設playbook。

#type/playbook #domain/agent #layer/rule

## 何をするか

自己改善(self-improving)をself-learning(重みの更新)と切り離し、モデルを取り巻く環境(記憶・Skill・検証ループ)が走るたびに鋭くなる性質として定義する。中核は複利スタック4層1ループ([[compound-stack]])と、それを回す8原則: 独立検証([[verifier-subagent]])・5段階記憶([[five-stage-memory]])・状態ファイル規律([[state-file-discipline]])・Skillへの書き戻し([[skill-compounding]])・モデルルーティング([[model-routing]])・worktree分離による並列安全性・スケジュール起動・視覚検証と安全境界のフォールバック設計。アンチパターンとして、独立検証者なしの自己批判・状態ファイルなし・書き込まれないSkill・定型作業の上位モデル送り・客観的停止条件のないループ・分類器ブロックのsilent failure等を挙げる。

## 入出力・使いどころ

新レイヤは増やさず、既存の部品を「自己改善ループの4層」として位置づけ直す。既存設計とのマージ: STATE.md構造は**[[playbook-obsidian-vault]]のvaultが代替**(新設しない)、eval loop/rubricは**[[skill-memory-dream]]のlint+採用前レビュー**、morning briefingは**[[skill-vault-compile]]の早朝cron**、Skill書き戻しは**[[skill-session-compound]](本playbookと同時に新設)**が担う。

## 関連

- [[compound-stack]] — 本playbookの中核概念、4層1ループの定義元
- [[verifier-subagent]] — 原則1(独立検証者)の定義元
- [[five-stage-memory]] — 原則2(5段階記憶)の定義元
- [[state-file-discipline]] — 原則3(状態ファイル)の定義元
- [[skill-compounding]] — 原則4(Skillへの書き戻し)の定義元
- [[model-routing]] — 原則5(モデルルーティング)の定義元
- [[playbook-obsidian-vault]] — STATE.mdの代替先であるvault設計の定義元
- [[skill-session-compound]] — 原則3・4を運用手順化したSkill

出典: [`notes/playbook/self-improving-system.md`](../raw/source-snapshot/notes/playbook/self-improving-system.md)
