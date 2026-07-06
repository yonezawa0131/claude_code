---
name: vault-synthesis
description: Obsidian vault の過去 7 日分（raw/daily・reviews/ の日次ダイジェスト・compiled の差分）を横断して読み、「今週何が繰り返され・何が矛盾し・何がドリフトしたか」を reviews/YYYY-Www.md に 1 ページ書く週次 synthesis パス。トリガー:「今週のまとめ」「synthesisして」「週次レビュー」「週次サマリー」。矛盾は指摘まで（解消はしない）。変更は論理単位ごとの commit で提示し、push はユーザー明示指示まで保留する。
---

# vault synthesis（週次 synthesis）

過去 7 日分の vault を横断し、週の意味を 1 ページに凝縮する。vault の維持ループ（`notes/playbook/obsidian-vault.md`）のうち、**上位モデル（Opus 級）が席代を稼ぐ唯一のパス**。ルーチンな compile / lint（memory-dream）とは役割が違う — ここでは差分ではなく「意味」を書く。

## 前提: 作業対象の特定

vault のルートを次の順で解決する:

1. ロード済みの CLAUDE.md / AGENTS.md が指す vault パスから逆引きする
2. `notes/ghq.md` にリポジトリ配置の記載があれば従う
3. 見つからなければ推測で進めず、ユーザーに場所を確認する

## 入力: 過去 7 日の差分を特定する

横断パスなので **subagent に vault を広く読ませてよい**（playbook「読み取りルール」の横断パス例外規定に従う。日常の pay-per-read とは別扱い）。読む対象:

- `raw/daily/` の直近 7 日分（生の作業・決定・気づき）
- `reviews/` のこの 7 日の日次ダイジェスト
- compiled（`entities/` `concepts/`）のこの 7 日の差分。範囲は git log で特定する:

  ```bash
  cd {vault_root} && git log --since='7 days ago' --stat -- entities/ concepts/ reviews/ raw/daily/
  ```

subagent には 50 ページ読ませても、メインに返すのは結論だけ。図書館ではなく決定を context に置く。

## 出力: reviews/YYYY-Www.md（ISO 週番号）

ファイル名は ISO 週番号（例 `reviews/2026-W28.md`）。次の構成要素を、各項目に出典の `[[リンク]]` を付けて書く:

- **繰り返し現れたテーマ** — 週を通して何度も戻ってきた話題
- **矛盾** — 自分の思考内で、気づかずに両方を言っていること
- **やりかけの約束** — 自分に半分だけした宣言・宙に浮いた TODO
- **ドリフト** — 静かに変わった方針・注意の移動
- **来週注目に値すること**

出典リンクの無い主張は書かない（playbook の出典規律）。仮リンク（未作成ページへの `[[リンク]]`）は歓迎だが放置しない。

## NOW.md の更新

`NOW.md` を今週の着地点で更新する（定義・行数上限は playbook「NOW.md」）。週の重心だけを置き、履歴は reviews/ に残す。

## 禁止事項（境界）

- **raw/ は書き換えない**（ground truth。読むだけ）。
- **過去の reviews/ は書き換えない**（日付付きスナップショット）。書くのは今週の 1 ページと NOW.md だけ。
- **矛盾を見つけても解消しない** — 指摘までが synthesis の仕事。解消は memory-dream（lint）かユーザー判断に委ねる。この分業を混ぜない。

## 提示規律

- 変更は「更新した」の主張ではなく **diff で提示**する。
- 論理単位ごとに commit 可能な状態に分ける。
- **push はユーザーの明示指示まで保留**。

## チェックリスト

- [ ] vault ルートを確定した（不明ならユーザー確認済み）
- [ ] git log で過去 7 日の差分範囲を特定した
- [ ] 横断読みは subagent に任せ、メインには結論だけ返した
- [ ] 5 構成要素（テーマ / 矛盾 / やりかけの約束 / ドリフト / 来週）を書いた
- [ ] 各項目に出典 `[[リンク]]` を付けた
- [ ] ファイル名が ISO 週番号（YYYY-Www）
- [ ] NOW.md を 20 行以内で更新した
- [ ] raw/ と過去 reviews/ に書き込んでいない
- [ ] 矛盾は指摘のみ（解消していない）
- [ ] 変更を diff で提示・論理単位で commit（push は保留）
