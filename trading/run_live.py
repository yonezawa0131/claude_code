#!/usr/bin/env python
"""執行本体。目標の保有に近づけるための注文を出す。

## 動き方

    1. 取引所から**現在の保有を読む**（記憶に頼らない）
    2. 戦略から目標の保有を求める
    3. 差分を注文にする
    4. 関門を通す
    5. 通れば出す。通らなければ止めて理由を出す
    6. すべて記録する

毎回1から現在地を読み直すので、前回落ちていても、手で売買していても、
別のマシンから動かしても、同じ判断になる。

## 既定はペーパー

本番は `--live` を明示し、さらに関門をすべて通ったときだけ動く。
関門には「事前登録した検定に合格しているか」が含まれる。

**優位性のない戦略を自動化すると、損失は確実に、正確に、休みなく実現する。**
この基盤が実データで測った5戦略は、元本30万円で平均11.5万円を失う成績だった。
自動化していれば、その11.5万円は取りこぼしなく失われていた。

## 使い方

    # 取引所につながるかだけを確かめる（**1円も動かさない**）
    GMO_API_KEY=... GMO_API_SECRET=... \
        python trading/run_live.py --check-connection --exchange gmo

    # 配線の確認（発注しない）
    python trading/run_live.py --strategy equal_weight_btc --paper-capital 300000

    # 定期実行（cron から。週次リバランスなら週1回で足りる）
    0 0 * * 1 cd ~/claude_code && .venv-trading/bin/python trading/run_live.py ...

    # 本番（関門を全部通った場合のみ動く）
    BITBANK_API_KEY=... BITBANK_API_SECRET=... \
        python trading/run_live.py --strategy ... --live
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.src.execution.broker import (  # noqa: E402
    BitbankBroker,
    BrokerError,
    GmoBroker,
    Order,
    PaperBroker,
)
from trading.src.execution.guards import (  # noqa: E402
    GuardContext,
    Limits,
    ValidationRecord,
    check,
    describe,
)
from trading.src.execution.journal import Journal  # noqa: E402
from trading.src.execution.reconcile import (  # noqa: E402
    TargetPortfolio,
    build_orders,
    current_weights,
    exposure_jpy,
)

#: 取引所ごとの実装。**どちらも実物に対して検証されていない**
EXCHANGES = {"bitbank": BitbankBroker, "gmo": GmoBroker}

#: 目標を決める関数。戦略ごとにここへ足す。
#: **どれも、検証を通るまで本番では動かない。**
def _equal_weight_btc(_prices: dict[str, float]) -> TargetPortfolio:
    """BTCを全額持つ。買い持ちそのもの。

    この基盤が実データで測った範囲では、**これが最も成績の良かった方針**になる
    （年17.9%、ただし最大下落 −50.2%）。
    比較の基準線として、また配線の確認用として置いてある。
    """
    return TargetPortfolio(weights={"btc_jpy": 1.0})


def _half_btc(_prices: dict[str, float]) -> TargetPortfolio:
    """BTCを半分、残りは現金。下落耐性を半分にする。"""
    return TargetPortfolio(weights={"btc_jpy": 0.5})


TARGETS = {
    "equal_weight_btc": _equal_weight_btc,
    "half_btc": _half_btc,
}

#: bitbank の最小注文数量。**取引所の画面で確かめ直すこと。**
#: ここを大きく見積もると、確認のために必要以上の額を動かすことになる。
#: GMOコインは `/public/v1/symbols` から実際の値を読むので、この表を使わない
MIN_ORDER_AMOUNT = {"btc_jpy": 0.0001, "eth_jpy": 0.0001, "xrp_jpy": 0.0001}
DEFAULT_MIN_AMOUNT = 0.0001


def _credentials(exchange: str) -> tuple[str | None, str | None, str, str]:
    """環境変数から鍵を読む。名前は取引所ごとに分ける。

    同じ名前を使い回すと、bitbank の鍵で GMO に接続を試みることになる。
    """
    prefix = {"bitbank": "BITBANK", "gmo": "GMO"}[exchange]
    key_name, secret_name = f"{prefix}_API_KEY", f"{prefix}_API_SECRET"
    return os.environ.get(key_name), os.environ.get(secret_name), key_name, secret_name


def _minimum_amount(broker, pair: str) -> tuple[float, str]:
    """最小注文数量を、できるかぎり**取引所から**取る。

    取れない取引所では、こちらが持っている表を使う。
    どちらから来た値かは表示する。**出どころを隠さない。**
    """
    rules = getattr(broker, "trading_rules", None)
    if rules is not None:
        try:
            row = rules(pair)
            return float(row["minOrderSize"]), "取引所が公開している値"
        except (BrokerError, KeyError, TypeError, ValueError):
            pass
    return MIN_ORDER_AMOUNT.get(pair, DEFAULT_MIN_AMOUNT), "**こちらの手持ちの表（未確認）**"


#: テスト注文で動かしてよい上限（円）。**配線の確認に必要以上の額は要らない。**
#: 取引所が返す最小数量が想定外に大きかったときの歯止めにもなる
MAX_TEST_ORDER_JPY = 2_000.0

#: テスト注文を現在値からどれだけ離すか。**約定させないための距離**
TEST_ORDER_MARGIN = 0.05


def send_test_order(broker, pair: str, price: float, journal: Journal) -> int:
    """**実際に1回だけ注文を出し、板を確認して、取り消す。**

    ## なぜこれを別の道にしたのか

    本番の経路（`--live`）は関門を通る。関門の第一項は
    「その戦略は事前登録した検定に合格しているか」で、合格記録のある戦略は
    **1つも無い**。だから本番の経路では1回も注文を出せない。

    それは正しい。**優位性のない戦略を自動で動かさない**ための関門だから。

    しかしここでやりたいのは戦略の実行ではなく、**配線の確認**になる。
    「発注の応答をこちらが正しく解釈できるか」は、戦略とは無関係な別の問題で、
    確かめるには実際に1回出すしかない。だから経路を分ける。

    関門を緩めるのではなく、**関門の外に、関門より厳しい別の道を作る**。

    ## この道が自分に課している制限

      - 出すのは**1件だけ**。戦略も目標保有も関与しない
      - **最小数量**。取引所が公開している値を使う
      - 現在値から **5% 下**。約定しない位置に置く
      - Post-Only。**万一その位置が板を叩くなら、注文自体が成立しない**
      - 金額の上限を別に持つ。最小数量が想定外でも歯止めになる
      - 出したら**別の経路で板を読み**、並んでいることを確かめる
      - 確かめたら**必ず取り消す**。取り消せなければ大きく警告する

    買いだけを出す。売りは現物を持っていないと出せない。
    """
    amount, source = _minimum_amount(broker, pair)
    limit = price * (1.0 - TEST_ORDER_MARGIN)
    order = Order(pair, "buy", amount, limit)

    conform = getattr(broker, "conform", None)
    if conform is not None:
        order = conform(order)

    notional = order.notional(price)
    print()
    print("=" * 70)
    print("テスト注文 — **実際に発注します**")
    print("=" * 70)
    print(f"  銘柄     : {pair}")
    print(f"  数量     : {order.amount}（最小数量 / 出どころ: {source}）")
    print(f"  指値     : {order.price:,.0f} 円（現在値 {price:,.0f} の "
          f"{TEST_ORDER_MARGIN * 100:.0f}% 下）")
    print(f"  想定金額 : {notional:,.0f} 円")
    print()

    if notional > MAX_TEST_ORDER_JPY:
        print(f"中止: {notional:,.0f} 円は上限 {MAX_TEST_ORDER_JPY:,.0f} 円を超えます。",
              file=sys.stderr)
        print("      最小数量が想定と違う可能性があります。確かめてください。",
              file=sys.stderr)
        journal.write("test_order_refused", pair=pair, notional=notional)
        return 1

    # --- 出す -------------------------------------------------------------
    try:
        response = broker.place_order(order)
    except BrokerError as exc:
        print(f"  発注できませんでした: {exc}", file=sys.stderr)
        print()
        print("  よくある原因:")
        print("    - 残高が足りない（入金が反映されていない）")
        print("    - APIキーに注文の権限が付いていない")
        print("    - 最小注文数量や刻み幅の解釈が違う")
        journal.write("test_order_failed", pair=pair, reason=str(exc))
        return 1

    order_id = response.get("orderId")
    print(f"  出しました。注文番号 {order_id}")
    journal.write("test_order_placed", pair=pair, order_id=str(order_id),
                  amount=order.amount, price=order.price)

    # --- 別の経路で確かめる -------------------------------------------------
    # 発注の応答と、実際に板に並んでいることは**別の事実**になる。
    # 応答だけを信じると、応答の解釈が間違っていたときに気づけない
    print()
    print("  板を読み直して、並んでいるか確かめます")
    listed = None
    try:
        for row in broker.active_orders(pair):
            if str(row.get("orderId")) == str(order_id):
                listed = row
                break
    except BrokerError as exc:
        print(f"  板を読めませんでした: {exc}", file=sys.stderr)

    if listed is not None:
        print(f"    並んでいます: {listed.get('side')} {listed.get('size')} "
              f"@ {listed.get('price')}  状態 {listed.get('status')}")
        print("    **この内容が、出したものと一致しているか確かめてください。**")
    else:
        print("    見つかりませんでした。次のどれかです。")
        print("      - Post-Only で弾かれた（その位置が板を叩いた）")
        print("      - 応答の解釈が違っていて、別の注文番号を見ている")
        print("      - すでに約定した（**5%下なので、ふつう起きません**）")

    # --- 必ず取り消す -------------------------------------------------------
    print()
    print("  取り消します")
    try:
        broker.cancel_order(order_id)
        print("    取り消しました")
        journal.write("test_order_cancelled", pair=pair, order_id=str(order_id))
    except BrokerError as exc:
        print(f"    **取り消せませんでした: {exc}**", file=sys.stderr)
        print(f"    **取引所の画面で、注文番号 {order_id} を手で取り消してください。**",
              file=sys.stderr)
        journal.write("test_order_cancel_failed", pair=pair,
                      order_id=str(order_id), reason=str(exc))
        return 1

    print()
    print("-" * 70)
    if listed is not None:
        print("発注・板の確認・取消がすべて通りました。")
        print("**取引所の画面で、注文が残っていないことを確かめてください。**")
        print("残っていなければ、この経路は実物に対して確かめられたことになります。")
    else:
        print("発注と取消は通りましたが、**板で確かめられませんでした**。")
        print("応答の解釈が正しいと言い切れません。取引所の画面を確認してください。")
    print("-" * 70)
    return 0


def check_connection(
    pairs: list[str], journal: Journal, exchange: str = "bitbank",
    test_order: bool = False,
) -> int:
    """**1円も動かさずに**、本番の配線がどこまで正しいかを確かめる。

    ## なぜこれを最初にやるのか

    `BitbankBroker` は `unverified=True` のまま置いてある。この開発環境から
    取引所に到達できないので、署名の組み立ても応答の解釈も
    **実物に対して一度も確かめていない**。

    確かめる方法は2つある。

      1. 最小額で1回発注して、取引所の画面と突き合わせる
      2. **読むだけの呼び出しで、署名と応答の解釈を確かめる**

    1 は約定リスクを負う。2 は負わない。そして署名の仕組み
    （nonce・HMAC・ヘッダ名）は GET と POST で共通なので、
    **2 が通れば「鍵と署名が正しい」ことは確定する。**

    ## それでも確かめられないもの

    残るのは POST 側だけ、つまり注文本文の形と応答の解釈になる。
    ここは読むだけでは触れない。だから本文を**組み立てて表示する**。
    実際に送る `order_body()` をそのまま呼ぶので、表示と送信内容はずれない。

    ## 鍵の権限について

    **出金権限は付けないこと。** 取引権限だけで足りる。
    この確認に必要なのは資産照会だけであり、それすら読むだけになる。
    """
    key, secret, key_name, secret_name = _credentials(exchange)
    if not key or not secret:
        print(f"エラー: {key_name} と {secret_name} を環境変数で渡してください",
              file=sys.stderr)
        print("       出金権限は付けないこと。取引権限だけで足ります。", file=sys.stderr)
        return 1

    broker = EXCHANGES[exchange](api_key=key, api_secret=secret)
    print(f"接続  : {broker.name}")
    print("**読むだけです。注文は出しません。**")
    print()

    # --- 0. 取引所が開いているか -----------------------------------------
    # メンテナンス中の失敗は配線の問題ではない。
    # 切り分けられないと、直っているものを直そうとして時間を溶かす
    status_of = getattr(broker, "exchange_status", None)
    if status_of is not None:
        try:
            status = status_of()
            print(f"0. 取引所の状態 — {status}")
            if status != "OPEN":
                print("   ※ いま開いていません。この先が失敗しても配線のせいとは限りません")
        except BrokerError as exc:
            print(f"0. 取引所の状態 — 取れませんでした（{exc}）")
        print()

    # --- 1. 公開API（署名なし）------------------------------------------
    print("1. 公開API（署名なし）— 価格が取れるか")
    prices: dict[str, float] = {}
    for pair in pairs:
        try:
            prices[pair] = broker.fetch_price(pair)
            print(f"   OK  {pair:<12} {prices[pair]:>14,.0f} 円")
        except BrokerError as exc:
            print(f"   NG  {pair:<12} {exc}", file=sys.stderr)
    if not prices:
        print("\n公開APIに到達できていません。ここが通らなければ先はありません。",
              file=sys.stderr)
        journal.write("connection_check", stage="public", ok=False)
        return 1

    # --- 2. 私設API（署名あり）------------------------------------------
    print()
    print("2. 私設API（署名あり）— 鍵・nonce・HMAC・応答の解釈")
    try:
        balances = broker.fetch_balances()
    except BrokerError as exc:
        print(f"   NG  {exc}", file=sys.stderr)
        print()
        print("   よくある原因:")
        print("     - 鍵か秘密鍵の取り違え（ACCESS-KEY と署名の鍵は別物です）")
        print("     - APIキーに取引権限が付いていない")
        print("     - 接続元IPの制限に、今いる場所が入っていない")
        print("     - 端末の時計がずれている（nonce は現在時刻から作ります）")
        journal.write("connection_check", stage="private", ok=False, error=str(exc))
        return 1

    print("   OK  署名が通り、応答が返りました")
    print()
    equity = balances.get("jpy", 0.0)
    if not balances:
        # **空の応答は、2つのことを同時に意味しうる。**
        #   1. 口座に資産が無い（正しく読めている）
        #   2. 応答の解釈を間違えていて、何も拾えていない
        # 見分けがつかないので、「読めました」で済ませない。
        # ここを濁すと、確かめていないものを確かめたことにしてしまう
        print("   ※ **資産が1件も返っていません。**")
        print("      これは次の2つを区別できません。")
        print("        1. 口座に資産がない（正しく読めている）")
        print("        2. 応答の解釈を間違えていて、何も拾えていない")
        print("      **入金してから、もう一度これを実行してください。**")
        print("      金額が画面と一致して、はじめて読み取り側が確かめられます。")
        print()
    for asset, amount in sorted(balances.items()):
        pair = f"{asset}_jpy"
        if asset == "jpy":
            print(f"     {asset:<6} {amount:>18,.4f}")
        else:
            value = amount * prices.get(pair, 0.0)
            equity += value
            note = "" if pair in prices else "  ← 価格未取得のため総額に入れていません"
            print(f"     {asset:<6} {amount:>18.8f}  ≒ {value:>12,.0f} 円{note}")
    print(f"     {'合計':<6} {'':>18} ≒ {equity:>12,.0f} 円")
    if balances:
        print()
        print("   **この数字を取引所の画面と突き合わせてください。**")
        print("   合わなければ、応答の解釈が間違っています。")

    # --- 3. 送らずに、送る中身を見る --------------------------------------
    print()
    print("3. 発注本文 — **組み立てるだけで、送りません**")
    for pair in pairs:
        if pair not in prices:
            continue
        amount, source = _minimum_amount(broker, pair)
        # 現在値から離した指値。すぐには約定しない位置に置く想定
        order = Order(pair, "buy", amount, round(prices[pair] * 0.995))
        conform = getattr(broker, "conform", None)
        if conform is not None:
            try:
                order = conform(order)
            except BrokerError as exc:
                print(f"   {pair}: 注文ルールに合わせられませんでした — {exc}")
                continue
        body = broker.order_body(order)
        print(f"   POST {getattr(broker, 'order_path', '/v1/order')}  {body}")
        print(f"     ≒ {order.notional(prices[pair]):,.0f} 円相当"
              f"（最小数量 {amount} / 出どころ: {source}）")

    journal.write("connection_check", exchange=exchange, stage="private", ok=True,
                  balances=balances, prices=prices, equity=equity)

    print()
    print("-" * 70)
    if balances:
        print("確かめられたこと : 鍵・署名・時刻・ヘッダ・応答の解釈（読み取り側）")
        print("確かめていないこと: 発注の応答の解釈、板に並ぶかどうか")
    else:
        print("確かめられたこと : 鍵・署名・時刻・ヘッダ（取引所が受理した）")
        print("確かめていないこと: **応答の解釈**（資産が空なので突き合わせられない）、")
        print("                    発注の応答の解釈、板に並ぶかどうか")
    if not test_order:
        print()
        print("残りを確かめるには、上の本文を1回だけ実際に送る必要があります。")
        print("  --send-test-order を付けると、最小数量・現在値の5%下の指値を")
        print("  1件だけ出し、板を読んで確かめ、取り消すところまでやります。")
        print("  **約定しない位置なので、損失は出ません。**")
    print("-" * 70)

    if not test_order:
        return 0

    if not balances:
        print()
        print("テスト注文は見送ります: **残高がありません。**", file=sys.stderr)
        print("入金が反映されてから、もう一度実行してください。", file=sys.stderr)
        return 1

    target = pairs[0]
    if target not in prices:
        print(f"\nテスト注文は見送ります: {target} の価格が取れていません", file=sys.stderr)
        return 1
    return send_test_order(broker, target, prices[target], journal)


def _price_ranges(
    pending: list[dict], fallback: dict[str, float]
) -> dict[str, tuple[float, float]]:
    """板に置いてからの値動きの幅（安値, 高値）を、銘柄ごとに返す。

    ## 起点は「注文を出した時刻」であって、その日の始まりではない

    09:00 に指値を置いたのに、03:00 に付いた安値で「約定した」と判定すると、
    **約定を過大に見積もる**ことになる。板に置く前の値動きでは約定しない。

    この基盤は同じ論点で既に2回間違えている。
      1回目 出した瞬間に約定させ、0.05% の利益を無から作った
      2回目 瞬間の価格だけで見て、実際には約定していたものを見逃した
    どちらに倒しても嘘になるので、**置いた時刻から数える**。

    1時間足で求める。取れなければ現在値で代用するが、
    その場合は約定を過小に見積もるので、呼び出し側でそう表示する。

    ## 足の出どころは bitbank に固定してある

    取引所をまたいだ値差のぶん、判定はわずかにずれる。ペーパーで確かめるのは
    **配線であって成績ではない**ので許容するが、黙ってやると気づけない。
    `--exchange` が bitbank でないときは、呼び出し側でその旨を表示する。
    """
    import datetime as _dt
    import json as _json
    import urllib.request as _req

    by_pair: dict[str, str] = {}
    for o in pending:
        placed = o.get("placed_at")
        if placed and (o["pair"] not in by_pair or placed < by_pair[o["pair"]]):
            by_pair[o["pair"]] = placed

    out: dict[str, tuple[float, float]] = {}
    for pair, placed_at in by_pair.items():
        price = fallback.get(pair)
        span = (price, price) if price else None
        try:
            since = _dt.datetime.strptime(placed_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=_dt.timezone.utc
            )
            now = _dt.datetime.now(_dt.timezone.utc)
            days = [
                (since + _dt.timedelta(days=i)).strftime("%Y%m%d")
                for i in range((now.date() - since.date()).days + 1)
            ][:8]  # 取りすぎない

            lows, highs = [], []
            for day in days:
                url = f"https://public.bitbank.cc/{pair}/candlestick/1hour/{day}"
                with _req.urlopen(url, timeout=15) as resp:
                    payload = _json.loads(resp.read())
                for _o, h, low, _c, _v, ts in payload["data"]["candlestick"][0]["ohlcv"]:
                    bar = _dt.datetime.fromtimestamp(int(ts) / 1000, _dt.timezone.utc)
                    # **置いた時刻より前のバーは使わない**
                    if bar >= since - _dt.timedelta(hours=1):
                        highs.append(float(h))
                        lows.append(float(low))
            if lows:
                span = (min(lows), max(highs))
                if price:
                    span = (min(span[0], price), max(span[1], price))
        except Exception:
            pass
        if span:
            out[pair] = span
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="目標の保有に近づける")
    p.add_argument("--strategy", choices=sorted(TARGETS),
                   help="目標を決める方針")
    p.add_argument("--live", action="store_true",
                   help="本番で発注する（関門をすべて通った場合のみ動きます）")
    p.add_argument("--check-connection", action="store_true",
                   help=("取引所につながるかだけを確かめる。**注文は出しません。**"
                         "戦略も検証記録も要りません"))
    p.add_argument("--exchange", default="bitbank", choices=sorted(EXCHANGES),
                   help="つなぐ取引所。鍵の環境変数名もこれで決まります")
    p.add_argument("--send-test-order", action="store_true",
                   help=("**実際に1件だけ発注します。** 最小数量・現在値の5%%下の指値を"
                         "出し、板を読んで確かめ、取り消します。--check-connection と"
                         "一緒に使います"))
    p.add_argument("--pairs", default="btc_jpy",
                   help="価格を取る銘柄（カンマ区切り）")
    p.add_argument("--state", type=Path, default=Path("trading/data/paper_state.json"),
                   help="ペーパー用の保有状態ファイル")
    p.add_argument("--paper-capital", type=float, default=0.0,
                   help="ペーパーの初期資金。状態ファイルが空のときだけ入れる")
    p.add_argument("--journal", type=Path, default=Path("trading/data/journal.jsonl"),
                   help="記録の出力先")
    p.add_argument("--validation", type=Path, default=Path("trading/data/validation.json"),
                   help="事前登録した検定の合格記録")
    p.add_argument("--initial-equity", type=float, default=0.0,
                   help="運用開始時の資産（円）。損失の上限判定に使う")
    p.add_argument("--max-per-run", type=float, default=50_000.0)
    p.add_argument("--max-per-order", type=float, default=20_000.0)
    p.add_argument("--max-exposure", type=float, default=100_000.0)
    p.add_argument("--market", action="store_true",
                   help="指値ではなく成行で出す（往復コストが約9倍になります）")
    p.add_argument("--give-up-after", type=int, default=3,
                   help=("指値がこの回数届かなかったら成行に切り替える。"
                         "粘りすぎると目標にたどり着けないまま相場が離れる"))
    args = p.parse_args()

    journal = Journal(args.journal)
    pairs = [s.strip() for s in args.pairs.split(",") if s.strip()]

    if args.check_connection:
        print("=" * 70)
        print(f"接続確認  {args.exchange}  — 発注しません")
        print("=" * 70)
        return check_connection(pairs, journal, args.exchange, args.send_test_order)

    if args.send_test_order:
        p.error("--send-test-order は --check-connection と一緒に使ってください")

    if not args.strategy:
        p.error("--strategy が必要です（--check-connection のときだけ省けます）")

    mode = "本番" if args.live else "ペーパー"

    print("=" * 70)
    print(f"執行  {mode}  戦略: {args.strategy}")
    print("=" * 70)

    # --- 取引所につなぐ --------------------------------------------------
    if args.live:
        key, secret, key_name, secret_name = _credentials(args.exchange)
        if not key or not secret:
            print(f"エラー: {key_name} と {secret_name} を環境変数で渡してください",
                  file=sys.stderr)
            return 1
        broker = EXCHANGES[args.exchange](api_key=key, api_secret=secret)
        print(f"接続  : {broker.name}")
        if broker.unverified:
            print("  ※ この発注経路は実物に対して検証されていません。")
            print("     最小額で1回動かし、取引所の画面と突き合わせてください。")
    else:
        broker = PaperBroker(state_path=args.state)
        if args.paper_capital > 0 and not broker.fetch_balances().get("jpy"):
            broker.deposit("jpy", args.paper_capital)
            print(f"ペーパーに {args.paper_capital:,.0f} 円を置きました")
        print(f"接続  : {broker.name}")

    # --- 1. 現在地を読む（記憶に頼らない）--------------------------------
    try:
        prices = {pair: broker.fetch_price(pair) for pair in pairs}
    except BrokerError as exc:
        # ペーパーは価格を持たないので、公開APIから取ってくる
        if args.live:
            print(f"エラー: 価格を取得できません。{exc}", file=sys.stderr)
            return 1
        # ペーパーでも価格は本物を使う。取引所は選んだものに合わせる
        pub = EXCHANGES[args.exchange](api_key="", api_secret="")
        try:
            prices = {pair: pub.fetch_price(pair) for pair in pairs}
        except BrokerError as exc2:
            print(f"エラー: 価格を取得できません。{exc2}", file=sys.stderr)
            return 1
        broker.set_prices(prices)

    # 板に残っている注文を、まず片付ける。
    #   1. 前回からの値動きが指値に届いていたものは約定させる
    #   2. 届かなかったものは取り消して資金を戻す
    # これをやらないと、前回の指値に資金が取られたまま新しい注文を出すことになる
    if isinstance(broker, PaperBroker):
        broker.set_prices(prices)
        pending = broker.open_orders()
        if not pending:
            print("  板に残っている注文はありません")
        else:
            print(f"  板に {len(pending)} 件残っています。"
                  "置いてからの値動きで約定を判定します")
            if args.exchange != "bitbank":
                print("  ※ 約定判定に使う足は bitbank のものです。"
                      f"価格は {args.exchange} から取っているので、わずかにずれます")
            # **瞬間の価格ではなく、前回からの値動きの幅で判定する。**
            # 一度でも指値に触れていれば約定しているので、
            # 瞬間値で見ると「約定しなかった」と嘘をつくことになる
            ranges = _price_ranges(pending, prices)
            for fill in broker.settle(ranges):
                print(f"  約定していました: {fill['side']} {fill['pair']} "
                      f"{fill['amount']:.8f} @ {fill['price']:,.0f}")
                journal.write("settled", **fill)
            for miss in broker.open_orders():
                gap = abs(miss["closest"] / miss["price"] - 1) * 100
                print(f"  届きませんでした: {miss['pair']} 指値 {miss['price']:,.0f} / "
                      f"最も近づいた値 {miss['closest']:,.0f}（あと {gap:.3f}%）")
                journal.write("expired", **miss)
            cancelled = broker.cancel_all()
            if cancelled:
                print(f"  板に残っていた {cancelled} 件を取り消しました")

    balances = broker.fetch_balances()
    weights, equity = current_weights(balances, prices)
    exposure = exposure_jpy(balances, prices)

    print()
    print(f"現在の総資産: {equity:,.0f} 円")
    for pair, w in sorted(weights.items()):
        print(f"  {pair:<12} {w * 100:6.2f} %  ({balances.get(pair.split('_')[0], 0):.8f})")
    print(f"  {'現金':<12} {balances.get('jpy', 0.0) / equity * 100 if equity else 0:6.2f} %")

    journal.write("state", mode=mode, equity=equity, balances=balances, prices=prices)

    # --- 2〜3. 目標と差分 -------------------------------------------------
    target = TARGETS[args.strategy](prices)

    # 指値で粘り続けると、目標にたどり着けないまま相場が離れていく。
    # 何度も届かなかった銘柄は、諦めて成行に切り替える。
    # **「安く買えるかもしれない」より「持つべきものを持つ」を優先する。**
    stubborn = {p for p in pairs if journal.consecutive_misses(p) >= args.give_up_after}
    if stubborn and not args.market:
        for pair in sorted(stubborn):
            print(f"\n  {pair} は指値が {journal.consecutive_misses(pair)} 回届きませんでした。"
                  "成行に切り替えます")

    orders, _ = build_orders(
        target, balances, prices,
        limit_offset=None if args.market else 0.0005,
    )
    if stubborn and not args.market:
        orders = [
            Order(o.pair, o.side, o.amount, None) if o.pair in stubborn else o
            for o in orders
        ]

    print()
    print("目標:")
    for pair, w in sorted(target.weights.items()):
        print(f"  {pair:<12} {w * 100:6.2f} %")

    print()
    if not orders:
        print("差分はありません。何もしません。")
        journal.write("no_action", strategy=args.strategy)
        return 0

    print(f"出す注文（{len(orders)} 件）:")
    for o in orders:
        kind = "指値" if o.price else "成行"
        print(f"  {o.side:<5} {o.pair:<12} {o.amount:.8f}  "
              f"{kind} {o.price if o.price else prices[o.pair]:,.0f}  "
              f"≒ {o.notional(prices[o.pair]):,.0f} 円")

    # --- 4. 関門 ----------------------------------------------------------
    validation = None
    if args.validation.exists():
        try:
            validation = ValidationRecord.load(args.validation)
        except (KeyError, ValueError) as exc:
            print(f"\n検証記録を読めません: {exc}", file=sys.stderr)

    limits = Limits(
        max_notional_per_run=args.max_per_run,
        max_notional_per_order=args.max_per_order,
        max_total_exposure=args.max_exposure,
    )
    violations = check(GuardContext(
        strategy=args.strategy, orders=orders, prices=prices,
        equity=equity, initial_equity=args.initial_equity or equity,
        exposure=exposure, limits=limits, validation=validation,
    ))

    print()
    print("-" * 70)
    print(describe(violations))
    print("-" * 70)
    journal.write("guards", strategy=args.strategy,
                  violations=[str(v) for v in violations],
                  orders=[o.__dict__ for o in orders])

    # --- 5. 執行 ----------------------------------------------------------
    if not args.live:
        print()
        print("ペーパーなので、板に置くところまでを再現します（発注はしていません）。")
        resting = 0
        for o in orders:
            try:
                response = broker.place_order(o)
                journal.write("paper_order", status=response["status"], **o.__dict__)
                if response["status"] == "resting":
                    resting += 1
            except BrokerError as exc:
                print(f"  スキップ: {o.pair} {o.side} — {exc}")
                journal.write("paper_reject", reason=str(exc), **o.__dict__)
        if resting:
            print(f"  {resting} 件を板に置きました。"
                  "**指値なので、価格が届くまで約定しません。**")
            print("  次に実行したときに、届いていれば約定します。")
        return 0

    if violations:
        print()
        print("**本番では実行しません。** 上の理由を解消してください。")
        return 2

    print()
    print("関門を通過しました。発注します。")
    placed, failed = 0, 0
    for o in orders:
        try:
            response = broker.place_order(o)
            journal.write("order_placed", response=response, **o.__dict__)
            print(f"  出しました: {o.side} {o.pair} {o.amount:.8f}")
            placed += 1
        except BrokerError as exc:
            journal.write("order_failed", reason=str(exc), **o.__dict__)
            print(f"  失敗: {o.side} {o.pair} — {exc}", file=sys.stderr)
            failed += 1

    print()
    print(f"発注 {placed} 件 / 失敗 {failed} 件。記録: {args.journal}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
