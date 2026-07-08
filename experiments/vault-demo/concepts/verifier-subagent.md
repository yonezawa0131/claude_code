# verifier-subagent

独立検証者は自己批判に勝る。自己選好バイアスは構造問題でプロンプトでは直らない。停止条件は検証者側に置く。

#type/concept #domain/agent #layer/rule

## 主張

作った本人に採点させない。自分の出力を評価するモデルは自分の推論の痕跡を見てしまい、既に書いた結論と整合する判定を好む(**自己選好バイアス**)。これは「頑張って批判する」で直る問題ではなく構造の問題なので、プロンプトでは直せない。

- **maker と verifier を分ける**: verifier には maker の推論過程を渡さず、成果物+判定基準(ルーブリック)だけ渡す。作り手の事情に肩入れさせない。
- **検証は安価なモデルで足りる**: 検証は分類・照合作業に近く、Haiku 級のモデルで十分なことが多い。上位モデルは maker 側([[model-routing]])に残す。
- **停止条件は検証者側に置く**: 「もう十分やった」で止まるループと「検証者が合格を出した」で止まるループは別物。停止条件は測定可能な形で書く(テストが通る・リンク切れゼロ・検出問題ゼロ等)。

[[skill-session-compound]] の独立検証手順、[[skill-memory-dream]] の採用前レビュー必須の運用は、いずれもこの原則の適用例。

## 関連

[[compound-stack]] / [[model-routing]] / [[skill-session-compound]] / [[skill-memory-dream]] / [[playbook-self-improving-system]]

[出典](../raw/source-snapshot/notes/playbook/self-improving-system.md)
