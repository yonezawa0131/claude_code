"""エンジン自身の正しさを検査するテスト。

戦略が儲かるかではなく、**エンジンが嘘をつかないか**を確かめる。
ここが通らないうちは、どんなバックテスト結果にも意味がない。

実行:
    .venv-trading/bin/python -m pytest trading/tests -q
または pytest がない場合:
    .venv-trading/bin/python trading/tests/test_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.backtest import BacktestConfig, Side, run_backtest  # noqa: E402
from trading.src.costs import (  # noqa: E402
    DEALER_DESK,
    GMO_EXCHANGE,
    ZERO_COST,
    OrderType,
    breakeven_move,
    required_daily_return,
)
from trading.src import indicators as ind  # noqa: E402
from trading.src.metrics import evaluate, max_drawdown  # noqa: E402
from trading.src.strategy import BuyAndHold, EmaCrossATR, RandomEntry, RsiMeanReversion  # noqa: E402
from trading.src.validate import check_causality  # noqa: E402


def make_frame(closes: list[float], spread: float = 0.0) -> pd.DataFrame:
    """終値の列から、整合したOHLCVを作るテスト用ヘルパー。"""
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="1h", tz="UTC")
    close = np.array(closes, dtype=float)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(len(close)),
        },
        index=idx,
    )


# --- 1. 執行タイミング（先読みしていないこと） ------------------------------


def test_signal_executes_on_next_bar_open() -> None:
    """バー t のシグナルは、バー t+1 の始値で約定すること。

    同じバーの終値で約定していたら、未来を知って取引したことになる。
    """
    closes = [100.0] * 5 + [200.0] * 5
    df = make_frame(closes)

    class BuyAtIndex3:
        name = "3本目で買う"

        def warmup(self) -> int:
            return 1

        def generate(self, d: pd.DataFrame) -> pd.DataFrame:
            direction = np.zeros(len(d))
            direction[3:] = 1.0
            return pd.DataFrame(
                {
                    "direction": direction,
                    "stop_loss": np.full(len(d), np.nan),
                    "take_profit": np.full(len(d), np.nan),
                },
                index=d.index,
            )

    result = run_backtest(df, BuyAtIndex3(), ZERO_COST, BacktestConfig(initial_capital=10_000))
    assert len(result.trades) == 1
    trade = result.trades[0]
    # index 3 のシグナル → index 4 の始値で約定。index 4 の始値は index 3 の終値 = 100
    assert trade.entry_time == df.index[4]
    assert trade.entry_price == 100.0, f"約定価格が {trade.entry_price}（100であるべき）"


def test_no_lookahead_in_shipped_strategies() -> None:
    """同梱の戦略がすべて因果的であること。"""
    rng = np.random.default_rng(7)
    closes = 10_000_000 * np.exp(np.cumsum(rng.normal(0, 0.005, 400)))
    df = make_frame(list(closes), spread=0.002)

    for strategy in (
        BuyAndHold(),
        EmaCrossATR(),
        EmaCrossATR(allow_short=True),
        RsiMeanReversion(),
        RandomEntry(seed=1),
    ):
        violations = check_causality(strategy, df, cuts=4)
        assert not violations, f"{strategy.name} が先読みしています: {violations[0]}"


def test_causality_checker_catches_a_peeking_strategy() -> None:
    """検査器そのものが機能すること。

    わざと未来を見る戦略を作って、ちゃんと捕まえられるか確かめる。
    検査器が壊れていたら、他のテストがすべて無意味になる。
    """
    df = make_frame([100.0 + i for i in range(100)], spread=0.001)

    class Cheater:
        name = "未来を見る戦略"

        def warmup(self) -> int:
            return 2

        def generate(self, d: pd.DataFrame) -> pd.DataFrame:
            # 翌バーの終値を見て、上がるなら買う。実運用では不可能
            future = d["close"].shift(-1)
            direction = (future > d["close"]).astype(float)
            return pd.DataFrame(
                {
                    "direction": direction,
                    "stop_loss": np.full(len(d), np.nan),
                    "take_profit": np.full(len(d), np.nan),
                },
                index=d.index,
            )

    violations = check_causality(Cheater(), df, cuts=4)
    assert violations, "未来を見る戦略を検出できませんでした"


# --- 2. コスト -------------------------------------------------------------


def test_costs_reduce_returns() -> None:
    """同じ戦略・同じデータなら、コストが高いほど成績が悪くなること。"""
    rng = np.random.default_rng(3)
    closes = 10_000_000 * np.exp(np.cumsum(rng.normal(0.0002, 0.004, 600)))
    df = make_frame(list(closes), spread=0.002)
    strategy = EmaCrossATR()
    config = BacktestConfig(initial_capital=500_000)

    zero = evaluate(run_backtest(df, strategy, ZERO_COST, config)).total_return
    gmo = evaluate(run_backtest(df, strategy, GMO_EXCHANGE, config)).total_return
    dealer = evaluate(run_backtest(df, strategy, DEALER_DESK, config)).total_return

    assert zero > gmo > dealer, (
        f"コストが成績に反映されていません: zero={zero:.4f} gmo={gmo:.4f} dealer={dealer:.4f}"
    )


def test_dealer_desk_is_ruinous() -> None:
    """販売所形式で回転させると壊滅すること。

    片道4.5%・往復9%は、デイトレードでは取り返せない。
    この数字が実感として出ることを確認しておく。
    """
    assert breakeven_move(DEALER_DESK, OrderType.TAKER) > 0.08
    assert breakeven_move(GMO_EXCHANGE, OrderType.TAKER) < 0.005


def test_maker_can_be_cheaper_than_taker() -> None:
    """Maker（指値）は Taker（成行）より安いこと。GMOはリベートで負になる。"""
    assert GMO_EXCHANGE.cost_rate(OrderType.MAKER) < GMO_EXCHANGE.cost_rate(OrderType.TAKER)


# --- 3. 損切りと利確 -------------------------------------------------------


def test_stop_loss_triggers_within_bar() -> None:
    """バーの安値が損切り水準に触れたら、そのバーで決済されること。"""
    idx = pd.date_range("2026-01-01", periods=6, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0, 101.0, 101.0, 101.0],
            # index 4 だけ大きく下ヒゲを出す
            "low": [99.0, 99.0, 99.0, 99.0, 80.0, 99.0],
            "close": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "volume": [1.0] * 6,
        },
        index=idx,
    )

    class LongWithStop:
        name = "損切り付きロング"

        def warmup(self) -> int:
            return 1

        def generate(self, d: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "direction": np.ones(len(d)),
                    "stop_loss": np.full(len(d), 90.0),
                    "take_profit": np.full(len(d), np.nan),
                },
                index=d.index,
            )

    result = run_backtest(df, LongWithStop(), ZERO_COST, BacktestConfig(initial_capital=10_000))
    stopped = [t for t in result.trades if t.reason == "stop_loss"]
    assert stopped, "損切りが発動していません"
    assert stopped[0].exit_price == 90.0
    assert stopped[0].exit_time == idx[4]


def test_stop_wins_over_target_in_same_bar() -> None:
    """同じバーで損切りと利確の両方に触れたら、損切りが優先されること。

    1本のバーの中でどちらが先に起きたかはデータから分からない。
    分からないものは不利な側に倒す。
    """
    idx = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0] * 4,
            "high": [101.0, 101.0, 130.0, 101.0],  # index 2 で利確水準に届く
            "low": [99.0, 99.0, 70.0, 99.0],       # 同じバーで損切り水準にも届く
            "close": [100.0] * 4,
            "volume": [1.0] * 4,
        },
        index=idx,
    )

    class Bracketed:
        name = "損切り・利確つき"

        def warmup(self) -> int:
            return 1

        def generate(self, d: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "direction": np.ones(len(d)),
                    "stop_loss": np.full(len(d), 80.0),
                    "take_profit": np.full(len(d), 120.0),
                },
                index=d.index,
            )

    result = run_backtest(df, Bracketed(), ZERO_COST, BacktestConfig(initial_capital=10_000))
    assert result.trades[0].reason == "stop_loss", "利確が優先されています（保守側でない）"


def test_trailing_stop_only_moves_favourably() -> None:
    """トレーリングストップが不利な方向に動かないこと。

    損切りを遠ざける操作は「損切りをずらす」ことであり、
    これを許すと損失が青天井になる。
    """
    closes = [100.0, 110.0, 120.0, 130.0, 125.0, 120.0, 115.0, 110.0]
    df = make_frame(closes, spread=0.0)

    class WobblyStop:
        name = "揺れる損切り"

        def warmup(self) -> int:
            return 1

        def generate(self, d: pd.DataFrame) -> pd.DataFrame:
            # 一度上げたあと、わざと下げた損切り水準を出す
            stops = np.array([90.0, 100.0, 110.0, 115.0, 60.0, 60.0, 60.0, 60.0])
            return pd.DataFrame(
                {
                    "direction": np.ones(len(d)),
                    "stop_loss": stops[: len(d)],
                    "take_profit": np.full(len(d), np.nan),
                },
                index=d.index,
            )

    result = run_backtest(df, WobblyStop(), ZERO_COST, BacktestConfig(initial_capital=10_000))
    stopped = [t for t in result.trades if t.reason == "stop_loss"]
    assert stopped, "損切りが発動していません"
    # 115 まで引き上げた損切りが、その後 60 に下げられていないこと
    assert stopped[0].exit_price >= 115.0, (
        f"損切りが不利側に動きました（決済 {stopped[0].exit_price}）"
    )


# --- 4. 対照群（エンジンが幻の利益を作っていないこと） ----------------------


def test_random_strategy_loses_after_costs_on_random_walk() -> None:
    """ドリフトのないランダムウォークで、ランダム戦略はコスト分だけ負けること。

    **ここが黒字になったらエンジンのバグ。**
    優位性のない戦略が、優位性のないデータから利益を出すことはありえない。
    """
    results = []
    for seed in range(8):
        rng = np.random.default_rng(seed)
        closes = 10_000_000 * np.exp(np.cumsum(rng.normal(0.0, 0.004, 1500)))
        df = make_frame(list(closes), spread=0.002)
        rep = evaluate(
            run_backtest(
                df,
                RandomEntry(seed=seed, flip_probability=0.08),
                GMO_EXCHANGE,
                BacktestConfig(initial_capital=500_000),
            )
        )
        results.append(rep.total_return)

    mean_return = float(np.mean(results))
    assert mean_return < 0, (
        f"ランダム戦略の平均リターンが {mean_return:.4f} で正になっています。"
        "エンジンが実在しない利益を作っている可能性があります"
    )


def test_buy_and_hold_matches_price_change() -> None:
    """買い持ちの成績が、コストゼロなら価格変化とほぼ一致すること。"""
    closes = [100.0, 110.0, 120.0, 150.0, 200.0]
    df = make_frame(closes)
    rep = evaluate(
        run_backtest(df, BuyAndHold(), ZERO_COST, BacktestConfig(initial_capital=100_000))
    )
    # index1 の始値(=100)で買い、最終終値 200 で手仕舞う → 2倍
    assert abs(rep.total_return - 1.0) < 0.02, f"総リターン {rep.total_return}"


# --- 5. 指標 ---------------------------------------------------------------


def test_rsi_bounds_and_extremes() -> None:
    """RSIが0〜100に収まり、単調上昇では100に近づくこと。"""
    up = pd.Series([100.0 + i for i in range(60)])
    r = ind.rsi(up, 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()
    assert r.iloc[-1] > 99, f"単調上昇でRSIが {r.iloc[-1]}"

    down = pd.Series([100.0 - i for i in range(60)])
    r2 = ind.rsi(down, 14).dropna()
    assert r2.iloc[-1] < 1, f"単調下落でRSIが {r2.iloc[-1]}"


def test_atr_is_positive_and_tracks_volatility() -> None:
    """ATRが正で、値動きが荒くなると増えること。"""
    calm = make_frame([100.0 + 0.1 * (i % 3) for i in range(80)], spread=0.0005)
    wild = make_frame([100.0 + 5.0 * (i % 3) for i in range(80)], spread=0.01)
    a_calm = ind.atr(calm["high"], calm["low"], calm["close"], 14).dropna()
    a_wild = ind.atr(wild["high"], wild["low"], wild["close"], 14).dropna()
    assert (a_calm > 0).all() and (a_wild > 0).all()
    assert a_wild.mean() > a_calm.mean()


def test_ema_is_causal_by_construction() -> None:
    """EMAが打ち切りに対して安定であること（adjust=False の確認）。"""
    s = pd.Series([100.0 + i * 0.5 for i in range(100)])
    full = ind.ema(s, 20)
    part = ind.ema(s.iloc[:60], 20)
    assert np.allclose(full.iloc[:60].dropna(), part.dropna())


# --- 6. 評価指標 -----------------------------------------------------------


def test_max_drawdown() -> None:
    eq = pd.Series([100.0, 120.0, 60.0, 80.0], index=pd.date_range("2026-01-01", periods=4))
    assert abs(max_drawdown(eq) - (-0.5)) < 1e-9


def test_required_daily_return_translation() -> None:
    """1日あたりの目標金額が、元本によって難易度が変わること。"""
    assert abs(required_daily_return(500, 100_000) - 0.005) < 1e-12
    assert abs(required_daily_return(500, 1_000_000) - 0.0005) < 1e-12


def test_leverage_cap_enforced() -> None:
    """国内規制の2倍を超えるレバレッジを設定できないこと。"""
    try:
        BacktestConfig(leverage=3.0)
    except ValueError as exc:
        assert "2倍" in str(exc)
    else:
        raise AssertionError("レバレッジ3倍が通ってしまいました")


def test_short_disabled_by_default() -> None:
    """既定ではショートが無効で、指示されても建てないこと。"""
    closes = [100.0 - i for i in range(60)]
    df = make_frame(closes, spread=0.001)
    result = run_backtest(
        df, EmaCrossATR(allow_short=True), ZERO_COST, BacktestConfig(initial_capital=100_000)
    )
    assert all(t.side is not Side.SHORT for t in result.trades)
    assert any("allow_short=False" in w for w in result.warnings)


if __name__ == "__main__":
    failures = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {name}\n        {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {name}\n        {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures} / {len(tests)} 通過")
    raise SystemExit(1 if failures else 0)


# --- 7. 資金管理 -----------------------------------------------------------


def test_breakeven_win_rate_arithmetic() -> None:
    """損益比と必要勝率の関係。勝率30%なら損益比2.33以上が必要。"""
    from trading.src.metrics import breakeven_win_rate, required_reward_risk

    assert abs(breakeven_win_rate(1.0) - 0.5) < 1e-12
    assert abs(breakeven_win_rate(2.0) - 1 / 3) < 1e-12
    assert abs(breakeven_win_rate(3.0) - 0.25) < 1e-12
    assert abs(required_reward_risk(0.3) - 7 / 3) < 1e-9


def test_recovery_return_asymmetry() -> None:
    """-50%からの回復には+100%が必要。"""
    from trading.src.metrics import recovery_return

    assert abs(recovery_return(0.5) - 1.0) < 1e-12
    assert abs(recovery_return(0.2) - 0.25) < 1e-12
    assert recovery_return(0.9) > 8.9


def test_risk_based_sizing_limits_loss() -> None:
    """risk_per_trade を設定すると、1回の損切りでの損失がその率に収まること。"""
    from trading.src.metrics import evaluate

    idx = pd.date_range("2026-01-01", periods=8, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0] * 8,
            "high": [101.0] * 8,
            "low": [99.0, 99.0, 99.0, 90.0, 99.0, 99.0, 99.0, 99.0],
            "close": [100.0] * 8,
            "volume": [1.0] * 8,
        },
        index=idx,
    )

    class LongWithStop:
        name = "損切り付き"

        def warmup(self) -> int:
            return 1

        def generate(self, d: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "direction": np.ones(len(d)),
                    "stop_loss": np.full(len(d), 95.0),  # 5%下
                    "take_profit": np.full(len(d), np.nan),
                },
                index=d.index,
            )

    capital = 1_000_000.0
    result = run_backtest(
        df, LongWithStop(), ZERO_COST,
        BacktestConfig(initial_capital=capital, risk_per_trade=0.01),
    )
    stopped = [t for t in result.trades if t.reason == "stop_loss"]
    assert stopped, "損切りが発動していません"
    loss = abs(stopped[0].pnl)
    # 資金の1%（1万円）程度に収まっているはず。多少の誤差は許容
    assert loss <= capital * 0.012, f"損失が {loss:,.0f} 円で、想定の1%を超えています"
    assert loss >= capital * 0.008, f"損失が {loss:,.0f} 円で、想定より小さすぎます"


def test_risk_per_trade_rejects_reckless_values() -> None:
    """1トレードで資金の50%超を危険に晒す設定を拒否すること。"""
    try:
        BacktestConfig(risk_per_trade=0.8)
    except ValueError as exc:
        assert "50%" in str(exc)
    else:
        raise AssertionError("危険な risk_per_trade が通ってしまいました")


def test_kelly_is_zero_for_losing_strategy() -> None:
    """負けている戦略のケリー値が0以下になること。"""
    from trading.src.metrics import kelly_fraction
    from trading.src.backtest import Trade, Side

    t = pd.Timestamp("2026-01-01", tz="UTC")
    trades = [
        Trade(t, t, Side.LONG, 100, 99, 1, 0, -100.0, "stop_loss") for _ in range(7)
    ] + [Trade(t, t, Side.LONG, 100, 101, 1, 0, 100.0, "take_profit") for _ in range(3)]
    assert kelly_fraction(trades) < 0
