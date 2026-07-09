# 成功条件駆動ループ(success-criteria-loop)

エージェントには手順を細かく命令せず、検証可能な成功条件と完了の定義を与え、テスト(検証手段)が通るまでループさせる。

#type/concept #domain/agent #layer/rule

## 主張

- **命令(手順)ではなく成功条件(ゴール)を渡す**。エージェントは具体的な目標に向かって反復するのが得意で、ゴールが検証可能なほど自律的に進める。「このバグを直して」ではなく「何を満たせば成功か」の列挙。
- **検証手段を先に置く**: コードならテストを先に書かせ、通るまで反復させる。テストはエージェントを自律的にするレール。vault 作業なら `verify_links.py` のような lint が同じ役割を果たす。
- **完了の定義(done_definition)を明示する**: 「関連テストが通っている / Lint が通っている / 変更点と未確認リスクが報告されている」のように、完了を主張してよい条件を先に固定する。
- **完了報告には証拠を要求する**: 実行したコマンド・通ったテスト・確認したファイル・未確認リスクを分けて報告させる。「更新した」という主張ではなく before/after(この vault の「変更は diff で提示」の一般形)。
- **作らせた後に削らせる**: ループの最終段に単純化レビュー(過剰な抽象化・不要コード・既存パターンとのズレを削る)を必ず挟み、最後に人間が読む。生成はエージェント、識別は人間。

## この vault への適用

Skill(vault-compile / vault-synthesis / memory-dream)のプロンプトは手順記述が中心。各 Skill に「完了の定義」(例: verify_links.py が通る・INDEX が実ファイルと同期・diff が提示されている)を 1 ブロック足すと、この原則に沿う。

## 関連

[[article-karpathy-claude-playbook]] / [[model-vs-effort]] / [[maintenance-loop]] / [[graph-health-metric]]

[出典](../raw/reading/2026-07-09-karpathy-claude-playbook.md)
