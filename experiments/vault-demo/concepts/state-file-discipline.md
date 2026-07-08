# state-file-discipline

状態ファイルの規律: セッションは書き込みで終え(Write before walking away)、読み込みで始める(Read at session start)。

#type/concept #domain/memory #layer/rule

## 主張

5段階記憶([[five-stage-memory]])は頭の中のモデルで、状態ファイルは各段階の出力の置き場。運用律は2つだけ:

- **Write before walking away**: セッションは必ず状態の書き込みで終える(何を試し・何が通り・何が落ち・どのルールが生き残ったか)。書かずに終えたセッションの次はゼロから再出発になる。
- **Read at session start**: セッションは状態の読み込みで始める。読み込みを省くと、蓄積があっても参照されず、複利が消える。

元記事の STATE.md は5セクション(Verified facts / General rules / Open failures / Lessons learned / Last session)構成だが、**このvaultではSTATE.mdを新設しない**。vaultが既に同じ役割を分担しているため(重複させると[[single-source-dedup]]に反する):

| STATE.md のセクション | vault での対応 |
|---|---|
| Verified facts | entities/ concepts/(出典リンク付きの検証済み知識) |
| General rules | concepts/(1ファイル1教訓) |
| Open failures | NOW.md「未解決の仮説」 |
| Lessons learned | concepts/ + 該当Skillへの書き戻し |
| Last session | NOW.md「直近の決定」+ reviews/ |

vaultを持たないプロジェクトでは、プロジェクトルートに上記5セクションのSTATE.mdを1枚置くのが最小構成。書き込み手順そのものは[[skill-session-compound]]が担う。

## 関連

[[five-stage-memory]] / [[now-md-context-load]] / [[skill-session-compound]] / [[single-source-dedup]] / [[playbook-self-improving-system]]

[出典](../raw/source-snapshot/notes/playbook/self-improving-system.md)
