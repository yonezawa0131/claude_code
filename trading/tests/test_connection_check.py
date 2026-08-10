"""接続確認の検証。

## この確認が守らなければならない一線

**1円も動かさないこと。**

接続確認は、本番の鍵を使って本番のAPIを叩く。ここで誤って注文が出れば、
「安全な確認」だと思って実行した操作が、そのまま実弾になる。

だからこのファイルが固定するのは機能ではなく**不作為**になる。
何をするかより、**何をしないか**を壊れない形にする。

もうひとつ守らせるのは、表示と送信内容が一致することになる。
表示用に本文を組み立て直すと、いずれずれる。ずれた本文を見て
「確認した」と思い込むほうが、確認しないより危ない。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.run_live import (  # noqa: E402
    EXCHANGES,
    MIN_ORDER_AMOUNT,
    check_connection,
    main,
)
from trading.src.execution.broker import BitbankBroker, BrokerError, Order  # noqa: E402
from trading.src.execution.journal import Journal  # noqa: E402


# ---------------------------------------------------------------------------
# 送らずに、送る中身を見る
# ---------------------------------------------------------------------------


def test_the_body_shown_is_the_body_sent(monkeypatch):
    """**表示する本文と、実際に送る本文が同じものであること。**

    別々に組み立てると、片方だけ直したときに黙ってずれる。
    ずれた本文で「確認した」と思い込むのが、この確認の最悪の失敗になる。
    """
    broker = BitbankBroker(api_key="k", api_secret="s")
    order = Order("btc_jpy", "buy", 0.0001, 9_950_000.0)

    sent: dict = {}

    def fake_post(path, body):
        sent["path"] = path
        sent["body"] = body
        return {}

    monkeypatch.setattr(broker, "_signed_post", fake_post)
    broker.place_order(order)

    assert sent["body"] == broker.order_body(order)
    assert sent["path"] == "/user/spot/order"


def test_order_body_does_not_reach_the_network(monkeypatch):
    """本文を組み立てるだけでは、どこにも送らないこと。"""

    def explode(*_a, **_kw):
        raise AssertionError("本文の組み立てで通信が起きています")

    monkeypatch.setattr(BitbankBroker, "_send", explode)
    body = BitbankBroker("k", "s").order_body(Order("btc_jpy", "buy", 0.0001, 9_950_000.0))
    assert body["pair"] == "btc_jpy"
    assert body["post_only"] is True, "板に並べる注文だけを出すこと"


def test_a_market_order_body_carries_no_price():
    body = BitbankBroker("k", "s").order_body(Order("btc_jpy", "buy", 0.0001))
    assert body["type"] == "market"
    assert "price" not in body
    assert "post_only" not in body


# ---------------------------------------------------------------------------
# 何をしないか
# ---------------------------------------------------------------------------


class _ReadOnlyBroker:
    """発注しようとしたら失敗する見張り役。"""

    name = "見張り"
    unverified = True

    def __init__(self):
        self.balances_read = 0

    def fetch_price(self, pair):
        return {"btc_jpy": 10_000_000.0, "eth_jpy": 500_000.0}[pair]

    def fetch_balances(self):
        self.balances_read += 1
        return {"jpy": 300_000.0, "btc": 0.005}

    def order_body(self, order):
        return BitbankBroker.order_body(self, order)

    def place_order(self, order):  # pragma: no cover - 呼ばれてはいけない
        raise AssertionError("接続確認が発注しました。**これは絶対に起きてはいけません**")


@pytest.fixture
def spy(monkeypatch, tmp_path):
    watcher = _ReadOnlyBroker()
    monkeypatch.setitem(EXCHANGES, "bitbank", lambda **_kw: watcher)
    monkeypatch.setenv("BITBANK_API_KEY", "key")
    monkeypatch.setenv("BITBANK_API_SECRET", "secret")
    return watcher


def test_the_check_never_places_an_order(spy, tmp_path, capsys):
    """接続確認は、どんな経路でも発注に到達しないこと。

    `_ReadOnlyBroker.place_order` は呼ばれた時点で失敗する。
    """
    journal = Journal(tmp_path / "j.jsonl")
    assert check_connection(["btc_jpy"], journal) == 0
    assert spy.balances_read == 1

    out = capsys.readouterr().out
    assert "注文は出しません" in out


def test_the_check_needs_no_strategy_and_no_validation(spy, tmp_path, monkeypatch, capsys):
    """戦略も検証記録もなしに通ること。

    ここで検証記録を要求すると、**検証を通った戦略がまだ1つもない**この基盤では
    配線の確認そのものができなくなる。確認と発注許可は別の問題になる。
    """
    monkeypatch.setattr(sys, "argv", [
        "run_live.py", "--check-connection",
        "--journal", str(tmp_path / "j.jsonl"),
    ])
    assert main() == 0
    assert "接続確認" in capsys.readouterr().out


def test_missing_credentials_stop_before_any_call(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("BITBANK_API_KEY", raising=False)
    monkeypatch.delenv("BITBANK_API_SECRET", raising=False)
    monkeypatch.setitem(
        EXCHANGES, "bitbank",
        lambda **_kw: pytest.fail("鍵がないのに接続しようとしました"),
    )
    journal = Journal(tmp_path / "j.jsonl")
    assert check_connection(["btc_jpy"], journal) == 1
    assert "出金権限は付けないこと" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 失敗したときに、原因が分かること
# ---------------------------------------------------------------------------


def test_a_signing_failure_is_reported_as_such(spy, tmp_path, capsys):
    """署名が通らなかったとき、心当たりを出すこと。

    `HTTP 401` だけ出しても、何を直せばいいか分からない。
    """
    def fail():
        raise BrokerError("取引所がエラーを返しました（code=20003）")

    spy.fetch_balances = fail
    journal = Journal(tmp_path / "j.jsonl")
    assert check_connection(["btc_jpy"], journal) == 1

    captured = capsys.readouterr()
    assert "取引権限" in captured.out, "何を確かめればよいかが出ていません"
    assert "時計がずれている" in captured.out

    record = journal.read_all()[-1]
    assert record["stage"] == "private"
    assert record["ok"] is False
    assert "20003" in record["error"], "取引所が返したコードを残すこと"


def test_a_public_api_failure_stops_before_using_the_key(spy, tmp_path):
    """公開APIが通らないなら、鍵を使う前に止まること。

    ここが通らない原因は鍵ではない。鍵を送っても切り分けにならない。
    """
    def fail(_pair):
        raise BrokerError("到達できません")

    spy.fetch_price = fail
    spy.fetch_balances = lambda: pytest.fail("公開APIが落ちているのに鍵を使いました")

    journal = Journal(tmp_path / "j.jsonl")
    assert check_connection(["btc_jpy"], journal) == 1
    assert journal.read_all()[-1]["stage"] == "public"


# ---------------------------------------------------------------------------
# 記録
# ---------------------------------------------------------------------------


def test_the_result_is_recorded(spy, tmp_path):
    """確認したことが残ること。

    「いつ確認したか」が残っていないと、**確認したつもり**で本番に進める。
    """
    journal = Journal(tmp_path / "j.jsonl")
    check_connection(["btc_jpy"], journal)

    record = journal.read_all()[-1]
    assert record["event"] == "connection_check"
    assert record["ok"] is True
    assert record["equity"] == pytest.approx(300_000.0 + 0.005 * 10_000_000.0)


def test_an_empty_balance_is_not_reported_as_verified(spy, tmp_path, capsys):
    """**資産が空のとき、「読めました」で済ませないこと。**

    空の応答は2つのことを同時に意味しうる。

      1. 口座に資産がない（正しく読めている）
      2. 応答の解釈を間違えていて、何も拾えていない

    区別がつかないのに「確かめられた」と書くと、
    **確かめていないものを確かめたことにしてしまう。**
    そのまま本番に進めば、残高を読み違えたまま注文を出すことになる。
    """
    spy.fetch_balances = lambda: {}
    assert check_connection(["btc_jpy"], Journal(tmp_path / "j.jsonl")) == 0

    out = capsys.readouterr().out
    assert "資産が1件も返っていません" in out
    assert "入金してから" in out
    assert "**応答の解釈**（資産が空なので突き合わせられない）" in out
    assert "この数字を取引所の画面と突き合わせて" not in out


def test_a_populated_balance_asks_for_reconciliation(spy, tmp_path, capsys):
    """資産があるときは、画面と突き合わせるよう言うこと。"""
    check_connection(["btc_jpy"], Journal(tmp_path / "j.jsonl"))
    out = capsys.readouterr().out
    assert "取引所の画面と突き合わせて" in out
    assert "資産が1件も返っていません" not in out


# ---------------------------------------------------------------------------
# テスト注文 — **本物の金を動かす唯一の経路**
# ---------------------------------------------------------------------------


class _OrderSpy:
    """発注できるが、何を出したか全部覚えている見張り役。"""

    name = "見張り（発注可）"
    unverified = True

    def __init__(self, *, listed=True, cancel_fails=False):
        self.placed: list = []
        self.cancelled: list = []
        self._listed = listed
        self._cancel_fails = cancel_fails
        self.rules = {"minOrderSize": "0.00001", "sizeStep": "0.00001", "tickSize": "1"}

    def fetch_price(self, pair):
        return 10_000_000.0

    def fetch_balances(self):
        return {"jpy": 10_000.0}

    def trading_rules(self, _pair):
        return self.rules

    def conform(self, order):
        return order

    def order_body(self, order):
        return {"symbol": "BTC", "size": str(order.amount)}

    def place_order(self, order):
        self.placed.append(order)
        return {"orderId": "12345"}

    def active_orders(self, _pair):
        if not self._listed:
            return []
        o = self.placed[-1]
        return [{"orderId": "12345", "side": "BUY", "size": str(o.amount),
                 "price": str(o.price), "status": "ORDERED"}]

    def cancel_order(self, order_id):
        if self._cancel_fails:
            raise BrokerError("取引所がエラーを返しました（ERR-5122）")
        self.cancelled.append(order_id)


@pytest.fixture
def order_spy(monkeypatch):
    watcher = _OrderSpy()
    monkeypatch.setitem(EXCHANGES, "gmo", lambda **_kw: watcher)
    monkeypatch.setenv("GMO_API_KEY", "key")
    monkeypatch.setenv("GMO_API_SECRET", "secret")
    return watcher


def test_no_order_is_sent_without_the_explicit_flag(order_spy, tmp_path):
    """**旗を立てない限り、1件も出さないこと。**

    接続確認は「読むだけ」であり続けなければならない。
    発注が既定に紛れ込んだ瞬間、この道具は安全に実行できなくなる。
    """
    check_connection(["btc_jpy"], Journal(tmp_path / "j.jsonl"), "gmo")
    assert order_spy.placed == []


def test_the_test_order_is_placed_far_below_the_market(order_spy, tmp_path):
    """**約定しない位置に置くこと。**

    確かめたいのは配線であって、売買ではない。
    現在値の近くに置くと、確認のつもりが取引になる。
    """
    check_connection(["btc_jpy"], Journal(tmp_path / "j.jsonl"), "gmo", test_order=True)

    assert len(order_spy.placed) == 1, "1件だけ出すこと"
    order = order_spy.placed[0]
    assert order.side == "buy", "現物を持っていないので売りは出せない"
    assert order.price == pytest.approx(10_000_000.0 * 0.95)
    assert order.amount == pytest.approx(0.00001), "最小数量で出すこと"


def test_the_test_order_is_always_cancelled(order_spy, tmp_path, capsys):
    """出したら必ず取り消すこと。**置き去りにしない。**"""
    assert check_connection(
        ["btc_jpy"], Journal(tmp_path / "j.jsonl"), "gmo", test_order=True) == 0
    assert order_spy.cancelled == ["12345"]


def test_a_failed_cancel_is_loud_and_names_the_order(tmp_path, monkeypatch, capsys):
    """**取り消せなかったときが一番危ない。**

    黙って終わると、注文が板に残ったまま忘れられる。
    番号を出して、手で取り消すよう言うこと。
    """
    watcher = _OrderSpy(cancel_fails=True)
    monkeypatch.setitem(EXCHANGES, "gmo", lambda **_kw: watcher)
    monkeypatch.setenv("GMO_API_KEY", "k")
    monkeypatch.setenv("GMO_API_SECRET", "s")

    journal = Journal(tmp_path / "j.jsonl")
    assert check_connection(["btc_jpy"], journal, "gmo", test_order=True) == 1

    err = capsys.readouterr().err
    assert "12345" in err, "注文番号を出すこと"
    assert "手で取り消して" in err
    assert journal.read_all()[-1]["event"] == "test_order_cancel_failed"


def test_an_order_above_the_cap_is_refused(tmp_path, monkeypatch, capsys):
    """最小数量が想定外に大きければ、出さずに止まること。

    取引所が返す値をそのまま信じるので、**別の歯止め**が要る。
    """
    watcher = _OrderSpy()
    watcher.rules = {"minOrderSize": "1", "sizeStep": "1", "tickSize": "1"}
    monkeypatch.setitem(EXCHANGES, "gmo", lambda **_kw: watcher)
    monkeypatch.setenv("GMO_API_KEY", "k")
    monkeypatch.setenv("GMO_API_SECRET", "s")

    assert check_connection(
        ["btc_jpy"], Journal(tmp_path / "j.jsonl"), "gmo", test_order=True) == 1
    assert watcher.placed == [], "上限を超えたのに発注しています"
    assert "上限" in capsys.readouterr().err


def test_no_order_is_sent_when_the_account_is_empty(tmp_path, monkeypatch, capsys):
    """残高が無いなら、発注を試みる前に止まること。

    失敗するに決まっている注文を出しても、確かめたいことは確かめられない。
    """
    watcher = _OrderSpy()
    watcher.fetch_balances = lambda: {}
    monkeypatch.setitem(EXCHANGES, "gmo", lambda **_kw: watcher)
    monkeypatch.setenv("GMO_API_KEY", "k")
    monkeypatch.setenv("GMO_API_SECRET", "s")

    assert check_connection(
        ["btc_jpy"], Journal(tmp_path / "j.jsonl"), "gmo", test_order=True) == 1
    assert watcher.placed == []
    assert "残高がありません" in capsys.readouterr().err


def test_an_order_missing_from_the_book_is_not_called_verified(tmp_path, monkeypatch, capsys):
    """板で見つからなかったら、「確かめられた」と言わないこと。

    発注の応答が返ったことと、板に並んでいることは**別の事実**になる。
    """
    watcher = _OrderSpy(listed=False)
    monkeypatch.setitem(EXCHANGES, "gmo", lambda **_kw: watcher)
    monkeypatch.setenv("GMO_API_KEY", "k")
    monkeypatch.setenv("GMO_API_SECRET", "s")

    check_connection(["btc_jpy"], Journal(tmp_path / "j.jsonl"), "gmo", test_order=True)

    out = capsys.readouterr().out
    assert "板で確かめられませんでした" in out
    assert "すべて通りました" not in out
    assert watcher.cancelled == ["12345"], "確かめられなくても取り消すこと"


def test_the_shown_amount_is_the_exchange_minimum(spy, tmp_path, capsys):
    """表示する数量が、最小数量であること。

    確認のために必要以上の額を動かす理由はない。
    """
    check_connection(["btc_jpy"], Journal(tmp_path / "j.jsonl"))
    out = capsys.readouterr().out
    assert f"{MIN_ORDER_AMOUNT['btc_jpy']:.8f}" in out
