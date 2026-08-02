"""指値の約定モデルの検証。

`docs/02` は「成行を減らし、指値を使う」を実証研究付きで挙げている。
しかしエンジンは長らく**「指値を並べたら必ず約定する」**前提で計算していた。
その前提の上で「指値なら往復コストが9分の1」と書いていた。

ここで確かめるのは3つ。
  1. 約定判定が、板の順番が分からない以上、**約定しない側に倒れているか**
  2. 損切りが、指値ではなく**必ず成行**として扱われているか
  3. 逆選択（約定するのは不利なときだけ）が、**モデル化せずに出てくるか**

3つ目が要点。逆選択は係数を置いて表現するものではなく、
正直に約定判定すれば勝手に現れる。やるべきなのは打ち消さないことだけ。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts.make_synthetic import make_synthetic_ohlcv  # noqa: E402
from trading.src.backtest import (  # noqa: E402
    BacktestConfig,
    MakerFill,
    Side,
    run_backtest,
)
from trading.src.costs import GMO_EXCHANGE, OrderType  # noqa: E402
from trading.src.metrics import evaluate  # noqa: E402
from trading.src.strategy import IntradayMomentum  # noqa: E402

OFFSET = 0.0002


@dataclass
class _Scripted:
    """テスト用。バーごとの目標ポジションを直接指定する。"""

    directions: list[float]
    stop: float | None = None
    name: str = "台本"
    _unused: tuple = field(default=(), repr=False)

    def warmup(self) -> int:
        return 1

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        d = np.zeros(len(df))
        d[: len(self.directions)] = self.directions[: len(df)]
        return pd.DataFrame(
            {
                "direction": d,
                "stop_loss": np.full(len(df), np.nan if self.stop is None else self.stop),
                "take_profit": np.full(len(df), np.nan),
            },
            index=df.index,
        )


def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """(open, high, low, close) の並びから1時間足を作る。"""
    o, h, l, c = (np.array(x, dtype=float) for x in zip(*rows))
    return pd.DataFrame(
        {
            "open": o,
            "high": np.maximum.reduce([h, o, c]),
            "low": np.minimum.reduce([l, o, c]),
            "close": c,
            "volume": np.ones(len(rows)),
        },
        index=pd.date_range("2024-01-01", periods=len(rows), freq="h", tz="UTC"),
    )


def _maker_config(**kw) -> BacktestConfig:
    return BacktestConfig(
        initial_capital=1_000_000.0,
        order_type=OrderType.MAKER,
        maker_fill=MakerFill(offset=OFFSET, **kw),
    )


# ---------------------------------------------------------------------------
# 約定判定
# ---------------------------------------------------------------------------


def test_limit_does_not_fill_when_the_bar_never_reaches_it():
    """安値が指値まで来なければ約定しない。当たり前だが、ここが出発点。"""
    limit = 100.0 * (1 - OFFSET)
    df = _bars([(100, 100, 100, 100), (100, 101, limit + 0.005, 101), (101, 101, 101, 101)])
    result = run_backtest(df, _Scripted([1.0, 1.0, 0.0]), GMO_EXCHANGE, _maker_config())
    assert result.trades == []
    assert any("約定しなかった" in w for w in result.warnings)


def test_limit_fills_when_the_bar_trades_through_it():
    limit = 100.0 * (1 - OFFSET)
    df = _bars([(100, 100, 100, 100), (100, 101, limit - 0.5, 101), (101, 101, 101, 101)])
    result = run_backtest(df, _Scripted([1.0, 0.0, 0.0]), GMO_EXCHANGE, _maker_config())
    assert len(result.trades) == 1
    assert result.trades[0].side is Side.LONG


def test_touching_the_limit_is_not_treated_as_a_fill():
    """指値と同値までしか来なかった場合は約定させない。

    板に先に並んでいた注文が優先されるので、自分まで回るとは限らない。
    OHLCVからは順番が分からない以上、**約定しない側に倒す**。
    """
    limit = 100.0 * (1 - OFFSET)
    df = _bars([(100, 100, 100, 100), (100, 101, limit, 101), (101, 101, 101, 101)])
    result = run_backtest(df, _Scripted([1.0, 1.0, 0.0]), GMO_EXCHANGE, _maker_config())
    assert result.trades == []


def test_offset_changes_whether_it_fills_but_not_the_price():
    """**深い指値で値段は良くならない。**

    スプレッドを払わずに済む分は cost_rate(MAKER) が既に織り込んでいる。
    ここで値段も良くすると二重計上になる。最初の実装はそれを間違えていて、
    EMAクロス戦略の成績を実際の2倍以上に見せていた。
    """
    df = _bars([(100, 100, 100, 100), (100, 101, 90, 101), (101, 101, 101, 101)])
    prices = []
    for offset in (0.0002, 0.0100):
        result = run_backtest(
            df,
            _Scripted([1.0, 0.0, 0.0]),
            GMO_EXCHANGE,
            BacktestConfig(
                initial_capital=1_000_000.0,
                order_type=OrderType.MAKER,
                maker_fill=MakerFill(offset=offset),
            ),
        )
        assert len(result.trades) == 1, offset
        prices.append(result.trades[0].entry_price)
    assert prices[0] == pytest.approx(prices[1])


def test_unfilled_exit_keeps_the_position():
    """降りたい場面で指値が約定しなければ、ポジションは残る。

    「降りられなかった」を「降りた」ことにしてはいけない。
    """
    entry_low = 100.0 * (1 - OFFSET) - 0.5
    # 3本目で手仕舞いたいが、高値が売り指値まで届かない
    exit_limit = 100.0 * (1 + OFFSET)
    df = _bars(
        [
            (100, 100, 100, 100),
            (100, 101, entry_low, 100),
            (100, exit_limit - 0.005, 99, 100),
            (100, 105, 99, 104),
        ]
    )
    result = run_backtest(df, _Scripted([1.0, 0.0, 0.0, 0.0]), GMO_EXCHANGE, _maker_config())
    assert len(result.trades) == 1
    # 3本目では降りられず、4本目まで持ち越している
    assert result.trades[0].exit_time > df.index[2]
    assert any("決済 1 回" in w for w in result.warnings)


def test_chase_at_close_falls_back_to_a_market_order():
    """約定しなければ終値で成行に切り替える設定。手数料は成行のものになる。"""
    limit = 100.0 * (1 - OFFSET)
    df = _bars([(100, 100, 100, 100), (100, 101, limit + 0.005, 101), (101, 101, 101, 101)])
    result = run_backtest(df, _Scripted([1.0, 0.0, 0.0]), GMO_EXCHANGE, _maker_config(chase_at_close=True))
    assert len(result.trades) == 1
    # 終値101で、成行のコストを乗せて約定している
    taker = GMO_EXCHANGE.cost_rate(OrderType.TAKER)
    assert result.trades[0].entry_price == pytest.approx(101.0 * (1 + taker))


# ---------------------------------------------------------------------------
# 損切りは指値では置けない
# ---------------------------------------------------------------------------


def test_stop_loss_always_pays_the_taker_cost():
    """**損切りは常に成行。**

    逆行しているときに指値を置いても約定しない。
    指値戦略でも、損切りだけはスプレッドを払う。
    ここを MAKER のままにすると、一番払うところを払わない計算になる。
    """
    entry_low = 100.0 * (1 - OFFSET) - 0.5
    df = _bars(
        [
            (100, 100, 100, 100),
            (100, 101, entry_low, 100),
            (100, 100, 94, 95),  # 損切り水準95を割る
        ]
    )
    # 損切りのあとに同じシグナルで建て直さないよう、2本目以降は0にしておく
    result = run_backtest(
        df, _Scripted([1.0, 0.0, 0.0], stop=95.0), GMO_EXCHANGE, _maker_config()
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.reason == "stop_loss"

    implied = 1.0 - trade.exit_price / 95.0
    assert implied == pytest.approx(GMO_EXCHANGE.cost_rate(OrderType.TAKER))
    assert implied > GMO_EXCHANGE.cost_rate(OrderType.MAKER)


# ---------------------------------------------------------------------------
# 逆選択
# ---------------------------------------------------------------------------


def test_adverse_selection_appears_without_being_modelled():
    """約定した機会のほうが、取り逃した機会より**悪い**こと。

    買い指値が約定するのは価格が下げてきたとき。
    つまり上げていく機会ほど買えない。

    これは係数を置いて表現したものではない。
    正直に約定判定した結果として出てくる。**打ち消していないことの確認。**
    """
    df = make_synthetic_ohlcv(20_000, 1, "intraday", session_bars=24, beta=1.0)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    df = df.set_index("timestamp")

    signal = IntradayMomentum(stop_atr=None).generate(df)["direction"].to_numpy()
    o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
    model = MakerFill(offset=OFFSET)

    filled, missed = [], []
    for i in range(len(df) - 1):
        if signal[i] <= 0:
            continue
        j = i + 1
        bucket = filled if model.fills(Side.LONG, o[j], h[j], l[j]) else missed
        bucket.append(c[j] / o[j] - 1.0)

    assert len(missed) > 30, "取り逃した機会が少なすぎて比較にならない"
    assert np.mean(filled) < np.mean(missed), (
        f"約定した機会 {np.mean(filled) * 100:+.3f}% / "
        f"取り逃した機会 {np.mean(missed) * 100:+.3f}%"
    )


def test_fill_modelling_removes_the_illusory_maker_advantage():
    """「必ず約定する」前提が作っていた優位性が、判定を入れると消えること。

    成行では取れない弱さの信号（beta=0.2）で、
    必ず約定する前提だけがプラスを出す。
    """
    df = make_synthetic_ohlcv(20_000, 1, "intraday", session_bars=24, beta=0.2)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    df = df.set_index("timestamp")
    strategy = IntradayMomentum(stop_atr=None)

    assumed = evaluate(
        run_backtest(
            df,
            strategy,
            GMO_EXCHANGE,
            BacktestConfig(initial_capital=300_000.0, order_type=OrderType.MAKER),
        )
    ).total_return
    modelled = evaluate(
        run_backtest(
            df,
            strategy,
            GMO_EXCHANGE,
            BacktestConfig(
                initial_capital=300_000.0,
                order_type=OrderType.MAKER,
                maker_fill=MakerFill(offset=OFFSET),
            ),
        )
    ).total_return

    assert assumed > 0 > modelled, f"必ず約定 {assumed:+.3f} / 約定判定 {modelled:+.3f}"


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------


def test_maker_without_a_fill_model_is_warned_about():
    df = _bars([(100, 101, 99, 100)] * 5)
    result = run_backtest(
        df,
        _Scripted([1.0] * 5),
        GMO_EXCHANGE,
        BacktestConfig(initial_capital=1_000_000.0, order_type=OrderType.MAKER),
    )
    assert any("並べたら必ず約定する" in w for w in result.warnings)


def test_fill_model_requires_maker_order_type():
    with pytest.raises(ValueError, match="MAKER"):
        BacktestConfig(order_type=OrderType.TAKER, maker_fill=MakerFill())


def test_zero_offset_is_rejected():
    """始値ちょうどの指値は必ず約定してしまうので、設定として認めない。

    始値は必ず [安値, 高値] の内側にあるため、判定が退化する。
    """
    with pytest.raises(ValueError, match="offset"):
        MakerFill(offset=0.0)
    with pytest.raises(ValueError, match="offset"):
        MakerFill(offset=0.20)
