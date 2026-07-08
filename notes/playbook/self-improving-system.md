---
name: self-improving-system
description: 自己改善するエージェントシステムの設計 — 複利スタック4層・独立検証者・5段階記憶・状態ファイル・Skill書き戻し・モデルルーティング
type: playbook
---

# 自己改善システム(self-improving agent system)の設計

エージェントを「毎回ゼロから指示する道具」ではなく「走るたびに次の走りが賢くなるシステム」として運用するための設計書。元ネタは Substack 記事「The 14-step roadmap to build the self-improving system Fable 5 was designed for」(原文: `experiments/vault-demo/raw/reading/2026-07-08-fable5-self-improving-system.md`)。記事の構造的な主張だけを取り込み、検証できない機能名・数値は末尾「採用しなかったもの」に隔離した。

中核の定義: **自己改善(self-improving)は self-learning(重みの更新)ではない。モデルは変わらない。モデルを取り巻く環境 — 記憶・Skill・検証ループ — が走るたびに鋭くなる。自己改善はモデルの性質ではなく、周囲に組むシステムの性質。** この点は `memory-dream` Skill の「consolidation は fine-tune ではなく記憶の再編。モデルは変えない」と同じ思想であり、本 playbook はそれをシステム全体へ一般化する。

## 複利スタック: 4 層 1 ループ

下から順に作る。レバレッジも下から順に複利になる。

| 層 | 中身 | このリポジトリでの実体 |
|---|---|---|
| 1. Primitives | モデル・subagent・worktree・ツール | Claude Code 本体、Agent tool、`isolation: worktree` |
| 2. Orchestration | 自己修正ループ・スケジュール起動 | cron / Routines(スケジュールトリガー)、Skill による定型化 |
| 3. Memory | 状態ファイル・Skill・教訓の蓄積 | Obsidian vault(`notes/playbook/obsidian-vault.md`)、`.claude/skills/` |
| 4. Self-improvement | 独立検証・eval・ルール蒸留・書き戻し | memory-dream(lint)、vault-synthesis、session-compound |

複利になる理由: 層 1 の出力が層 4 で採点・蒸留され、層 3 に書き戻される。翌日の層 1 は昨日より鋭い記憶と Skill を継承して走る。**モデルはステートレスだが、システムはステートフル。** どれか 1 層が欠けるとループが閉じない — 特に層 3 への書き戻しが無いと、毎セッションが「再開」ではなく「再出発」になる。

## 原則 1: 独立検証者は自己批判に勝る

作った本人に採点させない。自分の出力を評価するモデルは自分の推論の痕跡を見てしまい、既に書いた結論と整合する判定を好む(自己選好バイアス)。**別コンテキストの検証者は成果物とルーブリックしか見ない** — 作り手の事情に肩入れしない。これは「頑張って批判する」の問題ではなく構造の問題なので、プロンプトでは直せない。

実装: maker subagent と verifier subagent を分ける。verifier には maker の推論過程を渡さず、成果物+判定基準だけ渡す。検証は安価なモデル(Haiku)で足りることが多い。`memory-dream` の「採用前レビュー必須(dream 出力は hallucination 混入の懸念)」、`obsidian-vault.md` の外部リサーチ骨格(「リサーチしていない別コンテキストの懐疑エージェントが反証を試み、生存した主張だけ着地」)は、いずれもこの原則の適用例。

ループの停止条件も検証者側に置く: 「もう十分やった」で止まるループと「検証者が合格を出した」で止まるループは別物。停止条件は測定可能な形で書く(テストが通る・リンク切れゼロ・検出問題ゼロ等)。

## 原則 2: 5 段階記憶(fail → investigate → verify → distill → consult)

記憶が複利になるかは、失敗をどの段階まで処理してから書き残すかで決まる。

1. **Fail** — 失敗を、後で使える詳細付きで記録する
2. **Investigate** — 先へ進む前に、なぜ失敗したかを突き止める
3. **Verify** — 診断を「推測」ではなく「確認済みの事実」に変える(実際にクエリを打つ・実行して確かめる)
4. **Distill** — 検証結果を、その事例を超えて効く一般ルールに蒸留する
5. **Consult** — 次のタスクで、事実を再導出せずルールを読む

段階 1 で止まった記憶は「失敗メモと未解決の推測のリスト」であり、溜まっても複利にならない。**書き残す前に「これは推測か、検証済みか」を自問し、推測は推測と明記して分離する**(vault では NOW.md の「未解決の仮説」が推測置き場、concepts/ が検証済みルール置き場)。

