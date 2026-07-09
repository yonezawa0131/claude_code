---
name: reading-intake
description: Web記事・URLをObsidian vaultの raw/reading/ に「原文+要約」のクリップとして取り込む取込パス。トリガー例:「この記事を取り込んで」「readingに保存して」「クリップして」「記事を要約してvaultに入れて」。1記事1ファイル。既に同一URLが取り込み済みならskip。
---

# reading-intake(記事取込パス)

Web記事・URL(またはユーザーが貼り付けた原文)を Obsidian vault の `raw/reading/` に「原文+要約」クリップとして取り込む。vault の構造・書き込み境界の思想は `notes/playbook/obsidian-vault.md` を参照(このSkillでは再掲しない)。

**このSkillは playbook が言う「raw/ は人間(と取込スクリプト)が書く」の"取込スクリプト相当"としての明示的な例外**であり、`raw/reading/` への**新規ファイル追加のみ**を許可する。既存 raw/ ファイルの書き換え・削除は一切禁止(reading/ を含む)。entities/ concepts/ への反映はこのSkillでは行わず、vault-compile に委ねる。

## 前提: 作業対象の特定

作業対象 vault(以下 `{vault}`)の解決順は vault-compile と同じ(CLAUDE.md の knowledge 節から逆引き → `notes/ghq.md` → 見つからなければユーザーに確認)。詳細は vault-compile を参照。

## 手順

1. **重複チェック**: `{vault}/raw/reading/` を取込対象 URL で grep する。既にヒットするファイルがあれば、そのパスを示して **skip として報告**し、以降の取込は行わない(ユーザー要望「インプット済みは Skip」)。
2. **原文取得**: WebFetch で全文取得を試みる。ネットワークポリシーで 403 等になり取得できない環境では、WebSearch による内容復元にフォールバックする。取得できた場合は frontmatter `status: clipped`、復元ベースの場合は `status: needs-original`(原文未取得・要バックフィルの明示)。
3. **ユーザーが原文テキストを直接貼り付けた場合**: WebFetch/WebSearch を使わず、貼付テキストをそのまま原文として格納する(`via: manual`)。
4. **ファイル作成**: `raw/reading/YYYY-MM-DD-<slug>.md` を新規作成する(YYYY-MM-DD は取込日、slug はタイトルから生成)。
   - frontmatter: `title` / `url` / `author` / `published` / `clipped`(取込日) / `via`(webfetch|websearch|manual) / `status`(clipped|needs-original)。
   - 本文: `## 要約`(5〜10 行)→ `## 内容詳細`(原文取得/貼付時は `## 原文`)。
   - **復元ベース(websearch)の場合**: 確認できなかった箇所はその旨を明記し、**推測で埋めない**。不明な frontmatter 値は空にする。
5. **著作権への注意**: 原文全文クリップは私的利用の範囲での取込。**`{vault}` が公開リポジトリの場合は全文格納を避け、要約+短い引用に留める**(公開/非公開が不明ならユーザーに確認する)。
6. **取込後の接続**: 取込内容を entities/ concepts/ へ反映するため **vault-compile を次アクションとして提案する**(自動では実行しない)。
7. **提示規律**: 変更は必ず diff で提示する。push はユーザー明示指示まで保留する。

## チェックリスト

- [ ] 取込前に URL で `raw/reading/` を grep し、既取り込みなら skip 報告した
- [ ] 原文取得は WebFetch を試み、失敗時のみ WebSearch にフォールバックした
- [ ] `status` を取得手段に応じて正しく設定した(clipped / needs-original)
- [ ] 貼付原文は `via: manual` でそのまま格納した
- [ ] ファイル名 `raw/reading/YYYY-MM-DD-<slug>.md`・frontmatter 7 項目を満たした
- [ ] 本文は `## 要約`(5〜10 行)+ `## 内容詳細`/`## 原文` の構成にした
- [ ] 復元ベースでは未確認箇所を明記し、推測で埋めていない
- [ ] 公開リポジトリなら全文を避け要約+引用に留めた
- [ ] `raw/reading/` への新規追加のみで、既存 raw/ を書き換え・削除していない
- [ ] vault-compile を次アクションとして提案した(自動実行はしない)
- [ ] 変更を diff で提示した(push は保留)
