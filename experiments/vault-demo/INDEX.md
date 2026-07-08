# INDEX — vault-demo の玄関

全ページを 1 行説明付きで列挙する。全ファイルを開かずに何が在るかを知るための索引。

## タグ固定スキーマ

ここに定義したタグだけを使う(エージェントに自由発明させない。新種が要るならまずこの表を更新する)。

- **type**: `#type/skill` `#type/script` `#type/hook` `#type/config` `#type/playbook` `#type/concept`
- **domain**: `#domain/memory` `#domain/vault` `#domain/import` `#domain/infra` `#domain/model`(モデル/effort の選択・運用)
- **layer**: `#layer/rule`(守るべき規律) `#layer/procedure`(手順) `#layer/tool`(実行物)

## entities/(成果物 1 つ 1 ページ)

- [[skill-memory-dream]] — 記憶階層/vault を再編し重複・矛盾・陳腐化を除去する consolidation Skill
- [[skill-vault-compile]] — raw の新着を entities/concepts へ反映する日次 compile Skill(安価モデル)
- [[skill-vault-synthesis]] — 週次に 7 日分を横断し矛盾・ドリフトを 1 ページ化する synthesis Skill(上位モデル)
- [[script-export-to-obsidian]] — claude.ai 会話エクスポートを vault の raw/ へ変換するスクリプト
- [[playbook-obsidian-vault]] — vault 設計の定義元 playbook
- [[playbook-memory-dream-pointer]] — memory-dream playbook から Skill への移行ポインタ
- [[playbook-model-effort]] — モデル選択と effort 設定の使い分け判断手順の定義元 playbook
- [[hook-session-start]] — SessionStart フック(個人 Skill の同期)

## concepts/(設計原則 1 つ 1 ページ)

- [[write-boundary]] — 書き込み境界(raw 不可侵・人間/AI 層の分離)
- [[pay-per-read]] — 読み取りコスト管理(全読み禁止・必要ページのみ開く)
- [[maintenance-loop]] — 維持ループ(compile/lint/synthesis・朝は AI 夜は人間・cron 自動起動)
- [[backlink-discipline]] — バックリンク規律(3 本以上・1 本は古い層へ)
- [[now-md-context-load]] — NOW.md による毎セッション文脈ロード
- [[graph-health-metric]] — グラフのリンク密度=唯一の健全性メトリクス
- [[single-source-dedup]] — 定義は 1 箇所・上位ルールを下位で再掲しない
- [[capture-friction]] — capture の摩擦最小化(単一投入口・低摩擦入力)
- [[model-vs-effort]] — モデル(能力)と effort(徹底度)の使い分け・判断手順

## ルート

- [[NOW]] — 現在の焦点・未解決の仮説・直近の決定(20 行以内)
- [[README]] — この Vault は何か / 汚染回避の設計 / 検証結果
