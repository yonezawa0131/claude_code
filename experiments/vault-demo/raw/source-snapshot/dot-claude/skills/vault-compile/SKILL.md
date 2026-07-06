---
name: vault-compile
description: Obsidian vault の raw/(inbox・daily・reading・ClaudeChat Memory)の新着を entities/ concepts/ へコンパイルする日次ルーチン。安価なモデル(Sonnet/Haiku)で回してよい定型作業。トリガー:「inboxを整理して」「compileして」「vaultをコンパイルして」「今日の分を整理して」。変更は diff で提示し、push はユーザー明示指示まで保留する。
---

# vault-compile(日次 compile パス)

Obsidian vault の raw/ に溜まった新着素材を entities/ concepts/ へ反映する定型作業。vault の構造・書き込み境界・維持ループの設計は `notes/playbook/obsidian-vault.md` を参照(このSkillでは再掲しない)。このSkillは同ドキュメントの維持ループ表にある「定期(日次目安)compile」に対応する。**ルーチン作業なので安価なモデル(Sonnet/Haiku)で回してよい** — 上位モデルは週次の memory-dream(lint)・synthesis に温存する。

## 前提: 作業対象の特定

このSkillの作業対象は Obsidian vault のルート(以下 `{vault}`)。場所は次の順で解決する:

1. 現在ロード済みの CLAUDE.md に vault への参照(`knowledge` 節等)があれば実パスを逆引きする
2. `notes/ghq.md` にリポジトリ/vault の配置記載があれば従う
3. 見つからなければ推測で進めず、ユーザーに場所を確認する

## 手順

1. **新着の特定**: 前回 compile 以降に増えた raw/ 配下(inbox・daily・reading・ClaudeChat Memory)のファイル/差分を特定する。git 管理下なら `git log` で前回 compile commit 以降の変更ファイル、そうでなければファイル更新日時(mtime)で判定する。
2. **entities/ concepts/ への反映**: 既存ページの更新を優先し、重複ページを作らない(同じ対象・概念に触れるページが既にあるか探してから書く)。新規ページは 1 ファイル 1 教訓、冒頭に 1 行要約を置く。
3. **バックリンク規律**: 更新/新規ページに `[[リンク]]` を 3 本以上、うち 1 本は古い層(できれば 2 年以上前)へ繋ぐ(定義は playbook 書き込みルール 7)。
4. **出典規律**: 主張には raw/ 内の元ファイルへのリンクを必須で付ける(出典の無いページは次回の lint でフラグ対象になる)。
5. **タグ**: INDEX.md が定義する固定スキーマのタグのみを使う。スキーマに無いタグが欲しくなったら新規発明せず、先に INDEX.md 側のスキーマ更新を提案する。
6. **INDEX.md 更新**: 新規ページを 1 行説明付きで追加する。
7. **日次ダイジェスト**: `reviews/YYYY-MM-DD.md` に当日分の compile 内容の要約を書く。
8. **NOW.md 更新**: playbook「NOW.md」の定義に従い更新する(20 行以内。vault に無ければ新規作成してよい)。
9. **禁止事項**: raw/ への書き込み・書き換えは一切行わない(compile の入力は raw/ のまま保存し、コンパイル側が壊れても再コンパイルできる状態を保つ)。過去の reviews/ も書き換えない(日付付きスナップショットとして固定)。
10. **提示規律**: 変更は必ず diff で提示する。論理単位(ページ単位・topic 単位)ごとに commit できる粒度に分ける。push はユーザー明示指示まで保留する。

## チェックリスト

- [ ] 前回 compile 以降の新着を漏れなく特定した(git log または mtime)
- [ ] 既存ページを優先して更新し、重複ページを作っていない
- [ ] 新規ページは 1 ファイル 1 教訓・冒頭 1 行要約になっている
- [ ] 更新/新規ページに `[[リンク]]` を 3 本以上張った(1 本は古い層へ)
- [ ] 全ての主張に raw/ への出典リンクを付けた
- [ ] タグは INDEX.md の固定スキーマの範囲内
- [ ] INDEX.md に新規ページを 1 行説明付きで追加した
- [ ] `reviews/YYYY-MM-DD.md` に当日分のダイジェストを書いた
- [ ] NOW.md を更新した(20 行以内)
- [ ] raw/ と過去の reviews/ に一切書き込んでいない
- [ ] 変更を diff で提示し、論理単位ごとに commit 可能な状態にした(push は保留)