## 原則 3: 状態ファイル — 記憶が実際に住む場所

5 段階は頭の中のモデルで、状態ファイルは各段階の出力の置き場。記事の STATE.md 構造は 5 セクション: Verified facts(段階3)/ General rules(段階4)/ Open failures(段階1–2)/ Lessons learned(段階4)/ Last session(段階5の再開ポインタ)。

**このリポジトリでは STATE.md を新設しない。vault が既に同じ役割を分担している**(重複させると single-source 原則に反する):

| STATE.md のセクション | vault での対応 |
|---|---|
| Verified facts | entities/ concepts/(出典リンク付きの検証済み知識) |
| General rules | concepts/(1 ファイル 1 教訓) |
| Open failures | NOW.md「未解決の仮説」 |
| Lessons learned | concepts/ +該当 Skill への書き戻し(原則 4) |
| Last session | NOW.md「直近の決定」+ reviews/(日付付き記録) |

vault を持たないプロジェクトでは、プロジェクトルートに上記 5 セクションの STATE.md を 1 枚置くのが最小構成。

ファイルが「複利する」か「ただ肥る」かを分ける運用律は 2 つだけ:

- **Write before walking away**: セッションは必ず状態の書き込みで終える(何を試し・何が通り・何が落ち・どのルールが生き残ったか)。書かずに終えたセッションの次はゼロから再出発になる。→ `session-compound` Skill(`.claude/skills/session-compound/SKILL.md`)がこの手順。
- **Read at session start**: セッションは状態の読み込みで始める。vault では NOW.md がこの用途(`obsidian-vault.md`「NOW.md(毎セッションの文脈ロード)」)。読み込みを省くと、蓄積があっても参照されず、複利が消える。

## 原則 4: 教訓は Skill に書き戻す(チャットに置き去りにしない)

状態ファイルは**プロジェクト記憶**(そのプロジェクトと共に死ぬ)、Skill は**手続き記憶**(「この種の作業のやり方」— プロジェクトを跨いで持ち運ぶ)。非自明な失敗のたびに、教訓を該当 Skill 自体に書き込む。数週間複利した Skill には新しいセクションが生える: **Known failure modes(既知の失敗モード)・Anti-patterns(やってはいけないこと)**。Skill は静的な手順書から「実際に学んだことの蓄積記録」に変わる。

書き戻しの判定: その教訓は (a) このプロジェクト固有の事実か → vault/STATE、(b) 作業の種類に紐づく手順的知見か → Skill。両方に跨るなら両方(ただし定義は 1 箇所、他方はポインタ)。この判定も `session-compound` Skill が手順化している。

## 原則 5: モデルルーティング — 役割でモデルを分ける

全工程に最上位モデルを使わない。デフォルトではなくタスクの複雑さで振り分ける:

| 役割 | 仕事 | tier |
|---|---|---|
| Orchestrator(頭脳) | 計画・分割・subagent への委譲・証拠からのルール蒸留・最終判断 | 最上位(Fable/Opus 級) |
| Worker(手足) | 定型の大量作業: compile・リファクタ・scaffold・ドキュメント更新 | 中位(Sonnet 級) |
| Grader(検証者) | 独立コンテキストでの採点・分類・lint 判定 | 安価(Haiku 級) |
| Fallback | 上位モデルが安全分類器で辞退する領域の受け皿(原則 8) | Opus 級 |

vault 維持ループの tier 分け(`obsidian-vault.md`: ルーチンは安価に、上位が席代を稼ぐのは synthesis だけ)は、この表を vault 作業に適用した特殊形。**上位モデルが席代を稼ぐのは「蒸留と判断」であって「大量の手」ではない。**

## 原則 6: 並列の安全性 = worktree 分離

複数の agent が同じチェックアウトに書くとファイルが衝突する。git worktree(同じ履歴を共有する独立の作業ディレクトリ)で分離する: maker は worktree A に書き、verifier は B から読む(または read-only)。並列実験は 1 実験 1 worktree で走らせ、最良だけをマージ。長時間ランは大フェーズごとに worktree を分ければ、失敗したフェーズが残りを汚染しない。Claude Code では `git worktree` 直接・`--worktree` フラグ・subagent の `isolation: "worktree"` の 3 経路。

## 原則 7: スケジュール起動 — 維持を意志力からスケジュールへ

