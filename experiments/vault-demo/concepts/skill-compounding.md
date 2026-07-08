# skill-compounding

教訓はSkillに書き戻す。状態ファイル=プロジェクト記憶、Skill=手続き記憶。定義は1箇所、他方はポインタ。

#type/concept #domain/memory #layer/rule

## 主張

状態ファイルは**プロジェクト記憶**(そのプロジェクトと共に死ぬ)、Skillは**手続き記憶**(「この種の作業のやり方」— プロジェクトを跨いで持ち運ぶ)。非自明な失敗のたびに、教訓を該当Skill自体に書き込む。

- **Skillは育つ**: 数週間複利したSkillには新しいセクションが生える — **Known failure modes(既知の失敗モード)・Anti-patterns(やってはいけないこと)**。静的な手順書から「実際に学んだことの蓄積記録」に変わる。
- **書き戻しの判定**: その教訓は (a) このプロジェクト固有の事実か → vault/STATE、(b) 作業の種類に紐づく手続き的知見か → Skill。両方に跨るなら両方書くが、**定義は1箇所・他方はポインタ**にする([[single-source-dedup]]と同じ原則をSkillとvaultの間に適用したもの)。

[[skill-session-compound]]がこの判定と書き戻しをセッション終了時の定型手順にしたもの。

## 関連

[[single-source-dedup]] / [[state-file-discipline]] / [[skill-session-compound]] / [[five-stage-memory]] / [[playbook-self-improving-system]]

[出典](../raw/source-snapshot/notes/playbook/self-improving-system.md)
