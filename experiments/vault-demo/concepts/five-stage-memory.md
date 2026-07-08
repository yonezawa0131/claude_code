# five-stage-memory

記憶が複利になるかは fail→investigate→verify→distill→consult のどこまで処理してから書き残すかで決まる。

#type/concept #domain/memory #layer/rule

## 主張

失敗の処理は5段階に分かれる。

1. **Fail** — 失敗を、後で使える詳細付きで記録する
2. **Investigate** — 先へ進む前に、なぜ失敗したかを突き止める
3. **Verify** — 診断を「推測」ではなく「確認済みの事実」に変える(実際にクエリを打つ・実行して確かめる)
4. **Distill** — 検証結果を、その事例を超えて効く一般ルールに蒸留する
5. **Consult** — 次のタスクで、事実を再導出せずルールを読む

段階1で止まった記憶は「失敗メモと未解決の推測のリスト」であり、溜まっても複利にならない。**書き残す前に「これは推測か、検証済みか」を自問し、推測は推測と明記して分離する。** このvaultでは[[now-md-context-load]]が管理するNOW.mdの「未解決の仮説」が推測置き場、concepts/が検証済みルール置き場という役割分担になる。

[[skill-session-compound]]はこの5段階を仕分け基準としてセッション終了時に使う手順そのもの。

## 関連

[[state-file-discipline]] / [[now-md-context-load]] / [[skill-session-compound]] / [[compound-stack]] / [[playbook-self-improving-system]]

[出典](../raw/source-snapshot/notes/playbook/self-improving-system.md)
