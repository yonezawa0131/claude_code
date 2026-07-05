# compact 最適化（compact-prep skill + 2 段 hook + 閾値通知）

参考記事「Claude Code の compact で作業状態が壊れる問題への対策」の要約と、本リポジトリへの採用判断の記録。

## 記事の要約

### 問題: 標準 compact の構造的欠陥

Claude Code の compact（手動 `/compact` / 自動: 使用率 90〜95% 近辺で発火）は、会話履歴を LLM に自然文要約させて context を再構築する。要約は「何をやったか」の物語であり、次の情報が構造的に落ちる:

- **判断構造**: なぜその案を採用したか / どの案をなぜ却下したか / 今どのフェーズか
- **セッション状態**: plan mode / worker 委譲 / タスクツリー

かつ非可逆（圧縮後は raw ログに戻れない）。結果として compact 直後に典型 4 事故が起きる:

1. **検証前デプロイ** — 「検証してから配置」の順序制約が要約から落ち、いきなり破壊的操作に入る
2. **却下済みアプローチの再実行** — 要約が却下案を「試みた手順」として残すため、同じ失敗を再度踏む
3. **設計原則の失念** — 「配置先を直接編集せず管理元 repo から配布」等のセッション中に確立した原則が消える
4. **タスク目的の取り違え** — 固定していたテスト目的が落ち、周辺調査に脱線する

### 対策: 3 点セット

1. **compact-prep skill** — `/compact` 前にユーザーが明示的に叩き、要約に載りにくい判断構造・セッション状態だけを固定パスの state file (`${TMPDIR}/claude-compact-state/<session_id>.md`) へ固定フォーマットで保存する。Hard gate（session_id 不明なら推測名で作らない）・Forcing function（保存後に読み返して見出し欠落を検知）・allowed-tools 絞り込みで「書いたつもり」を潰す。
2. **PostCompact + UserPromptSubmit の 2 段 hook** — PostCompact は additionalContext を返せないため、PostCompact が marker file を書き、次の UserPromptSubmit が marker を検出して復旧指示（state file を読め / 圧縮サマリーの next step は仮説として扱え 等）を additionalContext で注入し marker を消す（one-shot）。hook 間の通信路は file system 上の marker のみ。全 hook fail-open（常に exit 0）。
3. **閾値通知（記事では 60%）** — 自動 compact に先を越されると state file を保存できないため、statusline が使用率閾値超過で warn marker を書き、UserPromptSubmit hook が「/compact-prep を提案せよ」を注入する。cooldown marker で二重通知を防ぎ、PostCompact が cooldown をリセットする。60% は 1M context 前提の値（200K なら 80% 台に上げる）。

記事の効果: 1 セッション 10 回 compact しても論理破綻なし。却下案の再提案・plan mode 喪失・worker topology 忘却が消えた。

## 本リポジトリでの実装と採用判断

### 採用（ほぼそのまま）

| 記事の部品 | 本リポジトリでの実体 |
|---|---|
| compact-prep skill | `.claude/skills/compact-prep/SKILL.md` |
| PostCompact marker hook | `.claude/hooks/compaction-recovery.sh` |
| UserPromptSubmit 復旧注入 + 閾値通知注入 | `.claude/hooks/userpromptsubmit-compact.sh`（下記のとおり統合） |
| statusline の閾値分岐 | `.claude/hooks/statusline.sh` |
| settings.json hook 登録 | `.claude/settings.json`（project scope、`$CLAUDE_PROJECT_DIR` 経由） |

marker 3 種（`claude-compact-warn` / `claude-compact-warned` / `claude-compacted`）の設計、one-shot 消費、fail-open、単一責務の分業は記事のまま。

### 変更・補完した点

