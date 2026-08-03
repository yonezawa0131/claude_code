"""ローテーション検定の検証。

実データ（BTC/JPY日足944本）を初めて回したとき、**コイン投げの対照群が
全戦略に勝った**。買い持ちにも +2.06pt 勝っていた。

これを「タイミングが良かった」と読むか「上げ相場に居合わせただけ」と読むかで、
結論が正反対になる。理論的な閾値（growth.expected_max_sharpe）は
リターンが独立同分布であることを前提にしているので、
**トレンドのある相場では、この区別ができない。**

ローテーション検定は、ポジション系列を時間方向に回す。
取引回数・保有期間・市場に晒されている時間・そして相場そのものは全部残り、
**「いつ建てたか」だけが壊れる**。だから差はタイミングだけに由来する。

ここで確かめるのは2つ。
  1. 本物の優位性を、上位として検出できるか
  2. 上げ相場に居合わせただけのものを、上位と言わないか

2つ目が本題。1つ目だけなら、常に「上位」と答える実装でも通ってしまう。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts.make_synthetic import make_synthetic_ohlcv  # noqa: E402
from trading.src.backtest import BacktestConfig  # noqa: E402
from trading.src.costs import GMO_EXCHANGE  # noqa: E402
from trading.src.strategy import IntradayMomentum, RandomEntry  # noqa: E402
from trading.src.validate import rotation_null  # noqa: E402

CONFIG = BacktestConfig(initial_capital=300_000.0, position_fraction=1.0)
RUNS = 120


def _frame(regime: str, seed: int = 5, bars: int = 6_000, **kw) -> pd.DataFrame:
    df = make_synthetic_ohlcv(bars, seed, regime, **kw)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    return df.set_index("timestamp")


# ---------------------------------------------------------------------------
# 本物を検出できるか
# ---------------------------------------------------------------------------


def test_a_real_edge_ranks_at_the_top():
    """埋め込んだ優位性は、ずらすと再現しないこと。"""
    result = rotation_null(
        _frame("intraday", beta=1.0),
        IntradayMomentum(stop_atr=None),
        GMO_EXCHANGE,
        CONFIG,
        n_runs=RUNS,
    )
    assert result.return_percentile >= 95, (
        f"実測 {result.observed_return * 100:+.1f}% / "
        f"ずらすと中央値 {np.median(result.null_returns) * 100:+.1f}% / "
        f"上位 {100 - result.return_percentile:.1f}%"
    )
    assert "タイミングだったこと" in result.summary()


# ---------------------------------------------------------------------------
# 相場に居合わせただけのものを、実力と言わないか
# ---------------------------------------------------------------------------


def test_a_coin_flip_in_a_rising_market_is_not_credited():
    """**この検定を作った理由。**

    上げ相場のコイン投げは大きなプラスを出す。
    しかし同じ売買パターンをどこに置いても同じだけ出るので、
    タイミングの実力ではない。
    """
    result = rotation_null(
        _frame("trend"), RandomEntry(seed=0), GMO_EXCHANGE, CONFIG, n_runs=RUNS
    )
    assert result.observed_return > 0.5, "上げ相場で大きなプラスが出ていないと検証にならない"
    assert result.return_percentile < 95, (
        f"相場に居合わせただけの成績を上位と判定しています"
        f"（実測 {result.observed_return * 100:+.1f}% / "
        f"ずらすと中央値 {np.median(result.null_returns) * 100:+.1f}%）"
    )
    assert "タイミングの良さでは説明できません" in result.summary()


def test_a_coin_flip_on_a_random_walk_is_not_credited():
    result = rotation_null(
        _frame("random"), RandomEntry(seed=0), GMO_EXCHANGE, CONFIG, n_runs=RUNS
    )
    assert result.return_percentile < 95


def test_the_null_distribution_sits_near_the_market_not_near_zero():
    """上げ相場では、ずらした対照も大きなプラスになること。

    対照が0付近に固まるなら、相場の効果が対照側に入っていない。
    それでは「居合わせただけ」を差し引けない。
    """
    result = rotation_null(
        _frame("trend"), RandomEntry(seed=0), GMO_EXCHANGE, CONFIG, n_runs=RUNS
    )
    assert np.median(result.null_returns) > 0.5


# ---------------------------------------------------------------------------
# 何を残し、何を壊しているか
# ---------------------------------------------------------------------------


def test_rotation_preserves_how_often_the_strategy_trades():
    """回しても取引回数がだいたい保たれること。

    ここが崩れていると、比べているのは別の売買パターンになる。
    """
    df = _frame("trend")
    strategy = RandomEntry(seed=0)
    direction = strategy.generate(df)["direction"].to_numpy()

    changes = int((np.diff(direction) != 0).sum())
    for offset in (137, 1_500, 4_321):
        rotated = np.roll(direction, offset)
        # 回転で継ぎ目が1つ増減しうる以外は同じ
        assert abs(int((np.diff(rotated) != 0).sum()) - changes) <= 1


def test_rotation_preserves_time_in_market():
    df = _frame("trend")
    direction = RandomEntry(seed=0).generate(df)["direction"].to_numpy()
    exposure = float((direction != 0).mean())
    assert float((np.roll(direction, 999) != 0).mean()) == pytest.approx(exposure)


def test_stops_are_rotated_as_ratios_not_as_price_levels():
    """損切りを価格のままずらすと、その時点の価格と無関係な水準になる。

    比率でずらしていれば、対照側の損切り距離は実際と同程度に保たれる。
    ずらした結果の損切りが、価格から極端に離れていないことを確認する。
    """
    df = _frame("trend", bars=3_000)
    result = rotation_null(
        df, IntradayMomentum(stop_atr=2.0), GMO_EXCHANGE, CONFIG, n_runs=30
    )
    # 価格水準のままずらしていたら、対照の成績が現実離れした値に飛ぶ
    assert np.isfinite(result.null_returns).all()
    assert result.null_returns.min() > -1.0, "資産がマイナスになっています"


# ---------------------------------------------------------------------------
# 使い方の制約
# ---------------------------------------------------------------------------


def test_too_few_runs_is_rejected():
    with pytest.raises(ValueError, match="20回以上"):
        rotation_null(_frame("trend", bars=2_000), RandomEntry(), GMO_EXCHANGE, CONFIG, n_runs=5)


def test_too_little_data_to_rotate_is_rejected():
    """ウォームアップに対してデータが短いと、ずらす幅が取れない。

    黙って狭い範囲で回すと、対照が元の並びとほとんど同じになり、
    どんな戦略でも「上位ではない」と出てしまう。
    """
    df = _frame("trend", bars=3_000).iloc[:60]
    with pytest.raises(ValueError, match="ずらせる幅"):
        rotation_null(df, IntradayMomentum(), GMO_EXCHANGE, CONFIG, n_runs=50)
