# 維持ループ

維持を意志力でなくスケジュールに乗せる。放置した vault は 3 週間で死ぬので、compile/lint/synthesis を頻度別に自動起動する。

#type/concept #domain/vault #layer/rule

## 主張

**朝は AI、夜は人間**に時計を分ける。夜に人間が capture し、早朝(例 6:30–8:00)に cron 等のスケジューラが自動起動する。朝ラップトップを開くと昨日分は既にマッピング済みで、「土曜の午後に片付ける」が消える。

| 頻度 | 作業 | Skill |
|---|---|---|
| セッション毎 | 決定・失敗・気づきを日付付きで記録 | — |
| 日次(早朝 cron) | compile: 新着を entities/concepts へ反映・NOW.md 更新 | [[skill-vault-compile]] |
| 週次 | lint: 矛盾・重複・リンク切れ・孤立ノート精査 | [[skill-memory-dream]] |
| 週次(日曜) | synthesis: 横断して「今週何が変わったか」を 1 ページ | [[skill-vault-synthesis]] |
| セッション終了時 | compound: 教訓・事実・仮説をコンパイル層と Skill に書き戻し | [[skill-session-compound]] |

**モデル tier 分け**: ルーチン(ノート更新)は安価なモデル(Sonnet/Haiku)。上位モデルが席代を稼ぐのは synthesis だけ。ルーチンを上位モデルに回さない。

## 関連

[[playbook-obsidian-vault]] / [[graph-health-metric]] / [[hook-session-start]] / [[state-file-discipline]]

[出典](../raw/source-snapshot/notes/playbook/obsidian-vault.md)