- **UserPromptSubmit hook を 1 本に統合**: 記事は復旧注入と閾値通知を別スクリプトにしていたが、毎ターン jq を 2 回起動するコストと登録の煩雑さを避けるため 1 スクリプトに統合した（評価順: session pointer 記録 → 復旧注入 → 閾値通知。additionalContext を出すのは高々 1 つ）。
- **`get-session-id.sh` を新規実装**: 記事が参照するだけで実体を載せていなかった部品。Claude Code は Bash tool に session_id を渡さない（`CLAUDE_SESSION_ID` 環境変数は存在しない。公式推奨は hook stdin JSON の `session_id`）。そこで UserPromptSubmit hook が毎ターン `${TMPDIR}/claude-session-id/by-cwd/<cksum(cwd)>` へ pointer を書き、`scripts/get-session-id.sh` が cwd キー → 最新 pointer の順で逆引きする。スキル実行はそれ自体が user prompt なので、スキルが走る時点で必ず pointer が存在する。
- **context 使用率は公式フィールドを使用**: statusline の stdin JSON に `context_window.used_percentage` が公式に存在するため、自前計算せずこれを読む。statusline 自体もこのリポジトリには無かったので、表示（モデル / ディレクトリ / ctx%）込みの最小実装を新規作成した。
- **閾値を環境変数化**: `COMPACT_WARN_THRESHOLD`（デフォルト 60）。1M context 前提の値なので、200K context 運用では settings.json の `env` で 80 程度に上げる。
- **復旧指示に安全弁を追加**: state file が存在しない（compact-prep 未実行のまま自動 compact された）ケースで「推測せずユーザーに確認せよ」を注入。破壊的操作（デプロイ・上書き・削除）前の前提検証も明示。
- **閾値通知にサブエージェント委譲の指示を追加**（下記）。

### 検証済みの仕様（2026-07 時点の公式ドキュメント）

- `PreCompact` / `PostCompact` イベントは存在する（matcher: `manual` / `auto`）。`SessionStart` にも `compact` matcher がある。
- additionalContext を確実に返せるのは `UserPromptSubmit` と `SessionStart`。PostCompact の additionalContext サポートは明記されていないため、記事どおり marker → UserPromptSubmit の 2 段構成を採る。
- 全 hook は stdin JSON で `session_id` / `transcript_path` / `cwd` を受け取る。
- 将来の簡略化候補: `SessionStart` (matcher: `compact`) は additionalContext を返せると明記されているので、2 段 marker 方式を 1 hook に畳める可能性がある。ただし記事の方式は実戦で安定実績があるため、まず現行構成で運用し、動作を確認してから移行を検討する。

## token 最適化: orchestrator + サブエージェント委譲

compact の頻度自体を下げる最も効く手段は、main context に読み込む量を減らすこと。方針:

- **main セッション（司令塔）は判断と統合に徹する**。大量のファイル読み・探索・ログ解析・定型実装は Task tool のサブエージェント（Explore / general-purpose。モデルは sonnet や haiku で足りることが多い）へ委譲し、**結果の要約だけ**を main context に受け取る。
- ドキュメント調査は `claude-code-guide` など専用エージェントに出す（本実装の仕様検証もこの方法で行い、doc 全文を main context に入れずに済んだ）。
- 閾値通知（60%）の additionalContext にもこの指示を含めてあり、残り 40% の消費ペースが自動的に落ちる。
- 委譲の判断基準: 「出力の大半を読み捨てる作業」（grep の試行錯誤、長いログの精査、複数ファイルの走査）はサブエージェント向き。「会話の文脈が要る判断」は main に残す。

## 運用フロー

1. 通常作業中、statusline に `ctx NN%` が常時表示される。
2. 使用率が閾値（デフォルト 60%）を超えた次のターンで、Claude が `/compact-prep` → `/compact` の実行を提案してくる。
3. 区切りの良いところで `/compact-prep` を叩く → state file 保存 → 「準備完了」報告。
4. `/compact` を叩く。
5. 圧縮後の最初のプロンプトで復旧指示が自動注入され、Claude が state file を読んで判断構造・セッション状態を復元する。
6. 自動 compact に先を越された場合も復旧注入は走る（state file 無しの縮退モード: 推測せずユーザーに確認する指示になる）。

## 制約・既知の注意点

- state file は `${TMPDIR:-/tmp}` 配下なので OS 再起動やリモートコンテナ再作成で消える。セッションをまたぐ永続記憶は memory-dream（agents-share）側の責務で、この仕組みは「同一セッション内の compact 前後」だけを守る。
- `get-session-id.sh` の cwd キーは、同一ディレクトリで並行セッションを走らせると後勝ちになる。並行運用時は最新 pointer フォールバックも誤りうるため、compact-prep の Hard gate（不明なら停止）に頼る。
- この settings.json は project scope。他リポジトリでも使う場合は hooks / scripts を `~/.claude/` へ配置し、コマンドパスを絶対パスに書き換える。
