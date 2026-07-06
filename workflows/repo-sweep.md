---
name: repo-sweep
trigger: cron "0 21 * * 5"（週次金曜夜想定。武装は playbook 参照。それまでは手動）
executor: sonnet
output: このリポジトリ（claude_code）+ 掃除レポート workflows/logs/ 併記
boundaries:
  allow:
    - "notes/**"
    - "workflows/**"
    - ".claude/**"
    - "scripts/**"
  deny:
    - ファイルの削除（削除候補のフラグ付けまで。実削除はユーザーレビュー後）
    - .claude/skills/autopilot/SKILL.md の不変条件セクションの変更
    - 外部送信・公開・PR 作成
  commit: true
  push: false
verify:
  - 報告に列挙されたリンク切れ・陳腐化箇所が現物と一致する（サンプル確認）
  - workflows/README.md の一覧表が workflows/*.md の実ファイル・frontmatter と一致している
  - 削除されたファイルが 1 つもない（git diff --stat で実測）
  - 各 commit が論理単位で、メッセージが変更内容を正しく説明している
---

# repo-sweep — リポジトリ衛生の定期掃除

## 目的

ドキュメント・設定リポジトリは書きっぱなしで静かに腐る（リンク切れ、実在しないパスへの言及、索引と実体のズレ）。週次で機械的に検出・修正し、「思い出す助け」がノイズに転落するのを防ぐ。

## 手順

1. **リンク・参照検査**: notes/ と .claude/ 配下の Markdown から、リポジトリ内パスへの言及（バッククォート内のパス、相対リンク）を抽出し、実在を確認する。切れているものは修正（リネーム追従）または要判断としてフラグ。
2. **索引同期**: `workflows/README.md` の一覧表を `workflows/*.md` の frontmatter から再生成する。乖離があれば表を直す。
3. **陳腐化検出**: 相対日付表現（「昨日」「先週」等）、完了済みタスクへの言及、現在の構成と矛盾する記述を検出する。機械的に直せるもの（絶対日付化）は直し、判断を要するものはフラグ。
4. **logs 剪定候補**: `workflows/logs/` が 30 件を超えていたら、古いものを削除**候補**として列挙する（削除はしない）。
5. 修正は種類ごとに論理単位で commit。フラグ一覧は報告にまとめる。

## 補足

- vault（agents-share 側）はこのワークフローの対象外。vault の掃除は memory-dream Skill の担当。
- 直すか迷う記述は直さずフラグに回す。無人運用では誤修正のほうが放置より高くつく。
