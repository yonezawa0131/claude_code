"""GMOコイン接続の検証。

## ここで守らせるのは「間違えると金が減る3つ」になる

GMOコインは bitbank と作りが違う。違いのうち3つは、間違えても
**エラーにならずに通ってしまう**。通ってしまうものは、テストで止めるしかない。

  1. **銘柄名** — `BTC` が現物、`BTC_JPY` がレバレッジ。
     取り違えると、現物を買ったつもりで建玉を持つ。
     出回っているサンプルコードには `BTC_JPY` で発注しているものがあり、
     真似すると1日0.04%を払い続けることになる
  2. **署名するパス** — URL には `/private` が入るが、署名する文字列には入らない。
     入れると署名が通らない（これは気づける）。**逆に、**
     クエリ文字列を署名に入れてしまうと、GET が通ったり通らなかったりする
  3. **成否の判定** — HTTP 200 でも `status != 0` なら失敗になる。
     見ないと、失敗した注文を成功として記録する

## 署名は既知の値と突き合わせる

「動いた」ではなく「**この入力からはこの署名が出る**」を固定する。
実物に対して確かめられないので、せめて手計算と一致させておく。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.execution.broker import (  # noqa: E402
    GMO_SPOT_SYMBOL,
    BrokerError,
    GmoBroker,
    Order,
)

SYMBOLS = [
    {"symbol": "BTC", "minOrderSize": "0.0001", "maxOrderSize": "5",
     "sizeStep": "0.0001", "tickSize": "1"},
    {"symbol": "BTC_JPY", "minOrderSize": "0.01", "maxOrderSize": "5",
     "sizeStep": "0.01", "tickSize": "1"},
    {"symbol": "XRP", "minOrderSize": "10", "maxOrderSize": "300000",
     "sizeStep": "1", "tickSize": "0.001"},
]


@pytest.fixture
def gmo():
    broker = GmoBroker(api_key="key", api_secret="secret")
    broker._rules = {row["symbol"]: row for row in SYMBOLS}
    return broker


# ---------------------------------------------------------------------------
# 1. 現物とレバレッジ
# ---------------------------------------------------------------------------


def test_spot_symbols_have_no_jpy_suffix(gmo):
    """現物銘柄に `_JPY` が付かないこと。

    **付いているものはレバレッジになる。** ここが対応表の存在理由になる。
    """
    for pair, symbol in GMO_SPOT_SYMBOL.items():
        assert not symbol.endswith("_JPY"), f"{pair} → {symbol} はレバレッジ銘柄です"


def test_a_leverage_symbol_is_refused(gmo):
    """GMO のレバレッジ銘柄を渡されたら拒否すること。**黙って通さない。**

    通してしまうと、現物を買ったつもりで建玉を持つ。
    建玉は1日0.04%かかるので、持っているだけで負けが積み上がる。
    """
    for name in ("BTC_JPY", "ETH_JPY", "XRP_JPY"):
        with pytest.raises(BrokerError, match="レバレッジ"):
            gmo.symbol(name)


def test_case_distinguishes_the_internal_pair_from_the_leverage_symbol(gmo):
    """**綴りが同じで、指すものが違う。**

    内部表記 `btc_jpy`（現物のつもり）と、GMOの `BTC_JPY`（レバレッジ）。
    照合を `upper()` してからやると、内部表記まで巻き込んで全部拒否する。
    実際に一度そう書いて、全銘柄が通らなくなった。
    """
    assert gmo.symbol("btc_jpy") == "BTC"
    with pytest.raises(BrokerError):
        gmo.symbol("BTC_JPY")


def test_the_ordinary_pair_maps_to_spot(gmo):
    """この基盤の `btc_jpy` は、GMOでは**現物の BTC** に対応すること。"""
    assert gmo.symbol("btc_jpy") == "BTC"
    assert gmo.symbol("xrp_jpy") == "XRP"


def test_an_unknown_pair_is_refused_rather_than_guessed(gmo):
    """対応表にない銘柄を、それらしく組み立てないこと。

    `doge_jpy` → `DOGE` と推測して外すと、通らないか、別のものを買う。
    """
    with pytest.raises(BrokerError, match="対応表"):
        gmo.symbol("doge_jpy")


def test_the_order_body_carries_the_spot_symbol(gmo):
    body = gmo.order_body(Order("btc_jpy", "buy", 0.0001, 9_950_000))
    assert body["symbol"] == "BTC", "レバレッジ銘柄で発注しようとしています"
    assert body["side"] == "BUY"
    assert body["executionType"] == "LIMIT"


# ---------------------------------------------------------------------------
# 板に並ぶ注文だけを出す / 取り消す
# ---------------------------------------------------------------------------


def test_a_limit_order_is_post_only(gmo):
    """**指値は板に並ぶ注文としてだけ出すこと。**

    GMO の `timeInForce: "SOK"`（Post-Only）は、その指値が出した瞬間に
    約定してしまう位置なら、注文自体を成立させない。

    付けないと、板を叩いた指値がテイカーになる。取引所現物では
    メイカー −0.01%（受け取り）に対しテイカー +0.05%（支払い）で、**符号が変わる**。
    往復 0.12pt の差は、この基盤が測った「必要な粗利 18bp」の水準では無視できない。
    """
    body = gmo.order_body(Order("btc_jpy", "buy", 0.0001, 9_950_000))
    assert body["timeInForce"] == "SOK"


def test_a_market_order_is_not_post_only(gmo):
    """成行に Post-Only は付かないこと。付けたら成立しない。"""
    body = gmo.order_body(Order("btc_jpy", "buy", 0.0001))
    assert "timeInForce" not in body


def test_cancel_sends_a_numeric_order_id(gmo, monkeypatch):
    """注文番号を数値で送ること。発注の応答は文字列で返ることがある。"""
    sent = {}
    monkeypatch.setattr(gmo, "_open", lambda req: sent.update(
        body=json.loads(req.data), url=req.full_url) or {})
    gmo.cancel_order("12345")

    assert sent["body"] == {"orderId": 12345}
    assert sent["url"].endswith("/private/v1/cancelOrder")


def test_active_orders_unwraps_the_list(gmo, monkeypatch):
    monkeypatch.setattr(gmo, "_open", lambda _req: {
        "pagination": {"currentPage": 1}, "list": [{"orderId": 1}, {"orderId": 2}]})
    assert [o["orderId"] for o in gmo.active_orders("btc_jpy")] == [1, 2]


def test_active_orders_tolerates_an_empty_response(gmo, monkeypatch):
    """板が空のとき、落ちずに空リストを返すこと。"""
    monkeypatch.setattr(gmo, "_open", lambda _req: None)
    assert gmo.active_orders("btc_jpy") == []


# ---------------------------------------------------------------------------
# 2. 署名
# ---------------------------------------------------------------------------


def test_the_signature_matches_a_hand_computed_value(gmo, monkeypatch):
    """既知の入力から、既知の署名が出ること。

    実物に対して確かめられない以上、せめて手計算と一致させておく。
    """
    monkeypatch.setattr("trading.src.execution.broker.time.time", lambda: 1_700_000.0)
    timestamp, signature = gmo.sign("GET", "/v1/account/assets")

    assert timestamp == "1700000000"
    expected = hmac.new(
        b"secret", b"1700000000GET/v1/account/assets", hashlib.sha256
    ).hexdigest()
    assert signature == expected


def test_the_signed_path_excludes_private(gmo, monkeypatch):
    """署名する文字列に `/private` を入れないこと。

    URL には入るので混同しやすい。入れると署名が通らない。
    """
    monkeypatch.setattr("trading.src.execution.broker.time.time", lambda: 1_700_000.0)
    _, right = gmo.sign("GET", "/v1/account/assets")
    _, wrong = gmo.sign("GET", "/private/v1/account/assets")
    assert right != wrong

    sent = {}
    monkeypatch.setattr(gmo, "_open", lambda req: sent.update(
        url=req.full_url, headers=dict(req.headers)) or [])
    gmo.fetch_balances()

    assert sent["url"] == "https://api.coin.z.com/private/v1/account/assets"
    assert sent["headers"]["Api-sign"] == right, "URLのパスをそのまま署名しています"


def test_the_post_body_signed_is_the_body_sent(gmo, monkeypatch):
    """署名した本文と、送る本文が**1バイトも違わない**こと。

    別々に組み立てると、空白の入り方だけで署名が通らなくなる。
    """
    monkeypatch.setattr("trading.src.execution.broker.time.time", lambda: 1_700_000.0)
    sent = {}
    monkeypatch.setattr(gmo, "_open", lambda req: sent.update(
        body=req.data, headers=dict(req.headers)) or "ORDER-ID")

    gmo.place_order(Order("btc_jpy", "buy", 0.0001, 9_950_000))

    body = sent["body"].decode()
    expected = hmac.new(
        b"secret", ("1700000000POST/v1/order" + body).encode(), hashlib.sha256
    ).hexdigest()
    assert sent["headers"]["Api-sign"] == expected
    assert json.loads(body)["symbol"] == "BTC"


def test_a_get_carries_no_body(gmo, monkeypatch):
    monkeypatch.setattr(gmo, "_open", lambda req: (_ for _ in ()).throw(
        AssertionError("GETに本文が付いています")) if req.data else [])
    gmo.fetch_balances()


# ---------------------------------------------------------------------------
# 3. HTTP 200 でも失敗していることがある
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_a_200_with_a_nonzero_status_is_an_error(gmo, monkeypatch):
    """`status != 0` を失敗として扱うこと。

    見ないと、**失敗した注文を成功として記録する**。
    記録が嘘になると、次の実行が誤った現在地から始まる。
    """
    monkeypatch.setattr(
        "trading.src.execution.broker.urllib.request.urlopen",
        lambda *_a, **_kw: _FakeResponse({
            "status": 1,
            "messages": [{"message_code": "ERR-5106", "message_string": "Invalid parameter."}],
        }),
    )
    with pytest.raises(BrokerError, match="ERR-5106"):
        gmo.fetch_price("btc_jpy")


def test_a_successful_envelope_is_unwrapped(gmo, monkeypatch):
    monkeypatch.setattr(
        "trading.src.execution.broker.urllib.request.urlopen",
        lambda *_a, **_kw: _FakeResponse(
            {"status": 0, "data": [{"symbol": "BTC", "last": "9990000"}]}
        ),
    )
    assert gmo.fetch_price("btc_jpy") == pytest.approx(9_990_000.0)


def test_balances_use_available_not_amount(gmo, monkeypatch):
    """板に置いた注文に取られている分を、使える額に数えないこと。

    `amount` を使うと、同じ資金を二重に使えることにしてしまう。
    """
    monkeypatch.setattr(gmo, "_open", lambda _req: [
        {"symbol": "JPY", "amount": "300000", "available": "250000"},
        {"symbol": "BTC", "amount": "0.01", "available": "0.004"},
        {"symbol": "ETH", "amount": "0", "available": "0"},
    ])
    balances = gmo.fetch_balances()
    assert balances == {"jpy": 250_000.0, "btc": 0.004}


# ---------------------------------------------------------------------------
# 注文ルールは取引所から読む
# ---------------------------------------------------------------------------


def test_the_size_is_rounded_down_to_the_step(gmo):
    """数量は**切り捨てる**こと。意図より多く出さない。"""
    conformed = gmo.conform(Order("btc_jpy", "buy", 0.000199, 9_950_000))
    assert conformed.amount == pytest.approx(0.0001)


def test_a_size_below_the_minimum_is_refused(gmo):
    with pytest.raises(BrokerError, match="最小注文数量"):
        gmo.conform(Order("btc_jpy", "buy", 0.00005, 9_950_000))


def test_the_price_is_rounded_to_the_passive_side(gmo):
    """買いは切り下げ、売りは切り上げること。

    どちらも板に並ぶ側に寄る。逆に丸めると、意図せずテイカーになりうる。
    """
    buy = gmo.conform(Order("btc_jpy", "buy", 0.001, 9_950_000.7))
    sell = gmo.conform(Order("btc_jpy", "sell", 0.001, 9_950_000.2))
    assert buy.price == pytest.approx(9_950_000.0)
    assert sell.price == pytest.approx(9_950_001.0)


def test_a_coarse_step_is_respected(gmo):
    """XRP は刻みが1。0.0001刻みで送ると弾かれる。"""
    conformed = gmo.conform(Order("xrp_jpy", "buy", 123.7, 80.0))
    assert conformed.amount == pytest.approx(123.0)


def test_rules_come_from_the_exchange_not_from_memory(monkeypatch):
    """最小数量を、こちらの記憶ではなく取引所から取ること。

    取引所が変えた日から、記憶で持っている値は嘘になる。
    """
    broker = GmoBroker(api_key="k", api_secret="s")
    calls = []
    monkeypatch.setattr(broker, "_public_get",
                        lambda path: calls.append(path) or SYMBOLS)

    assert broker.trading_rules("btc_jpy")["minOrderSize"] == "0.0001"
    assert calls == ["/v1/symbols"]

    broker.trading_rules("xrp_jpy")
    assert calls == ["/v1/symbols"], "毎回取りに行っています"


def test_the_smallest_size_is_not_sent_in_scientific_notation(gmo):
    """**`1e-05` を送らないこと。**

    GMO の BTC 現物の最小注文数量は 0.00001。Python の `str()` は
    これを `'1e-05'` にする。つまり**最小数量で出すたびに**指数表記になる。

    「一番小さい注文から順に試す」のは、確認の手順として一番やりたいこと。
    そこだけ通らないのが一番たちが悪い。しかも症状は「注文が弾かれる」なので、
    署名を疑って時間を溶かすことになる。

    実際に接続確認の出力にこの形が出た。送る前に気づけた。
    """
    gmo._rules["BTC"] = {**gmo._rules["BTC"], "minOrderSize": "0.00001",
                         "sizeStep": "0.00001"}
    body = gmo.order_body(gmo.conform(Order("btc_jpy", "buy", 0.00001, 9_985_024.0)))

    assert body["size"] == "0.00001", f"指数表記です: {body['size']}"
    assert "e" not in body["size"].lower()
    assert "e" not in body["price"].lower()


def test_a_whole_price_has_no_trailing_zero(gmo):
    """刻みが1の銘柄で `9985024.0` と送らないこと。"""
    body = gmo.order_body(Order("btc_jpy", "buy", 0.001, 9_985_024.0))
    assert body["price"] == "9985024"


def test_plain_decimal_covers_both_directions():
    from trading.src.execution.broker import plain_decimal

    assert plain_decimal(0.00001) == "0.00001"
    assert plain_decimal(9_985_024.0) == "9985024"
    assert plain_decimal(0.0001) == "0.0001"
    assert plain_decimal(123.45) == "123.45"


def test_placing_an_order_conforms_first(gmo, monkeypatch):
    """発注の直前に丸めること。丸め忘れた注文が取引所に届かないこと。"""
    sent = {}
    monkeypatch.setattr(gmo, "_open", lambda req: sent.update(
        body=json.loads(req.data)) or "ID")
    gmo.place_order(Order("btc_jpy", "buy", 0.000199, 9_950_000.7))
    assert sent["body"]["size"] == "0.0001"
    assert sent["body"]["price"] == "9950000"
