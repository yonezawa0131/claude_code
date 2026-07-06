# skill-vault-compile

raw/ の新着を entities/concepts へ反映する日次 compile Skill。安価なモデルで回す定型作業。

#type/skill #domain/vault #layer/procedure

## 何をするか

前回 compile 以降の raw/(inbox・daily・reading・ClaudeChat Memory)の新着を git log または mtime で特定し、既存ページ優先で entities/concepts を更新する。新規ページは 1 ファイル 1 教訓・冒頭 1 行要約。`[[リンク]]` を 3 本以上(1 本は古い層へ)張り、raw/ への出典リンクを必須で付け、タグは INDEX.md の固定スキーマ内に限る。`INDEX.md` へ新規ページを追加し、`reviews/YYYY-MM-DD.md` に日次ダイジェストを書き、`NOW.md` を更新する。

## 入出力・使いどころ

入力は raw/ 配下の新着素材。出力は entities/ concepts/ reviews/ NOW.md。raw/ と過去の reviews/ には書き込まない。変更は diff で提示し、push はユーザー明示指示まで保留。安価モデル(Sonnet/Haiku)向けで、上位モデルは週次の [[skill-memory-dream]] / [[skill-vault-synthesis]] に温存する。

## 関連

- [[playbook-obsidian-vault]] — 維持ループ表の「日次 compile」に対応する定義元
- [[skill-memory-dream]] — compile 結果を週次で lint する関係
- [[script-export-to-obsidian]] — compile が読む raw/ClaudeChat Memory の生成元
- [[now-md-context-load]] — compile が着地させる NOW.md の設計原則

出典: [`.claude/skills/vault-compile/SKILL.md`](../raw/source-snapshot/dot-claude/skills/vault-compile/SKILL.md)
