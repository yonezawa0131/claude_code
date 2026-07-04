# Skill棚卸し監査レポート（2026-07-02）

対象: 本セッションで利用可能な全14 Skill。全件について実物（SKILL.md またはバイナリ埋込本文）を読んで判定した。

## 前提となる在庫の実態（監査の最重要所見）

- **ユーザー自身のSkill資産は実質ゼロ。** 個人領域（`~/.claude/skills/`）は `session-start-hook` 1つのみで、これも環境が自動配備したストック品（`/root/.claude` と `/home/claude/.claude` にバイト一致のコピーが存在することを diff で確認）。プロジェクトSkill（`.claude/skills/`）は全ブランチでゼロ。
- 残り13は **Claude Code CLI 同梱のベンダーSkill**。実体は `/opt/claude-code/bin/claude`（248MB）内にJS文字列として埋め込まれており、ユーザーは編集できない。よってこれらの分類は事実上「現状維持」一択で、指摘は上流（Anthropic）向けの認識事項となる。
- 一方で、リポジトリの実作業（adops ブランチの広告運用ワークフロー、memory-consolidation ブランチの記憶整理手順）には **Skill化されるべき反復手順が既に文書として存在する**のに、Skillシステムの外に置かれている。今回の監査で最も価値がある指摘は「持っているSkillの整理」ではなく「Skillにすべきものが野良文書化している」ことである。
- 参考: `/mnt/skills/` に Anthropic サンプルSkill 32個（docx/pdf/pptx/xlsx ほか）がマウントされているが、本セッションのSkillツールには未登録で呼び出せない。環境同梱物であり在庫として扱う必要はない。

## 1. Skill一覧表

行数について: ベンダーSkillはバイナリ埋込（複数のJS文字列から実行時合成）のため正確な行数は測定不可。抽出できた範囲の概算を「~」付きで示す。

| # | name | 由来 | 本文行数 | 発火精度 | 推奨アクション |
|---|------|------|---------|:---:|----------------|
| 1 | session-start-hook | 個人 (`~/.claude/skills/`) | 153 | 6/10 | **description修正のみ**（+ name不一致修正） |
| 2 | dataviz | CLI同梱 | 測定不可（大規模、references/palette.md 等を含む） | 9/10 | 現状維持（description肥大は認識のみ） |
| 3 | update-config | CLI同梱 | 測定不可 | 9/10 | 現状維持 |
| 4 | keybindings-help | CLI同梱 | 測定不可（複数変数から合成） | 8/10 | 現状維持（本環境では死蔵、実害なし） |
| 5 | verify | CLI同梱 | ~150行前後（抽出断片より） | 8/10 | 現状維持（runとの衝突は上流課題） |
| 6 | code-review | CLI同梱 | 測定不可（大規模） | 8/10 | 現状維持 |
| 7 | simplify | CLI同梱 | 測定不可 | 7/10 | 現状維持（code-review --fix との重複は上流課題） |
| 8 | fewer-permission-prompts | CLI同梱 | ~70行（全文抽出済み） | 9/10 | 現状維持 |
| 9 | loop | CLI同梱 | 測定不可 | 9/10 | 現状維持 |
| 10 | claude-api | CLI同梱 | 数千行規模（言語別リファレンス多数を確認） | 8/10 | 現状維持（設計上の progressive disclosure） |
| 11 | run | CLI同梱 | ~200行前後（抽出断片より） | 7/10 | 現状維持（verifyとの衝突は上流課題） |
| 12 | init | CLI同梱 | 測定不可 | 5/10 | 現状維持（書き換え案は下記、上流向け） |
| 13 | review | CLI同梱 | 測定不可 | 6/10 | 現状維持（書き換え案は下記、上流向け） |
| 14 | security-review | CLI同梱 | ~100行前後（抽出断片より） | 5/10 | 現状維持（書き換え案は下記、上流向け） |

採点基準: 「そのdescriptionだけを読んで、発火すべき場面で発火し、発火すべきでない場面で発火しない確率」。トリガー語彙の具体性、除外条件の明記、近接Skillとの弁別性で評価。

## 2. 問題リスト（深刻度 高→低）

### 【高】H-1: Skill同等の手順書がSkillシステム外で死蔵している
`claude/memory-consolidation-playbook-4qlrr3` ブランチの `notes/playbook/memory-dream.md` は、frontmatter（name / description / type: playbook）を持つ**実質SKILL.md**。しかし notes/ 配下にあるためSkillとして一切発火せず、別ブランチにあるため他セッションから発見もされない。4フェーズ手順・判定ルールまで整備済みで、Skill化コストはほぼゼロ。→「作り直し」判定。

