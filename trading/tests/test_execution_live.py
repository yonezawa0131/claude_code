"""執行基盤の検証。

## 何を守らせるか

自動で休みなく動くものは、間違っていても休みなく間違い続ける。
この基盤が実データで測った5戦略は、元本30万円で平均11.5万円を失う成績だった。
**自動化していれば、その損失は取りこぼしなく実現していた。**

だから執行基盤の第一の仕事は、発注することではなく**発注を止めること**になる。

ここで確かめるのは4つ。
  1. 記憶に頼らず、毎回取引所から現在地を読むこと
  2. 二重発注が構造的に起きないこと
  3. 検証を通っていない戦略が本番で動かないこと
  4. 上限を超える注文が通らないこと
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.execution.broker import BrokerError, Order, PaperBroker  # noqa: E402
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

PRICES = {"btc_jpy": 10_000_000.0, "eth_jpy": 500_000.0}
TODAY = dt.date(2026, 8, 3)


@pytest.fixture
def broker(tmp_path) -> PaperBroker:
    b = PaperBroker(state_path=tmp_path / "state.json")
    b.set_prices(PRICES)
    b.deposit("jpy", 1_000_000.0)
    return b


def _ok_validation(strategy: str = "s", days_ago: int = 1) -> ValidationRecord:
    return ValidationRecord(
        strategy=strategy, passed=True,
        date=TODAY - dt.timedelta(days=days_ago), script="test",
    )


def _context(orders: list[Order], **kw) -> GuardContext:
    base = dict(
        strategy="s", orders=orders, prices=PRICES,
        equity=1_000_000.0, initial_equity=1_000_000.0, exposure=0.0,
        limits=Limits(), validation=_ok_validation(), today=TODAY,
    )
    base.update(kw)
    return GuardContext(**base)


# ---------------------------------------------------------------------------
# 1. 記憶に頼らない
# ---------------------------------------------------------------------------


def test_state_comes_from_the_broker_not_from_memory(broker, tmp_path):
    """**外で保有が変わっても、次の実行は正しい現在地から始まること。**

    「昨日どう建てたか」を覚えておく設計は、手で1回売買しただけで壊れる。
    毎回読み直すなら壊れない。
    """
    target = TargetPortfolio(weights={"btc_jpy": 1.0})
    orders, _ = build_orders(target, broker.fetch_balances(), PRICES, limit_offset=None)
    for o in orders:
        broker.place_order(o)

    # 別の誰か（手動、別プロセス、別マシン）が半分売った
    outside = PaperBroker(state_path=tmp_path / "state.json")
    outside.set_prices(PRICES)
    held = outside.fetch_balances()["btc"]
    outside.place_order(Order("btc_jpy", "sell", held / 2, None))

    # 何も伝えていないのに、次の差分は正しく「買い戻し」になる
    again, _ = build_orders(target, broker.fetch_balances(), PRICES)
    assert len(again) == 1
    assert again[0].side == "buy"
    assert again[0].amount == pytest.approx(held / 2, rel=0.02)


def test_current_weights_ignore_assets_without_a_price():
    """価格の取れない資産を総資産に数えないこと。

    分からないものを勝手に評価すると、比率の計算全体が狂う。
    """
    balances = {"jpy": 500_000.0, "btc": 0.05, "zzz": 1_000.0}
    weights, equity = current_weights(balances, {"btc_jpy": 10_000_000.0})
    assert equity == pytest.approx(1_000_000.0)
    assert "zzz_jpy" not in weights


# ---------------------------------------------------------------------------
# 2. 二重発注が起きない
# ---------------------------------------------------------------------------


def test_running_twice_does_not_trade_twice(broker):
    """**同じ処理を2回走らせても、2回目は何も出さないこと。**

    差分だけを出す設計なので、目標に到達していれば差分はゼロになる。
    「前回何を出したか」を覚える設計だと、記憶がずれた瞬間に二重発注する。
    """
    target = TargetPortfolio(weights={"btc_jpy": 1.0})

    first, _ = build_orders(target, broker.fetch_balances(), PRICES, limit_offset=None)
    assert first, "1回目は注文が出るはず"
    for o in first:
        broker.place_order(o)

    second, _ = build_orders(target, broker.fetch_balances(), PRICES, limit_offset=None)
    assert second == [], f"2回目に {len(second)} 件出ています"


def test_small_differences_are_not_traded(broker):
    """わずかなずれを追いかけないこと。動くこと自体にコストがかかる。"""
    target = TargetPortfolio(weights={"btc_jpy": 1.0})
    for o in build_orders(target, broker.fetch_balances(), PRICES, limit_offset=None)[0]:
        broker.place_order(o)

    nudged = TargetPortfolio(weights={"btc_jpy": 0.999})
    orders, _ = build_orders(nudged, broker.fetch_balances(), PRICES, min_trade_jpy=2_000)
    assert orders == []


def test_sells_are_ordered_before_buys():
    """先に売って現金を作ること。順番が逆だと現金不足で買えない。"""
    balances = {"jpy": 0.0, "btc": 0.1}
    target = TargetPortfolio(weights={"eth_jpy": 1.0})
    orders, _ = build_orders(target, balances, PRICES)
    assert [o.side for o in orders] == ["sell", "buy"]


def test_leverage_targets_are_rejected():
    with pytest.raises(ValueError, match="レバレッジ"):
        TargetPortfolio(weights={"btc_jpy": 0.7, "eth_jpy": 0.7})


def test_short_targets_are_rejected():
    with pytest.raises(ValueError, match="売り建て"):
        TargetPortfolio(weights={"btc_jpy": -0.5})


def test_limit_orders_are_the_default():
    """既定が指値であること。

    この基盤の測定では、やり直せる戦略なら指値で往復コストがほぼ0になる。
    """
    orders, _ = build_orders(
        TargetPortfolio(weights={"btc_jpy": 1.0}), {"jpy": 1_000_000.0}, PRICES
    )
    assert orders[0].price is not None
    assert orders[0].price < PRICES["btc_jpy"], "買い指値は現在値より下に置くこと"


# ---------------------------------------------------------------------------
# 3. 検証を通っていないものは本番で動かない
# ---------------------------------------------------------------------------


ONE = [Order("btc_jpy", "buy", 0.001, 10_000_000.0)]


def test_live_is_refused_without_a_validation_record():
    v = check(_context(ONE, validation=None))
    assert any("未検証" in x.rule for x in v)
    assert "本番では実行しません" in describe(v)


def test_live_is_refused_when_validation_failed():
    """**不合格の戦略を自動化させないこと。**

    ここが通ってしまうと、優位性のない戦略が休みなく損失を実現する。
    """
    failed = ValidationRecord(strategy="s", passed=False, date=TODAY, script="test")
    v = check(_context(ONE, validation=failed))
    assert any("不合格" in x.rule for x in v)


def test_live_is_refused_when_validation_is_stale():
    old = _ok_validation(days_ago=200)
    v = check(_context(ONE, validation=old))
    assert any("古い" in x.rule for x in v)


def test_live_is_refused_when_the_record_is_for_another_strategy():
    v = check(_context(ONE, validation=_ok_validation(strategy="別の戦略")))
    assert any("不一致" in x.rule for x in v)


def test_a_valid_record_passes():
    assert check(_context(ONE)) == []


def test_validation_record_round_trips(tmp_path):
    path = tmp_path / "v.json"
    record = _ok_validation()
    record.save(path)
    assert ValidationRecord.load(path) == record
    assert json.loads(path.read_text())["passed"] is True


# ---------------------------------------------------------------------------
# 4. 上限
# ---------------------------------------------------------------------------


def test_an_oversized_order_is_blocked():
    big = [Order("btc_jpy", "buy", 0.01, 10_000_000.0)]  # 10万円
    v = check(_context(big, limits=Limits(max_notional_per_order=20_000)))
    assert any("1注文の上限" in x.rule for x in v)


def test_too_many_orders_are_blocked():
    many = [Order("btc_jpy", "buy", 0.00001, 10_000_000.0) for _ in range(30)]
    v = check(_context(many, limits=Limits(max_orders_per_run=20)))
    assert any("注文数" in x.rule for x in v)


def test_drawdown_stops_everything():
    """開始時から決めた率まで減ったら止めること。"""
    v = check(_context(ONE, equity=700_000.0, initial_equity=1_000_000.0))
    assert any("損失の上限" in x.rule for x in v)


def test_exposure_cap_counts_existing_holdings():
    v = check(_context(ONE, exposure=99_000.0, limits=Limits(max_total_exposure=100_000)))
    assert any("建玉の上限" in x.rule for x in v)


def test_missing_price_blocks_the_order():
    v = check(_context([Order("zzz_jpy", "buy", 1.0, 100.0)]))
    assert any("価格不明" in x.rule for x in v)


def test_limits_reject_an_incoherent_configuration():
    with pytest.raises(ValueError):
        Limits(max_notional_per_run=10_000, max_notional_per_order=50_000)


# ---------------------------------------------------------------------------
# 記録
# ---------------------------------------------------------------------------


def test_journal_is_append_only(tmp_path):
    path = tmp_path / "j.jsonl"
    Journal(path, run_id="a").write("state", equity=100.0)
    Journal(path, run_id="b").write("state", equity=200.0)

    records = Journal(path).read_all()
    assert [r["run_id"] for r in records] == ["a", "b"]
    assert [r["equity"] for r in records] == [100.0, 200.0]


def test_journal_records_the_inputs_behind_a_decision(tmp_path):
    """結果だけでなく、判断に使った入力も残すこと。

    あとから同じ入力で再計算して、確かめられる必要がある。
    """
    journal = Journal(tmp_path / "j.jsonl")
    journal.write("guards", strategy="s", violations=[], orders=[{"pair": "btc_jpy"}])
    record = journal.read_all()[0]
    assert record["orders"][0]["pair"] == "btc_jpy"
    assert "time" in record and "run_id" in record


# ---------------------------------------------------------------------------
# ペーパーの整合
# ---------------------------------------------------------------------------


def test_paper_broker_cannot_spend_money_it_does_not_have(broker):
    with pytest.raises(BrokerError, match="足りません"):
        broker.place_order(Order("btc_jpy", "buy", 1.0, None))


def test_paper_broker_cannot_sell_what_it_does_not_hold(broker):
    with pytest.raises(BrokerError, match="足りません"):
        broker.place_order(Order("btc_jpy", "sell", 1.0, None))


def test_paper_round_trip_costs_only_the_fee(broker):
    """成行の往復で、減るのは手数料ぶんだけであること。"""
    before = broker.fetch_balances()["jpy"]
    broker.place_order(Order("btc_jpy", "buy", 0.01, None))
    broker.place_order(Order("btc_jpy", "sell", 0.01, None))
    after = broker.fetch_balances()["jpy"]
    expected_fee = 0.01 * 10_000_000.0 * broker.fee_taker * 2
    assert before - after == pytest.approx(expected_fee, rel=1e-6)


def test_exposure_excludes_cash():
    assert exposure_jpy({"jpy": 500_000.0, "btc": 0.05}, PRICES) == pytest.approx(500_000.0)


# ---------------------------------------------------------------------------
# 指値は、その値段に来るまで約定しない
# ---------------------------------------------------------------------------


def test_a_limit_order_does_not_fill_on_placement(broker):
    """**最初の実装が作っていたバグの再発防止。**

    現在値より下に買い指値を置いた瞬間に約定させると、
    その差額が利益として計上される。30万円の口座が1回の売買で
    300,150円になり、**0.05%が何もないところから生まれていた**。

    バックテスト側で同じ誤りを見つけて直したのに、執行側で再現させた。
    """
    before = broker.fetch_balances()["jpy"]
    limit = PRICES["btc_jpy"] * 0.9995

    response = broker.place_order(Order("btc_jpy", "buy", 0.01, limit))
    assert response["status"] == "resting", "出した瞬間に約定しています"
    assert broker.fetch_balances().get("btc", 0.0) == 0.0

    # 資金は予約されるだけ。増えも減りもしない
    reserved = 0.01 * limit
    assert broker.fetch_balances()["jpy"] == pytest.approx(before - reserved)


def test_equity_does_not_change_from_merely_placing_an_order(broker):
    """注文を出しただけで総資産が動かないこと。

    ここが動くなら、どこかで値段を作っている。
    """
    _, before = current_weights(broker.fetch_balances(), PRICES)
    limit = PRICES["btc_jpy"] * 0.9995
    broker.place_order(Order("btc_jpy", "buy", 0.01, limit))

    balances = broker.fetch_balances()
    reserved = sum(o["amount"] * o["price"] for o in broker.open_orders())
    _, after = current_weights(balances, PRICES)
    assert after + reserved == pytest.approx(before)


def test_a_limit_order_fills_only_when_the_price_arrives(broker):
    limit = PRICES["btc_jpy"] * 0.99
    broker.place_order(Order("btc_jpy", "buy", 0.01, limit))

    # まだ届いていない
    assert broker.settle({"btc_jpy": PRICES["btc_jpy"]}) == []
    assert len(broker.open_orders()) == 1

    # 届いた
    fills = broker.settle({"btc_jpy": limit - 1})
    assert len(fills) == 1
    assert broker.open_orders() == []
    assert broker.fetch_balances()["btc"] == pytest.approx(0.01)


def test_a_sell_limit_fills_only_when_the_price_rises_to_it(broker):
    broker.place_order(Order("btc_jpy", "buy", 0.01, None))
    limit = PRICES["btc_jpy"] * 1.01
    broker.place_order(Order("btc_jpy", "sell", 0.01, limit))

    assert broker.settle({"btc_jpy": PRICES["btc_jpy"]}) == []
    assert len(broker.settle({"btc_jpy": limit + 1})) == 1


def test_cancelling_returns_the_reserved_funds(broker):
    before = broker.fetch_balances()["jpy"]
    broker.place_order(Order("btc_jpy", "buy", 0.01, PRICES["btc_jpy"] * 0.99))
    assert broker.fetch_balances()["jpy"] < before

    assert broker.cancel_all() == 1
    assert broker.fetch_balances()["jpy"] == pytest.approx(before)
    assert broker.open_orders() == []


def test_reserved_funds_cannot_be_spent_twice(broker):
    """板に置いた注文の資金を、別の注文に使えないこと。"""
    limit = PRICES["btc_jpy"] * 0.99
    broker.place_order(Order("btc_jpy", "buy", 0.1, limit))  # 約99万円を予約
    with pytest.raises(BrokerError, match="足りません"):
        broker.place_order(Order("btc_jpy", "buy", 0.1, limit))


def test_a_maker_fill_earns_the_rebate(broker):
    """メイカーの受け取りが反映されること。ゼロにすると成績が良く出る。"""
    limit = PRICES["btc_jpy"] * 0.99
    broker.place_order(Order("btc_jpy", "buy", 0.01, limit))
    before = broker.fetch_balances()["jpy"]
    broker.settle({"btc_jpy": limit})
    after = broker.fetch_balances()["jpy"]
    # 手数料が負（受け取り）なので現金は増える
    assert after - before == pytest.approx(-0.01 * limit * broker.fee_maker)


def test_a_full_allocation_leaves_room_for_the_fee(broker):
    """比率100%の指示で、手数料を払う現金が残ること。

    資金を全部使って買おうとすると、手数料ぶんが足りず取引所に拒否される。
    最初の実装はこれで失敗した。「100%投じる」は「手数料込みで100%」になる。
    """
    orders, _ = build_orders(
        TargetPortfolio(weights={"btc_jpy": 1.0}),
        broker.fetch_balances(), PRICES, limit_offset=None,
    )
    # 拒否されずに通ること
    for o in orders:
        broker.place_order(o)
    assert broker.fetch_balances()["jpy"] >= 0.0


def test_a_rebate_needs_no_buffer():
    """受け取り（負の手数料）のときは余裕を取らないこと。"""
    full, _ = build_orders(
        TargetPortfolio(weights={"btc_jpy": 1.0}), {"jpy": 1_000_000.0}, PRICES,
        limit_offset=None, buy_fee=-0.0002,
    )
    assert full[0].amount == pytest.approx(1_000_000.0 / PRICES["btc_jpy"])
