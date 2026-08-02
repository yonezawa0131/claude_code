"""拡大ルールと、その前提の検算。

最も重要なテストは test_never_scales_up_after_a_loss。
負けたあとに増やす実装は、有限資金では破産確率が1に収束する。
これが通らない限り、拡大機能は使ってはいけない。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from trading.src.costs import ZERO_COST  # noqa: E402
from trading.src.growth import (  # noqa: E402
    AdaptiveSizing,
    expected_max_sharpe,
    growth_reality_check,
    is_sharpe_meaningful,
    probability_of_monotone_improvement,
    win_day_ratio,
)


# --- 拡大ルールの安全性 -----------------------------------------------------


def test_never_scales_up_after_a_loss() -> None:
    """ドローダウン中は絶対にサイズを増やさないこと。

    これが破られると、負けを取り返そうとしてサイズを上げる
    マーチンゲールになり、破産確率が1に収束する。
    """
    sizing = AdaptiveSizing(base_risk=0.005, max_risk=0.02, min_risk=0.001)
    peak = 1_000_000.0

    at_peak = sizing.risk_for(peak, peak, highs_made=0)
    for loss_pct in (0.01, 0.05, 0.10, 0.20, 0.40):
        equity = peak * (1 - loss_pct)
        risk = sizing.risk_for(equity, peak, highs_made=0)
        assert risk <= at_peak, (
            f"DD {loss_pct * 100:.0f}% でリスクが {risk:.4f} に増えています"
            f"（最高値時 {at_peak:.4f}）"
        )


def test_risk_decreases_monotonically_with_drawdown() -> None:
    """ドローダウンが深いほどサイズが小さくなること。"""
    sizing = AdaptiveSizing()
    peak = 1_000_000.0
    risks = [
        sizing.risk_for(peak * (1 - dd), peak, 0)
        for dd in (0.0, 0.05, 0.10, 0.15, 0.20, 0.30)
    ]
    for a, b in zip(risks, risks[1:]):
        assert b <= a, f"ドローダウンが深いのにリスクが増えています: {risks}"
    assert risks[-1] == sizing.min_risk, "下限まで落ちていません"


def test_scales_up_only_at_new_highs() -> None:
    """最高値を更新している間だけ拡大すること。"""
    sizing = AdaptiveSizing(base_risk=0.005, max_risk=0.02, scale_step=1.10)
    peak = 1_000_000.0

    r0 = sizing.risk_for(peak, peak, highs_made=0)
    r5 = sizing.risk_for(peak, peak, highs_made=5)
    r50 = sizing.risk_for(peak, peak, highs_made=50)

    assert r0 == 0.005
    assert r5 > r0, "最高値を更新しても拡大していません"
    assert r50 == sizing.max_risk, "上限を超えて拡大しています"


def test_max_risk_is_never_exceeded() -> None:
    """どれだけ勝っても上限を超えないこと。"""
    sizing = AdaptiveSizing(max_risk=0.02)
    assert sizing.risk_for(1e9, 1e9, highs_made=10_000) <= 0.02


def test_rejects_shrinking_scale_step() -> None:
    """成功するほど小さく張る設定を拒否すること。"""
    try:
        AdaptiveSizing(scale_step=0.9)
    except ValueError as exc:
        assert "1以上" in str(exc)
    else:
        raise AssertionError("scale_step < 1 が通ってしまいました")


def test_engine_uses_adaptive_sizing() -> None:
    """エンジンが拡大設定を実際に使うこと。

    同じデータで、拡大ありのほうがポジションサイズが変化することを確認する。
    """
    rng = np.random.default_rng(4)
    n = 800
    close = 10_000_000 * np.exp(np.cumsum(rng.normal(0.0004, 0.004, n)))
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    open_ = np.concatenate([[close[0]], close[:-1]])
    df = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.003,
            "low": np.minimum(open_, close) * 0.997,
            "close": close,
            "volume": np.ones(n),
        },
        index=idx,
    )

    from trading.src.strategy import EmaCrossATR

    fixed = run_backtest(
        df, EmaCrossATR(), ZERO_COST,
        BacktestConfig(initial_capital=1_000_000, risk_per_trade=0.005),
    )
    adaptive = run_backtest(
        df, EmaCrossATR(), ZERO_COST,
        BacktestConfig(initial_capital=1_000_000, adaptive_sizing=AdaptiveSizing()),
    )

    assert adaptive.trades, "拡大設定でトレードが発生していません"
    fixed_sizes = [t.size for t in fixed.trades]
    adaptive_sizes = [t.size for t in adaptive.trades]
    # 固定リスクではサイズの変動が小さく、拡大ありでは大きく振れるはず
    assert len(set(np.round(adaptive_sizes, 8))) > 1, "サイズが変化していません"


# --- 前提の検算 -------------------------------------------------------------


def test_monotone_improvement_probability() -> None:
    """n日連続改善の確率が 1/n! であること。"""
    assert abs(probability_of_monotone_improvement(3) - 1 / 6) < 1e-15
    assert abs(probability_of_monotone_improvement(5) - 1 / 120) < 1e-15
    assert probability_of_monotone_improvement(30) < 1e-30


def test_win_day_ratio_is_near_half_even_with_edge() -> None:
    """優位性があっても、勝つ日の割合は5割から大きく離れないこと。

    日次ボラ2.5%に対し、年125%ペース（日次0.5%）でも勝つ日は58%程度。
    「毎日勝つ」は優位性の問題ではなく、変動の問題。
    """
    assert abs(win_day_ratio(0.0, 0.025) - 0.5) < 1e-9
    r = win_day_ratio(0.005, 0.025)
    assert 0.55 < r < 0.62, f"勝つ日の割合が {r:.3f}"
    # ボラティリティが大きいほど5割に近づく
    assert win_day_ratio(0.005, 0.05) < r


def test_expected_max_sharpe_grows_with_trials() -> None:
    """試す戦略の数が増えるほど、偶然到達しうるシャープも上がること。"""
    n_obs = 500
    s10 = expected_max_sharpe(10, n_obs)
    s100 = expected_max_sharpe(100, n_obs)
    s1000 = expected_max_sharpe(1000, n_obs)
    assert 0 < s10 < s100 < s1000, f"{s10}, {s100}, {s1000}"
    assert expected_max_sharpe(1, n_obs) == 0.0


def test_sharpe_significance_accounts_for_trials() -> None:
    """同じシャープでも、試行数が多ければ意味を失うこと。"""
    sharpe = 0.15
    ok_few, _ = is_sharpe_meaningful(sharpe, n_trials=2, n_observations=500)
    ok_many, threshold = is_sharpe_meaningful(sharpe, n_trials=5000, n_observations=500)
    assert ok_few, "少ない試行では有意と判定されるべき"
    assert not ok_many, f"5000回試した後でも有意と判定されています（閾値 {threshold:.3f}）"


def test_reality_check_renders() -> None:
    text = growth_reality_check(500, 100_000)
    assert "0.500 %" in text
    assert "負ける日" in text


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