### 【高】H-2: 反復手順「知識取り込み」が発見不能
adops ブランチの `docs/KNOWLEDGE_INTAKE.md` は「inboxの知識を取り込んで」という自然言語トリガーを前提にした反復手順書だが、**CLAUDE.md から一切参照されていない**（grep で確認、ヒット0）。ユーザーがその依頼をしても Claude がこの手順書に到達する保証がない。Skill化（descriptionにトリガー句を書く）が正攻法。→ 新設候補 N-1。

### 【中】M-1: session-start-hook の name 不一致 + update-config とのトリガー衝突
frontmatter は `name: startup-hook-skill`、ディレクトリ名・セッション登録名は `session-start-hook`。管理上の混乱要因。さらに update-config のdescriptionは「hooks configured in settings.json」「hook troubleshooting」を明記しており、「SessionStartフックを設定して」という依頼で**どちらが発火するか曖昧**。session-start-hook 側のdescriptionに弁別条件（依存インストール用フック作成に限る／一般のフック設定は update-config）が無い。

### 【中】M-2: トリガー衝突 — verify vs run（ベンダー側）
run のdescriptionに「or to confirm a change works in the real app (not just tests)」とあり、verify の本務（変更をend-to-endで動かして確認）と文言レベルで被る。「この変更が動くか確認して」でどちらが起動するか曖昧。要確認: verify が内部で run に委譲する設計の可能性あり（run 本文に「First: does a project skill already cover this?」の分岐を確認）。ユーザー側で対処不能。

### 【中】M-3: 責務の重複 — simplify ⊂ code-review --fix（ベンダー側）
code-review のdescriptionは「reuse/simplification/efficiency cleanups」を明記し、`--fix` で適用まで行う。simplify の守備範囲（reuse, simplification, efficiency… then apply）はその真部分集合。「コードを綺麗にして」で発火先が割れる。simplify 側が「it does not hunt for bugs; use /code-review for that」と弁別を試みているが、重複自体は解消していない。ユーザー側で対処不能。

### 【低】L-1: 死蔵 — keybindings-help
リモートWeb実行環境ではターミナルのキーバインド設定（`~/.claude/keybindings.json`）は揮発性コンテナ内の話であり用途がほぼ無い。CLI同梱のため削除も不要。実害なし。

### 【低】L-2: description の肥大化 — dataviz / claude-api（ベンダー側）
dataviz は約190語、claude-api は約250語（TRIGGER/SKIP の擬似コードブロック込み）のdescriptionを持つ。description は全Skill分が常時コンテキストに載るため恒常的なトークン負担。発火精度を優先した意図的設計と推察されるが、認識はしておくべき。

### 【低】L-3: 素っ気なさすぎるdescription — init / review / security-review（ベンダー側）
3件とも「Use when」もトリガー例も無い一文。主にユーザー明示の slash command として使われるため実害は限定的だが、自動発火の文脈では精度が低い（採点 5〜6）。書き換え案は §3。

## 3. 発火精度 7点未満の書き換え案

### session-start-hook（6/10）— 唯一ユーザーが実際に修正可能
```yaml
name: session-start-hook   # ディレクトリ名・登録名と統一（現: startup-hook-skill）
description: >
  Claude Code on the web 用の SessionStart フック（依存インストールスクリプト）を作成・検証する。
  トリガー: 「Webセッションでテスト/リンターが動くようにして」「session start hook を作って」
  「このリポジトリを Claude Code on the web に対応させて」。
  settings.json の一般的な設定変更や SessionStart 以外のフック設定は update-config を使うこと。
```

### init（5/10）※上流向け提案
> Use when the user asks to create or regenerate CLAUDE.md, onboard Claude to this codebase, or runs /init. Analyzes repo structure, build/test/lint commands, and conventions, then writes CLAUDE.md.

### review（6/10）※上流向け提案
> Review a GitHub pull request given a PR number or URL (e.g. "review PR #123"). Fetches the PR diff and posts review feedback. For uncommitted local changes or the current branch's working diff, use /code-review instead.

### security-review（5/10）※上流向け提案
> Security-focused review of the pending changes on the current branch. Use when asked for a security review, vulnerability check, or "is this change safe" — covers injection, authz, secrets, crypto misuse. For general correctness review use /code-review.

## 4. 分類サマリ

| 分類 | Skill |
|------|-------|
| 現状維持 | dataviz, update-config, keybindings-help, verify, code-review, simplify, fewer-permission-prompts, loop, claude-api, run, init, review, security-review（全てCLI同梱・編集不可。M-2/M-3/L-2/L-3 は上流課題として認識） |
| description修正のみ | session-start-hook（name統一 + 弁別条件追記。§3の案） |
| 統合 | 該当なし（simplify→code-review への統合が論理的だがベンダー管轄） |
| 分割 | 該当なし |
| 削除 | 該当なし（削除可能なユーザーSkillが存在しない） |
| 作り直し | memory-dream（notes/playbook/memory-dream.md → 正式Skill化。§6） |