自己改善ループの層 2 はトリガーで回す。`obsidian-vault.md` の維持ループ(朝は AI、夜は人間: 日次 compile・週次 lint・週次 synthesis)がそのまま実装であり、本リポジトリでは cron / Routines(スケジュールトリガー)が起動主体。イベント起動(CI 失敗→調査、PR マージ→パターンを Skill へ書き戻し)は「実環境から学ぶ」パターンとして有効だが、導入する場合も**書き戻し先と検証者(原則 1・4)を先に用意してから**。書き戻し先の無いイベントループはログを増やすだけで複利しない。

## 原則 8: 視覚検証と安全境界

- **視覚検証**: UI・ダッシュボード・図の検証をテキストだけでやらない。maker がスクリーンショットを撮り、verifier が vision で目標記述・デザイントークン・前回スクリーンショットと突き合わせる。テキスト検証では「見た目が壊れている」という肝心の失敗モードを見逃す。
- **安全境界のフォールバック設計**: 上位モデルには高リスク領域(セキュリティ研究・生物・化学・蒸留等)で応答を辞退する安全分類器が入っている。自律ループがこの辞退に当たると、**分類器ブロックと実エラーは区別が付かず、silent failure になる**。設計則: ブロックされうるタスク種を Skill 側に明記し、ブロック時は (a) 明示的に別モデルへルーティングするか (b) 人間レビューへ浮上させる。黙って握り潰さない。

## アンチパターン(複利を殺すもの)

1. 独立検証者なしの自己批判 — 作った本人が自分の宿題を採点する(原則 1)
2. 状態ファイルなし — 毎セッションがゼロから再出発(原則 3)
3. 書き込まれない Skill — 実際の失敗後も教訓が蓄積されない足場は無駄(原則 4)
4. 定型作業を上位モデルに回す — 複雑さでルーティングする(原則 5)
5. 客観的な停止条件のないループ —「十分やった」で止まる(原則 1)
6. 分類器ブロックの silent failure — フォールバックを設計しない(原則 8)
7. 視覚タスクのテキスト検証(原則 8)
8. 機密データをスケジュールランに流す前に保持ポリシー(データ保持期間・コンプライアンス)を確認しない

## 既存設計との対応(マージメモ)

本 playbook は新レイヤを増やさず、既存の部品を「自己改善ループの 4 層」として位置づけ直すもの:

- 記事の STATE.md → **vault が代替**(原則 3 の対応表)。新設しない。
- 記事の eval loop / rubric → **memory-dream の lint + 採用前レビュー**(週次)。
- 記事の morning briefing → **vault-compile の早朝 cron**(既存)。
- 記事の Skill 書き戻し → **session-compound Skill(本 playbook と同時に新設)**。既存 Skill に Known failure modes / Anti-patterns 節を育てる。
- 記事のモデル tier 表 → 原則 5 が一般形、`obsidian-vault.md` の維持ループ表が vault への適用形。定義の重複はさせない。

## 採用しなかったもの(判断メモ)

- **`/goal` / Outcomes / Dynamic Workflows / CMA(Claude Managed Agents)**: 記事が前提とする機能名だが、一次資料で確認できない(`obsidian-vault.md` も `/goal` を「確認できない」と判断済みで整合)。「独立 grader が停止条件を判定するループ」という骨格だけ採用し、実装は Skill +検証 subagent + cron/Routines で行う。fan-out・adversarial verification・loop-until-done の 3 パターンも、専用機能なしに Agent tool の並列起動で組める骨格として扱う。
- **記事の数値・逸話**: 検証カバレッジ 73% vs 17%、改善 6 倍、「70%+ の記憶優位が消える」、Parameter Golf(8×H100・8 時間)、Continual Learning Bench の SQL タスク詳細 — いずれも一次出典未確認。方向性(独立検証者が仮説空間を広げる・書き戻しなしでは複利しない)だけ採用し、数値は根拠にしない。
- **価格・提供日・製品ライン語り**: トークン単価、launch 日付、「319 ページの system card」、Mythos/Glasswing の経緯、「ブロック時に Opus 4.8 へ自動フォールバック」— 記事の主張のまま検証していない。設計判断の根拠にしない(フォールバックは「自動で起きる」前提ではなく自分で設計する — 原則 8)。
- **「Fable 5 専用の設計」という枠組み**: 記事はモデル固有の話として書くが、4 層スタック・独立検証・5 段階記憶・書き戻しはモデル非依存の設計原則。vault がモデル非依存で生き残るのと同じ理由で、モデル名に依存しない形で採用した。
