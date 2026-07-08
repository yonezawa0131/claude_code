# skill-session-compound

セッション終了時に、そのセッションで得た教訓・検証済み事実・未解決の仮説をvault(またはSTATE.md)と該当Skillへ書き戻すSkill。

#type/skill #domain/memory #layer/procedure

## 何をするか

自己改善システムの複利は「層3(記憶)への書き戻し」で閉じる — 書かずに終えたセッションの次はゼロから再出発になる([[state-file-discipline]]の「Write before walking away」をセッション終了時の定型手順にしたもの)。セッションを振り返り、確定事項・失敗の調査/検証状況・蒸留できる教訓・未解決の仮説・再開ポインタを抽出し、[[five-stage-memory]]の5段階(fail→investigate→verify→distill→consult)のどこまで到達したかで仕分ける。検証していない推測を「検証済みの事実」として書かない。プロジェクト固有の検証済み知見はvaultのentities/concepts(またはSTATE.mdのVerified facts/General rules)へ、未解決の仮説はNOW.md「未解決の仮説」(またはOpen failures)へ、作業の種類に紐づく手続き的教訓は該当Skillの Known failure modes / Anti-patterns 節へ書き戻す([[skill-compounding]]の判定をそのまま実行する)。日次のraw/新着を整理する[[skill-vault-compile]]とは対象が異なり、こちらは**いま終わろうとしているセッション自体**から抽出する。

## 入出力・使いどころ

入力はセッションの会話・作業内容。出力はvaultのentities/concepts/NOW.md(またはSTATE.md)、および該当Skill本体への追記。書き込んだ内容は、このセッションの推論過程を渡していない独立検証subagent([[verifier-subagent]])に見せ、推測が事実の置き場に混入していないかをチェックさせてから確定する。変更はdiffで提示し、論理単位ごとにcommit可能な粒度に分け、pushはユーザー明示指示まで保留する。トリガーは「セッションを締めて」「compoundして」「教訓を書き戻して」等、または大きな作業単位の完了時・セッション終了前。

## 関連

- [[state-file-discipline]] — 書き戻しが実行する運用律の定義元
- [[skill-compounding]] — Skillへの書き戻し判定の定義元
- [[five-stage-memory]] — 仕分け基準そのものの定義元
- [[verifier-subagent]] — 独立検証手順の定義元
- [[skill-vault-compile]] — 対になる日次compileとの対比

出典: [`.claude/skills/session-compound/SKILL.md`](../raw/source-snapshot/dot-claude/skills/session-compound/SKILL.md)