## 5. 新設すべきSkill候補（「欠落」から）

| # | 候補名 | 根拠 | 置き場所 |
|---|--------|------|---------|
| N-1 | **knowledge-intake** | H-2。`docs/KNOWLEDGE_INTAKE.md` の手順（inbox精査→差分提案→承認→archive移動→回帰確認）は反復作業なのにCLAUDE.md未参照で発見不能。手順書をほぼそのままSKILL.md化できる。descriptionに「inboxの知識を取り込んで」「過去のプランニング資産を反映して」を明記 | adopsブランチ `.claude/skills/knowledge-intake/` |
| N-2 | **memory-dream** | H-1。既に手順書完成済み。Skill化のみ | agents-share リポジトリ（手順書の記述に従う）または利用リポジトリの `.claude/skills/` |
| N-3 | **run-adops** | run Skillは「まずプロジェクトSkillを探す」設計だが adops には存在せず、毎回コールドスタートになる。CLI同梱の run-skill-generator（バイナリ内に存在を確認）で生成可能 | adopsブランチ `.claude/skills/run-adops/` |
| N-4 | campaign-kickoff（要確認） | 新規案件の order.yaml 作成→plan→検収の定型フロー。ただし CLAUDE.md の委譲テーブル + media-planner agent で既に賄えている可能性が高く、屋上屋になりうる。運用してみて発火漏れが出た場合のみ新設 | adopsブランチ |

## 6. 「作り直し」判定一覧（次回見直しプロンプトへの引き継ぎ）

| Skill（現状の姿） | 作り直しの内容 |
|---|---|
| memory-dream（`notes/playbook/memory-dream.md`、claude/memory-consolidation-playbook-4qlrr3 ブランチ） | frontmatter付き手順書を `.claude/skills/memory-dream/SKILL.md` として正式Skill化。descriptionにトリガー句（「記憶を整理して」「dreamして」「memory consolidation」）を明記。type: playbook などSkill仕様外のフィールドは除去。本文の4フェーズ手順・重複排除ルールはそのまま流用可能 |

次回プロンプト例:
> notes/playbook/memory-dream.md を .claude/skills/memory-dream/SKILL.md に作り直して。frontmatter は name/description のみ、description には発火トリガー句を含めること。本文の手順は維持しつつ、Skill として単体で読めるよう文脈依存の記述（{agent_global_home} 等のプレースホルダ）の解決方法を冒頭に明記して。

## 7. 今すぐやる3つ（最優先アクション)

1. **knowledge-intake をSkill化する（H-2）** — 実務で最も発火頻度が高いのに現状は発見不能。手順書は完成しているため作業は移植のみ。暫定でも CLAUDE.md に1行リンクを足すだけで発見可能性は回復する。
2. **memory-dream を正式Skillに作り直す（H-1）** — 完成済み手順書の置き場所を直すだけで、別セッション・別ブランチからも使えるようになる。
3. **session-start-hook の name 統一 + description 書き換え（M-1）** — 唯一ユーザーが編集できるSkillの唯一の欠陥。§3の案を適用し、update-config との衝突を解消する。

---

## 8. 実施記録（2026-07-04）

「今すぐやる3つ」を全て実施した。

1. **knowledge-intake のSkill化 — 完了**: `claude/ad-workflow-automation-idw5ta` に `.claude/skills/knowledge-intake/SKILL.md` を追加し、`docs/KNOWLEDGE_INTAKE.md` は単一情報源維持のためポインタ化（commit 5d1046a）。なお実施時点でリモートに知識取り込み実施済みのコミット（d2910e9, benchmarks v2）が先行しており、リベースの上で反映した。
2. **memory-dream のSkill化 — 完了**: `claude/memory-consolidation-playbook-4qlrr3` に `.claude/skills/memory-dream/SKILL.md` を追加（トリガー句入りdescription、`{agent_global_home}` 解決手順を冒頭に明記、Skill仕様外の `type` フィールド除去）。`notes/playbook/memory-dream.md` は本Skill自身の単一定義原則に従いポインタ化（commit 80ac3e4）。
3. **session-start-hook の修正 — 完了（要・恒久化）**: コンテナ内の `~/.claude/skills/session-start-hook/SKILL.md`（2コピーとも）に name 統一とdescription書き換えを適用済み。**ただしリモートコンテナは揮発性のため、この修正はセッション終了で失われる。** 修正版を本ブランチの `proposals/session-start-hook.SKILL.md` に保存した。恒久化するにはローカルマシンの `~/.claude/skills/session-start-hook/SKILL.md` にこのファイルを上書きコピーすること。
