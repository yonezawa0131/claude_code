"""試行数を考慮した判定の検証。

`expected_max_sharpe` は「優位性ゼロの戦略を N 個試したとき、
最良のものが示すシャープ」を返す。式としては正しかったが、
**返す値の単位が、比較相手の単位と違っていた。**

  - `growth.expected_max_sharpe` … 1バーあたり
  - `metrics.sharpe_ratio`        … 年率化済み

1時間足なら sqrt(8766) = 93.6 倍のずれになる。
この状態では、閾値が実際より約94分の1に出るので、
**安全装置として一切機能しない。**

ここでは3つ確かめる。
  1. 式が、優位性ゼロの系列で実際に起きることと一致するか
  2. 単位を合わせた閾値が、実際のバックテストの最大シャープと合うか
  3. 本物の優位性は通り、偶然は弾かれるか
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
from trading.src.costs import ZERO_COST  # noqa: E402
from trading.src.growth import expected_max_sharpe, is_sharpe_meaningful  # noqa: E402
from trading.src.metrics import evaluate, multiple_testing_report  # noqa: E402
from trading.src.strategy import IntradayMomentum, RandomEntry  # noqa: E402

HOURLY_PERIODS_PER_YEAR = 365.0 * 24
CONFIG = BacktestConfig(initial_capital=300_000.0, position_fraction=1.0)


def _frame(regime: str, seed: int, bars: int = 5000, **kw) -> pd.DataFrame:
    df = make_synthetic_ohlcv(bars, seed, regime, **kw)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    return df.set_index("timestamp")


# ---------------------------------------------------------------------------
# 1. 式そのものが、優位性ゼロの世界で起きることと一致するか
# ---------------------------------------------------------------------------


def test_formula_matches_simulation_of_worthless_strategies():
    """優位性ゼロの系列を N 本作って最良を取る、を繰り返した実測と一致すること。

    式の導出を信じるのではなく、**式が主張していることを実際に起こして確かめる。**
    """
    rng = np.random.default_rng(20260802)
    n_obs = 2000

    for n_trials in (5, 20, 100):
        maxima = [
            (lambda r: (r.mean(axis=1) / r.std(axis=1, ddof=1)).max())(
                rng.standard_normal((n_trials, n_obs))
            )
            for _ in range(3000)
        ]
        empirical = float(np.mean(maxima))
        predicted = expected_max_sharpe(n_trials, n_obs)
        assert abs(empirical - predicted) / predicted < 0.12, (
            f"試行数 {n_trials}: 実測 {empirical:.5f} / 式 {predicted:.5f}"
        )


def test_one_trial_needs_no_correction():
    assert expected_max_sharpe(1, 1000) == 0.0


def test_threshold_rises_with_the_number_of_trials():
    values = [expected_max_sharpe(n, 1000) for n in (2, 10, 100, 1000)]
    assert values == sorted(values)


# ---------------------------------------------------------------------------
# 2. 単位
# ---------------------------------------------------------------------------


def test_annualising_scales_the_threshold_by_the_square_root():
    """年率化係数は、標準誤差に sqrt() で効くこと。"""
    per_bar = expected_max_sharpe(50, 5000)
    annual = expected_max_sharpe(50, 5000, periods_per_year=HOURLY_PERIODS_PER_YEAR)
    assert annual == pytest.approx(per_bar * np.sqrt(HOURLY_PERIODS_PER_YEAR))
    # 1時間足では約94倍。ここを揃え忘れると安全装置が働かない
    assert annual / per_bar > 90


def test_the_unit_mismatch_would_have_passed_pure_noise():
    """**単位を合わせないと、純粋なノイズが合格してしまう。**

    このテストは良い性質ではなく、**直した欠陥を固定する**ためにある。
    優位性ゼロのデータで最も良く見えた戦略の年率シャープを、
    1バーあたりの閾値と比べると通ってしまうことを示す。
    """
    df = _frame("random", seed=1000)
    sharpes = [
        evaluate(run_backtest(df, RandomEntry(seed=s), ZERO_COST, CONFIG)).sharpe
        for s in range(12)
    ]
    best = max(sharpes)
    assert best > 0, "この対照データでは偶然の勝ちが出ていないので検証にならない"

    passes_wrong, wrong = is_sharpe_meaningful(best, 12, 4999)  # 単位を揃えない
    passes_right, right = is_sharpe_meaningful(
        best, 12, 4999, periods_per_year=HOURLY_PERIODS_PER_YEAR
    )
    assert passes_wrong, "この対照データでは元の欠陥が再現しません"
    assert not passes_right, f"年率化した閾値 {right:.2f} をノイズが超えました（{best:.2f}）"
    assert right > wrong * 90


def test_report_carries_the_units_needed_for_the_check():
    """Report が年率化係数と観測数を持っていること。

    素の float を渡す API では単位を取り違えられる。
    Report 経由なら取り違えようがない、というのが直し方の要点。
    """
    report = evaluate(run_backtest(_frame("random", seed=1001), RandomEntry(), ZERO_COST, CONFIG))
    assert report.periods_per_year == pytest.approx(HOURLY_PERIODS_PER_YEAR, rel=1e-6)
    assert report.n_observations == len(_frame("random", seed=1001)) - 1


# ---------------------------------------------------------------------------
# 3. 本物は通り、偶然は弾かれるか
# ---------------------------------------------------------------------------


def test_noise_is_rejected_and_a_real_edge_is_not():
    """陽性対照と陰性対照を、同じ試行数で判定する。"""
    n_trials = 7  # --compare-all と同じ本数

    noise = max(
        (
            evaluate(run_backtest(_frame("random", seed=1002), RandomEntry(seed=s), ZERO_COST, CONFIG))
            for s in range(n_trials)
        ),
        key=lambda r: r.sharpe,
    )
    real = evaluate(
        run_backtest(
            _frame("intraday", seed=7, beta=1.0),
            IntradayMomentum(stop_atr=None),
            ZERO_COST,
            CONFIG,
        )
    )

    _, threshold = is_sharpe_meaningful(
        0.0, n_trials, real.n_observations, periods_per_year=real.periods_per_year
    )
    assert noise.sharpe < threshold < real.sharpe, (
        f"ノイズ {noise.sharpe:.2f} / 閾値 {threshold:.2f} / 本物 {real.sharpe:.2f}"
    )


def test_report_text_names_the_verdict():
    real = evaluate(
        run_backtest(
            _frame("intraday", seed=7, beta=1.0),
            IntradayMomentum(stop_atr=None),
            ZERO_COST,
            CONFIG,
        )
    )
    assert "偶然の水準を" in multiple_testing_report(real, n_trials=7)

    weak = evaluate(run_backtest(_frame("random", seed=1003), RandomEntry(), ZERO_COST, CONFIG))
    assert "たくさん試したことだけで説明がつきます" in multiple_testing_report(weak, n_trials=50)


def test_a_single_trial_is_called_out_as_uncounted():
    """試行数1で呼ばれたら、数え忘れの可能性を明示すること。

    既定値で通されると閾値0になり、何でも合格する。
    黙って合格させるのが一番危ない。
    """
    report = evaluate(run_backtest(_frame("random", seed=1004), RandomEntry(), ZERO_COST, CONFIG))
    assert "実際に試した数を数えて渡さないと" in multiple_testing_report(report, n_trials=1)


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        expected_max_sharpe(0, 1000)
    with pytest.raises(ValueError):
        expected_max_sharpe(10, 1)
    with pytest.raises(ValueError):
        expected_max_sharpe(10, 1000, periods_per_year=0)
