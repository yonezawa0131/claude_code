---
title: 「Fable 5 実践完全ガイド」の検証と採否
date: 2026-07-04
type: review
---

# 「Fable 5 実践完全ガイド」の検証と採否

ユーザー持ち込みの長文ガイド（2026年版・自己改善型AIエージェント構築）を検証し、
このリポジトリに取り入れるもの／見送るものを判断した記録。

## 事実検証（重要）

ガイドには事実と異なる・確認できない記述が混在している。**AI 生成コンテンツの可能性が高い**ため、内容を鵜呑みにしないこと。

| 記述 | 判定 |
|---|---|
| 「Fable 5 は AI エージェントフレームワーク」 | **誤り**。Fable 5 は Anthropic のモデル名（Claude 5 ファミリー、Mythos 級ティア）。フレームワークではない |
| `claude-opus-5` / `claude-haiku-5` というモデル | 実在しない。実在するのは Claude Sonnet 5 / Opus 4.8 / Haiku 4.5 など |
| `gpt-5.5` / `codex-2026` とその価格表 | 確認できない（おそらく創作） |
| 各モデルの $/1M トークン価格 | 創作の疑い。価格は必ず公式ドキュメントで確認する |
| 「7月7日までの無料期間」 | 未確認。判断材料にしない |

一方、**設計思想としては既知のベストプラクティスと整合する**部分が多い:
検証ループ（実行者と検証者を分離）、チェックポイントによる長時間実行の再開、
3層メモリ（作業/エピソード/手続き）、成功パターンのスキル化、コスト上限、
コンテキストドリフト監視、human-in-the-loop エスカレーション。

## 採用したもの

| ガイドの概念 | このリポジトリでの実装 |
|---|---|
| STATE.md チェックポイント・再開・コスト追跡・ドリフト監視（第3章・第8章） | Skill [`long-task-state`](../.claude/skills/long-task-state/SKILL.md) |
| Skills 自動蓄積・成功パターンの抽象化（第7章 SkillAutoGenerator） | Skill [`skill-harvest`](../.claude/skills/skill-harvest/SKILL.md)（自動バッチではなく手動・git ベースで再現） |
| 3層メモリ（エピソード記憶の consolidation） | 既存の [`memory-dream`](../.claude/skills/memory-dream/SKILL.md) が同等をカバー済み。追加実装なし |
| 検証ループ（Verifier を実行者と分離） | Claude Code 標準の `/verify` `/code-review` が相当。非コード成果物への適用指針は `long-task-state` に一節として記載 |
| human escalation triggers（自動化してはいけない判断） | `long-task-state` の「エスカレーション条件」節に採用 |

## 見送ったもの（理由つき）

- **Python フレームワーク実装（Router / VerificationEngine / MemoryStore 等のコード）**:
  当初は「実在しないモデル・API 前提の擬似コード」として見送ったが、
  **2026-07-05 にユーザーの明示指示で実装した**（[`orchestrator/`](../orchestrator/)）。
  ガイドの直訳ではなく、公式 Anthropic SDK と実在のモデル ID・価格
  （claude-fable-5 / opus-4-8 / sonnet-5 / haiku-4-5）で作り直している。
- **モデル別ルーティング表**: ガイドの表は前提のモデル名・価格が架空のため不採用。
  実在モデルで作り直した版が `orchestrator/README.md` にある。
- **AGENTS.md / WORKFLOW.md のフォーマット**: agents-share 側に既存の記憶階層があり、
  重複する構造を持ち込むと memory-dream の重複排除原則に反する。

## 教訓

- 「実在のプロダクト名 + もっともらしい価格表 + 動きそうなコード」の組み合わせでも
  創作は混じる。持ち込み文書はまずモデル名・価格・機能名を公式情報と突き合わせる。
- 使えるのは大抵「思想」であって「コード」ではない。既存の運用（Skill / notes / git）に
  最小の形で translate する。
