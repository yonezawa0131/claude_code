"""追加した指標と戦略の検査。因果性が最重要。

一目均衡表は「先行スパンを未来にずらして描画する」ため
先読みに見えやすい。実装が過去参照になっているかをここで確かめる。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src import indicators as ind  # noqa: E402
from trading.src.strategy import DonchianBreakout, IchimokuTrend  # noqa: E402
from trading.src.validate import check_causality  # noqa: E402


def make_frame(n: int = 500, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 10_000_000 * np.exp(np.cumsum(rng.normal(0.0002, 0.005, n)))
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.003,
            "low": np.minimum(open_, close) * 0.997,
            "close": close,
            "volume": np.ones(n),
        },
        index=idx,
    )


def test_adx_range_and_trend_sensitivity() -> None:
    """ADXが0〜100に収まり、トレンド相場で高くなること。"""
    n = 300
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    trend = pd.Series(np.linspace(100, 300, n), index=idx)
    chop = pd.Series(100 + 2 * np.sin(np.arange(n) / 2), index=idx)

    for series, label in ((trend, "trend"), (chop, "chop")):
        high = series * 1.002
        low = series * 0.998
        adx, p, m = ind.directional_movement(high, low, series, 14)
        valid = adx.dropna()
        assert (valid >= 0).all() and (valid <= 100).all(), f"{label}: ADXが範囲外"

    adx_t, _, _ = ind.directional_movement(trend * 1.002, trend * 0.998, trend, 14)
    adx_c, _, _ = ind.directional_movement(chop * 1.002, chop * 0.998, chop, 14)
    assert adx_t.dropna().mean() > adx_c.dropna().mean(), "ADXがトレンドを検出できていません"


def test_donchian_excludes_current_bar() -> None:
    """ドンチャンチャネルが現在のバーを含まないこと。

    含めてしまうと高値更新の判定が成立しなくなる。
    """
    idx = pd.date_range("2026-01-01", periods=10, freq="1h", tz="UTC")
    high = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 100.0], index=idx)
    low = pd.Series([9.0] * 10, index=idx)
    upper, lower = ind.donchian(high, low, 5)
    # 最終バーの高値100はチャネル上限に含まれてはいけない
    assert upper.iloc[-1] < 100.0, "現在のバーがチャネルに含まれています"


def test_pivot_uses_previous_bar_only() -> None:
    """ピボットが前のバーだけから決まること。"""
    idx = pd.date_range("2026-01-01", periods=4, freq="1D", tz="UTC")
    high = pd.Series([110.0, 120.0, 130.0, 140.0], index=idx)
    low = pd.Series([90.0, 100.0, 110.0, 120.0], index=idx)
    close = pd.Series([100.0, 110.0, 120.0, 130.0], index=idx)
    p, r1, s1, r2, s2 = ind.pivot_points(high, low, close)
    assert np.isnan(p.iloc[0]), "最初のバーにピボットが出ています"
    assert abs(p.iloc[1] - (110 + 90 + 100) / 3) < 1e-9


def test_ichimoku_cloud_is_backward_looking() -> None:
    """先行スパンが過去参照になっていること（描画のずらしと混同していない）。"""
    df = make_frame(300)
    ich = ind.ichimoku(df["high"], df["low"], df["close"])
    # senkou_a は 26本前の値から作られるので、先頭26本+warmupはNaN
    assert ich["senkou_a"].iloc[:26].isna().all(), "先行スパンが未来を参照しています"
    # 打ち切っても既存の値が変わらないこと
    part = ind.ichimoku(df["high"].iloc[:200], df["low"].iloc[:200], df["close"].iloc[:200])
    a_full = ich["senkou_a"].iloc[:200].to_numpy()
    a_part = part["senkou_a"].to_numpy()
    both_nan = np.isnan(a_full) & np.isnan(a_part)
    assert np.all(both_nan | np.isclose(a_full, a_part, equal_nan=False))


def test_new_strategies_are_causal() -> None:
    """追加した戦略がすべて因果的であること。"""
    df = make_frame(600, seed=9)
    for strategy in (
        DonchianBreakout(),
        DonchianBreakout(adx_threshold=None),
        DonchianBreakout(allow_short=True),
        IchimokuTrend(),
        IchimokuTrend(allow_short=True),
    ):
        violations = check_causality(strategy, df, cuts=4)
        assert not violations, f"{strategy.name} が先読みしています: {violations[0]}"


def test_adx_filter_reduces_trades() -> None:
    """ADXフィルタが取引回数を減らすこと（フィルタとして機能していること）。"""
    df = make_frame(1500, seed=21)
    with_filter = DonchianBreakout(adx_threshold=25.0).generate(df)
    without = DonchianBreakout(adx_threshold=None).generate(df)
    changes_with = int((with_filter["direction"].diff() != 0).sum())
    changes_without = int((without["direction"].diff() != 0).sum())
    assert changes_with <= changes_without, "ADXフィルタが取引を減らしていません"


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
