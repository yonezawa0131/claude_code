# state.md（永続化: ループのメモリ）

<!--
このファイルはループそのものの記憶である。
このファイルは必ず repo に commit すること。commitしないと、
翌朝クラウドランナー上で新しく起動するループからは何も見えず、
毎日ゼロから発見をやり直すことになる。
-->

## triage

<!--
最低4列: finding / source / priority / status
- finding が無い   → 何を見つけたか分からない
- source が無い    → 出所を監査できない（なぜこれが候補になったのか追跡できない）
- priority が無い  → 仕事を順序付けできない（次に何をやるべきか毎回考え直しになる）
- status が無い    → 翌日のループがバトンを受け取れない（同じfindingを二重に起票する）
-->

| finding | source | priority | status |
|---|---|---|---|
| ログインテストがCIで断続的に失敗する | gh run:12345678 | P0 | in_progress |
| `/api/users` が空配列で500を返す | issue:#482 | P1 | open |
| README のセットアップ手順が古い | commit:a1b2c3d | P2 | done |

<!--
change: 上記3行はサンプル。実運用では初回導入時に空テーブル(ヘッダー行のみ)から始めてよい。
-->

## 拡張列（必要に応じて追加）

<!--
運用が進むと基本4列だけでは足りなくなることが多い。以下は追加してよい代表例:

- last_seen    : このfindingを直近で観測した日時(ISO8601)。同一findingの再発を検知するのに使う。
- retry_count  : このfindingに対して過去に何回worktreeを切って再挑戦したか。MAX_RETRIESと突き合わせる。
- assigned_to  : どのworktree/ブランチ/エージェントが現在このfindingを担当しているか(例: fix/ci-flaky-login-test)。
-->

| finding | source | priority | status | last_seen | retry_count | assigned_to |
|---|---|---|---|---|---|---|
| ログインテストがCIで断続的に失敗する | gh run:12345678 | P0 | in_progress | 2026-07-06 | 1 | fix/ci-flaky-login-test |

<!--
change: 拡張列を増やす場合は、morning-triage.SKILL.md の Write セクションが出力するテーブル定義も
併せて更新すること(スキーマがずれると追記時にパースできなくなる)。
-->
