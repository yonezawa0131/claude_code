"""外部要因まわりの検査。

一番大事なのは「公表前の値が過去のバーに漏れないこと」。
この漏れは check_causality() では捕まらないので、ここで止める。

実行:
    .venv-trading/bin/python trading/tests/test_exogenous.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from trading.src.costs import GMO_EXCHANGE, ZERO_COST  # noqa: E402
from trading.src.exogenous import (  # noqa: E402
    BlackoutFilter,
    ExogenousSeries,
    SessionFilter,
    effective_sample_size,
    sample_size_report,
    session_of,
)
from trading.src.strategy import BuyAndHold, EmaCrossATR  # noqa: E402
from trading.src.validate import check_causality  # noqa: E402


def make_frame(n: int = 600, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 10_000_000 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.002,
            "low": np.minimum(open_, close) * 0.998,
            "close": close,
            "volume": np.ones(n),
        },
        index=idx,
    )


# --- 公表時刻の扱い ---------------------------------------------------------


def test_exogenous_rejects_impossible_timing() -> None:
    """対象期間より前に「観測できた」ことになっているデータを弾くこと。"""
    frame = pd.DataFrame(
        {
            "refers_to": pd.to_datetime(["2026-07-01"], utc=True),
            "known_at": pd.to_datetime(["2026-06-01"], utc=True),  # 公表が対象より前
            "value": [1.0],
        }
    )
    try:
        ExogenousSeries("不正な指標", frame)
    except ValueError as exc:
        assert "先読み" in str(exc)
    else:
        raise AssertionError("公表前の値を受け入れてしまいました")


def test_exogenous_does_not_leak_future_values() -> None:
    """公表前の値が、それ以前のバーに割り当てられないこと。

    7月分のCPIが8月中旬に公表されるとき、
    7月のバーに7月分CPIを結合したら1ヶ月ぶん先読みしている。
    """
    idx = pd.date_range("2026-07-01", periods=60, freq="1D", tz="UTC")
    series = ExogenousSeries(
        "CPI",
        pd.DataFrame(
            {
                # 7月分の統計だが、公表は8月15日
                "refers_to": pd.to_datetime(["2026-07-31", "2026-08-31"], utc=True),
                "known_at": pd.to_datetime(["2026-08-15", "2026-09-15"], utc=True),
                "value": [3.2, 2.9],
            }
        ),
    )
    aligned = series.align_to(idx)

    before = aligned.loc[: pd.Timestamp("2026-08-14", tz="UTC")]
    assert before.isna().all(), "公表前のバーに値が漏れています"

    after = aligned.loc[pd.Timestamp("2026-08-16", tz="UTC") :]
    assert (after.dropna() == 3.2).all(), "公表後に7月分の値が反映されていません"


# --- サンプル数 -------------------------------------------------------------


def test_effective_sample_size_counts_events_not_bars() -> None:
    """外部要因の有効サンプル数が、バー数ではなくイベント回数になること。"""
    idx = pd.date_range("2024-01-01", periods=2 * 365 * 24, freq="1h", tz="UTC")
    bars, fomc = effective_sample_size(idx, events_per_year=8.0)
    assert bars > 17_000
    assert 15 <= fomc <= 17, f"2年間のFOMC回数が {fomc}"

    _, summers = effective_sample_size(idx, events_per_year=1.0)
    assert summers < 3, "2年間で夏は2回しかないはず"


def test_sample_size_report_flags_untestable_factors() -> None:
    """観測回数の少ない材料に「検証不能」の判定が付くこと。"""
    idx = pd.date_range("2024-01-01", periods=2 * 365 * 24, freq="1h", tz="UTC")
    report = sample_size_report(idx)
    assert "検証不能" in report
    # 夏季は2回しかないので必ず検証不能側
    summer_line = [l for l in report.splitlines() if "夏季" in l][0]
    assert "検証不能" in summer_line


# --- セッション -------------------------------------------------------------


def test_session_classification() -> None:
    """時間帯の分類が日本時間基準で正しいこと。"""
    idx = pd.date_range("2026-01-01", periods=24, freq="1h", tz="UTC")
    sessions = session_of(idx, tz="Asia/Tokyo")
    # UTC 00:00 = JST 09:00 → asia
    assert sessions.iloc[0] == "asia"
    # UTC 08:00 = JST 17:00 → europe
    assert sessions.iloc[8] == "europe"
    # UTC 14:00 = JST 23:00 → us
    assert sessions.iloc[14] == "us"


def test_session_filter_blocks_outside_hours() -> None:
    """許可外の時間帯でポジションを持たないこと。"""
    df = make_frame()
    filtered = SessionFilter(EmaCrossATR(), allowed_sessions=("us",))
    sig = filtered.generate(df)
    sessions = session_of(df.index, tz="Asia/Tokyo")
    outside = sig.loc[sessions != "us", "direction"]
    assert (outside == 0).all(), "許可外の時間帯にシグナルが出ています"


def test_session_filter_reduces_trades() -> None:
    """時間帯を絞ると取引回数が減ること（＝フィルタが効いていること）。"""
    df = make_frame(n=1200, seed=11)
    config = BacktestConfig(initial_capital=300_000)

    base_trades = len(run_backtest(df, EmaCrossATR(), GMO_EXCHANGE, config).trades)
    filtered_trades = len(
        run_backtest(
            df,
            SessionFilter(EmaCrossATR(), allowed_sessions=("us",)),
            GMO_EXCHANGE,
            config,
        ).trades
    )
    assert filtered_trades < base_trades, (
        f"フィルタ後の取引回数 {filtered_trades} が元の {base_trades} より減っていません"
    )


def test_wrappers_stay_causal() -> None:
    """ラッパーを噛ませても因果性が壊れないこと。"""
    df = make_frame(n=800, seed=13)
    events = pd.DatetimeIndex(["2026-01-10 12:00", "2026-01-20 12:00"], tz="UTC")

    for strategy in (
        SessionFilter(EmaCrossATR(), allowed_sessions=("us", "europe")),
        SessionFilter(BuyAndHold(), allowed_weekdays=(0, 1, 2, 3, 4)),
        BlackoutFilter(EmaCrossATR(), events=events),
    ):
        violations = check_causality(strategy, df, cuts=4)
        assert not violations, f"{strategy.name} が先読みしています: {violations[0]}"


def test_blackout_filter_blocks_around_events() -> None:
    """イベント前後でポジションを持たないこと。"""
    df = make_frame(n=400, seed=17)
    event = df.index[200]
    strategy = BlackoutFilter(
        BuyAndHold(), events=pd.DatetimeIndex([event]),
        before=pd.Timedelta("3h"), after=pd.Timedelta("3h"),
    )
    sig = strategy.generate(df)
    window = sig.loc[event - pd.Timedelta("3h") : event + pd.Timedelta("3h"), "direction"]
    assert (window == 0).all(), "イベント前後でシグナルが出ています"
    assert sig["direction"].sum() > 0, "全期間が止まってしまっています"


def test_weekday_filter_only_allows_given_days() -> None:
    """曜日フィルタが指定曜日以外を止めること。"""
    df = make_frame(n=24 * 30)
    strategy = SessionFilter(BuyAndHold(), allowed_weekdays=(0,))  # 月曜のみ
    sig = strategy.generate(df)
    weekday = pd.Series(df.index.tz_convert("Asia/Tokyo").weekday, index=df.index)
    assert (sig.loc[weekday != 0, "direction"] == 0).all()
    assert (sig.loc[weekday == 0, "direction"] == 1).all()


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
