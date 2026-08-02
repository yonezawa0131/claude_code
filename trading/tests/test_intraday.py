"""日中モメンタム戦略の検証。

この検出器は「何も見つけない」という答えを返しうる。
そのとき、パターンが無かったのか、コードが壊れていたのかを
区別できなければ、結果に意味がない。

だから**陽性対照**を先に置く。
既知のパターンを埋め込んだデータで検出できることを確かめてから、
未知のデータに向ける。

陰性対照（パターンなし）だけでは足りない。
direction を常に0にするだけの空実装が、陰性対照を必ず通ってしまうからである。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts.make_synthetic import make_synthetic_ohlcv  # noqa: E402
from trading.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from trading.src.costs import GMO_EXCHANGE, ZERO_COST, OrderType  # noqa: E402
from trading.src.metrics import evaluate  # noqa: E402
from trading.src.strategy import IntradayMomentum  # noqa: E402
from trading.src.validate import check_causality  # noqa: E402

SEED = 7
BARS = 5000
SESSION_BARS = 24

CONFIG = BacktestConfig(
    initial_capital=500_000.0,
    position_fraction=1.0,
    order_type=OrderType.TAKER,
)


def _frame(beta: float, seed: int = SEED, bars: int = BARS) -> pd.DataFrame:
    """intradayレジームの合成データを DatetimeIndex 付きで返す。

    beta が埋め込むパターンの強さ。**0にすると純粋なランダムウォークになる。**
    陽性と陰性で同じ seed を使うので、両者の差はパターンの有無だけになる。
    """
    df = make_synthetic_ohlcv(bars, seed, "intraday", session_bars=SESSION_BARS, beta=beta)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    return df.set_index("timestamp")


def _flat_frame_with_session_open_jump(sessions: int = 4) -> pd.DataFrame:
    """セッション初バーだけ +1% 動き、あとは完全に横ばいのデータ。

    値動きが1本に限定されているので、戦略がどのバーを持ったかを
    位置だけで確認できる。
    """
    bars = sessions * SESSION_BARS
    closes = np.empty(bars)
    price = 100.0
    for i in range(bars):
        if i % SESSION_BARS == 0:
            price *= 1.01
        closes[i] = price

    opens = np.empty(bars)
    opens[0] = 100.0
    opens[1:] = closes[:-1]

    index = pd.date_range("2020-01-01", periods=bars, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, closes),
            "low": np.minimum(opens, closes),
            "close": closes,
            "volume": np.ones(bars),
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# 陽性対照：あるパターンを検出できること
# ---------------------------------------------------------------------------


def test_detects_the_pattern_that_was_deliberately_embedded():
    """埋め込んだ日中モメンタムを、コスト控除後でも検出できる。

    これが通らない限り、実データで「何も無かった」という結果は信用できない。
    """
    result = run_backtest(_frame(beta=1.0), IntradayMomentum(stop_atr=None), GMO_EXCHANGE, CONFIG)
    report = evaluate(result)

    assert report.total_return > 0.20, (
        f"埋め込んだパターンを検出できていません（{report.total_return * 100:.2f}%）"
    )
    assert report.excess_over_buy_hold > 0
    assert report.win_rate > 0.55


def test_detection_survives_the_atr_stop():
    """既定の損切りを入れても検出できる。

    損切りは利益を削るが、消してはいけない。
    消えるなら、その損切り幅はこの時間軸に対して狭すぎる。
    """
    report = evaluate(
        run_backtest(_frame(beta=1.0), IntradayMomentum(stop_atr=2.0), GMO_EXCHANGE, CONFIG)
    )
    assert report.total_return > 0.20


def test_stronger_pattern_gives_a_larger_result():
    """パターンを強くすれば結果も伸びる。

    埋め込んだ量と検出した量が連動しないなら、
    検出しているのはパターンではなく別の何かである。
    """
    returns = [
        evaluate(
            run_backtest(_frame(beta=b), IntradayMomentum(stop_atr=None), ZERO_COST, CONFIG)
        ).total_return
        for b in (0.0, 0.5, 1.0, 2.0)
    ]
    assert returns == sorted(returns), f"強さと結果が単調に対応していません: {returns}"


# ---------------------------------------------------------------------------
# 陰性対照：無いものを見つけないこと
# ---------------------------------------------------------------------------


def test_finds_nothing_when_the_pattern_is_absent():
    """同じ乱数列でパターンだけ消すと、コスト分だけ負ける。

    陽性対照との差は beta だけなので、
    ここで利益が出るならそれはパターン由来ではない。
    """
    report = evaluate(
        run_backtest(_frame(beta=0.0), IntradayMomentum(stop_atr=None), GMO_EXCHANGE, CONFIG)
    )
    assert report.total_return < 0, "パターンの無いデータで利益が出ています"
    assert report.trade_count > 50


def test_zero_cost_on_a_random_walk_is_a_coin_flip():
    """コストを外すと、パターンの無いデータでの成績はほぼゼロになる。

    ここが明確にプラスなら、エンジンが利益を作っている（先読みなど）。
    明確にマイナスなら、エンジンが利益を削っている。どちらもバグ。
    """
    report = evaluate(
        run_backtest(_frame(beta=0.0), IntradayMomentum(stop_atr=None), ZERO_COST, CONFIG)
    )
    assert abs(report.total_return) < 0.10, (
        f"コストゼロのランダムウォークで {report.total_return * 100:+.2f}% は説明がつきません"
    )


def test_the_control_data_itself_has_no_drift():
    """陰性対照データに、そもそも方向の偏りが無いことを確かめる。

    データ側が上昇していたら、どんな戦略でもロングで勝ててしまう。
    """
    df = _frame(beta=0.0)
    log_returns = np.diff(np.log(df["close"].to_numpy()))
    t_stat = log_returns.mean() / (log_returns.std(ddof=1) / np.sqrt(len(log_returns)))
    assert abs(t_stat) < 2.0, f"対照データにドリフトがあります（t={t_stat:.2f}）"


# ---------------------------------------------------------------------------
# 因果性と整合
# ---------------------------------------------------------------------------


def test_intraday_momentum_is_causal():
    violations = check_causality(IntradayMomentum(), _frame(beta=1.0, bars=1200))
    assert violations == [], "\n".join(str(v) for v in violations)


def test_causal_with_a_shifted_session_boundary():
    """セッションの区切りをずらしても因果性が保たれる。"""
    strategy = IntradayMomentum(session_start_hour=9, entry_bars=2, exit_bars=3)
    violations = check_causality(strategy, _frame(beta=1.0, bars=1200))
    assert violations == [], "\n".join(str(v) for v in violations)


def test_session_boundary_does_not_depend_on_where_the_data_starts():
    """データの開始位置を変えても、同じ時刻は同じセッション位置になる。

    最初の行を基点にすると、切り出し方が変わるだけで
    セッションの区切りが動いてしまう。時計で区切っていればそうならない。
    """
    strategy = IntradayMomentum(stop_atr=None)
    df = _frame(beta=1.0, bars=1200)
    offset = 7  # セッションの途中から始める

    full = strategy.generate(df)
    partial = strategy.generate(df.iloc[offset:])

    overlap = full["direction"].to_numpy()[offset:]
    # 冒頭のセッションは entry 窓が切れているので判断材料が無く、その分だけずれる
    assert np.array_equal(overlap[SESSION_BARS:], partial["direction"].to_numpy()[SESSION_BARS:])


def test_index_resolution_does_not_change_the_answer():
    """index の分解能（ns / us / ms）で結果が変わってはいけない。

    pandas は入力によって datetime64[ns] にも [us] にもなる。
    分解能に依存した時刻計算をすると、
    **同じデータを読み込み方だけ変えて結果が変わる**という最悪の壊れ方をする。
    """
    df = _frame(beta=1.0, bars=600)
    strategy = IntradayMomentum(stop_atr=None)

    answers = []
    for unit in ("ns", "us", "ms"):
        reindexed = df.copy()
        reindexed.index = df.index.astype(f"datetime64[{unit}, UTC]")
        answers.append(strategy.generate(reindexed)["direction"].to_numpy())

    for other in answers[1:]:
        assert np.array_equal(answers[0], other)


def test_holds_the_last_bar_of_the_session_not_the_first_of_the_next():
    """執行が1本ずれていないことを、位置で直接確かめる。

    エンジンは direction[t] をバー t+1 の始値で執行する。
    終盤の窓にそのまま direction を立てると、
    実際に持つのは**次のセッションの頭**になる。この取り違えは
    成績が出てしまうぶん気づきにくい。
    """
    df = _flat_frame_with_session_open_jump(sessions=4)
    strategy = IntradayMomentum(stop_atr=None)

    direction = strategy.generate(df)["direction"].to_numpy()
    position = np.arange(len(df)) % SESSION_BARS

    # シグナルが立つのは「最終バーの1本前」だけ
    assert set(np.unique(position[direction != 0])) == {SESSION_BARS - 2}

    result = run_backtest(df, strategy, ZERO_COST, CONFIG)
    assert result.trades, "トレードが発生していません"
    for trade in result.trades:
        entry_pos = df.index.get_loc(trade.entry_time) % SESSION_BARS
        assert entry_pos == SESSION_BARS - 1, "セッション最終バー以外で建てています"


def test_flat_session_body_yields_no_profit_without_the_pattern():
    """横ばいのバーを持っただけでは利益が出ない（建値の確認）。

    セッション初バーの +1% を取れてしまっていたら、
    それは動いたあとのバーを持てているという先読みになる。
    """
    df = _flat_frame_with_session_open_jump(sessions=6)
    report = evaluate(run_backtest(df, IntradayMomentum(stop_atr=None), ZERO_COST, CONFIG))
    assert abs(report.total_return) < 1e-9, (
        f"横ばい区間で {report.total_return * 100:+.4f}% 出ています"
    )


# ---------------------------------------------------------------------------
# 設定の妥当性
# ---------------------------------------------------------------------------


def test_overlapping_windows_are_rejected():
    """測る窓と持つ窓が重なる設定は受け付けない。

    重なると、同じバーの値動きを見てそのバーに賭けることになる。
    それは戦略ではなく先読みなので、黙って通してはいけない。
    """
    strategy = IntradayMomentum(entry_bars=13, exit_bars=13)
    with pytest.raises(ValueError, match="多すぎ"):
        strategy.generate(_frame(beta=1.0, bars=300))


def test_breakeven_matches_the_cost_arithmetic():
    """検出できる信号の下限が、コストの算術と一致する。

    1トレードの粗利の期待値は、ロングだけ取る場合

        beta × sigma × sqrt(2/π)

    で、これが往復コストを超えたところが分岐点になる。
    成行（往復0.180%）なら beta=0.376、指値（往復0.020%）なら beta=0.042。

    実測がこの計算とずれるなら、**エンジンのコスト計上が算術と合っていない。**
    戦略の検証というより、エンジンの検算にあたる。
    """
    sigma = 0.006
    gross_per_trade = sigma * np.sqrt(2.0 / np.pi)
    breakeven_beta = GMO_EXCHANGE.round_trip_rate(OrderType.TAKER) / gross_per_trade
    assert 0.3 < breakeven_beta < 0.45, breakeven_beta

    def mean_return(beta: float) -> float:
        returns = []
        for seed in (1, 2, 3):
            df = _frame(beta=beta, seed=seed, bars=20_000)
            returns.append(
                evaluate(
                    run_backtest(df, IntradayMomentum(stop_atr=None), GMO_EXCHANGE, CONFIG)
                ).total_return
            )
        return float(np.mean(returns))

    assert mean_return(breakeven_beta * 0.8) < 0, "分岐点より弱い信号で利益が出ています"
    assert mean_return(breakeven_beta * 1.2) > 0, "分岐点より強い信号を取り切れていません"


def test_threshold_reduces_the_number_of_trades():
    """閾値を上げれば取引回数は減る。ノイズで動かないための調整。"""
    df = _frame(beta=1.0)
    counts = [
        int((IntradayMomentum(threshold=t).generate(df)["direction"] != 0).sum())
        for t in (0.0, 0.005, 0.02)
    ]
    assert counts[0] > counts[1] > counts[2]
