---
name: morning-triage
description: 毎朝のデイリー自動実行(cron 等)から呼ばれる triage スキル。CI失敗・新規issue・昨日のcommitを読み、今日worktreeに値する候補だけを選び ./state/triage.md に記録し、次の worktree への引き継ぎを出力する。トリガー:デイリー自動実行から invoke。
---

# morning-triage（発見: Discovery のトリアージ）

このスキルはループの「発見」段階を担う。人間が候補リストを渡すのではなく、ループ自身に候補を発見・選別させる。

## Read

<!-- 発見の入力。ここに列挙したコマンドの出力が、今日の判断材料のすべてになる -->

- 直近のCI失敗: `gh run list --status failure --limit 20`
- 直近24時間のissue: `gh issue list --search "created:>=$(date -d '24 hours ago' +%Y-%m-%d)"`
  <!-- change: date コマンドはOSにより差異あり。macOS(BSD date)なら `date -v-24H` に置き換える -->
- 昨日以降のcommit: `git log --since="24 hours ago" --oneline --all`
- 前回のtriage結果: `./state/triage.md`（存在すれば読み込み、今回との差分・継続候補を把握する）

## Judge

<!-- ループの天井。ここで絞り込まないと worktree が無限に増える -->

読み取った候補それぞれについて、以下を自問して判定する（リストを渡すのではなく、ループ自身に選ばせる）:

- **今すぐ着手可能か、それともノイズか**: 再現手順・原因の当たりがあるか。情報不足で着手不能なものはノイズとして落とす。
- **リリースをブロックするか → P0**: mainブランチのビルド破壊、本番障害、セキュリティ関連は最優先。
- **既に追跡済みか → skip**: `./state/triage.md` に同一finding（source一致）が既にあり status が `open`/`in_progress` なら重複起票せず skip。
- 今日 worktree を1つ切る価値があるものだけを残す。すべてを残そうとしないこと（天井を超えたら翌日に回す）。

## Write

`./state/triage.md` に以下の形式で追記し、commit する（追記のみ。既存行は書き換えず、statusの更新のみ許可）。

```
| finding | source | priority | status |
|---|---|---|---|
| <一行要約> | <gh run/issue/commit へのURLまたはID> | P0/P1/P2 | open |
```

```bash
git add ./state/triage.md
git commit -m "triage: $(date +%Y-%m-%d) の候補を記録"
```

## Handoff

Judge で残した finding ごとに、次のフェーズ（委任）が読み取れる形式で出力する:

```
worktree=fix/<slug>
goal=<stop-condition>
```

- `<slug>` は finding を要約した短い識別子（例: `fix/ci-flaky-login-test`）。
- `<stop-condition>` は「いつ止めるか」を明確に書く（例: `テスト3件が緑になったら停止。それ以上のリファクタはしない`）。

## Stop

<!-- 唯一の非定型セクション。ここだけは判断ではなく禁止事項として固定する -->

- **never merge**: このスキル自身は何もmergeしない。
- **never delete**: 既存ファイル・ブランチ・stateの過去行を削除しない。
- **never push to main**: 作業は必ず `fix/<slug>` などの別worktree/別ブランチで行う。
- **不確実なものは `./inbox/` へ**: 自信が持てないfinding、判断がつかないもの、人間の確認が要るものはissue化やPR化せず `./inbox/` に置き、人間のレビューに委ねる。PRにしない。
