"""テクニカル指標。

すべて **因果的（causal）** に実装してある。
つまり時刻 i の値は 0..i のデータだけから決まり、未来を参照しない。
rolling / ewm はいずれも過去方向にしか窓を取らないのでこの性質を満たすが、
新しい指標を足すときは center=True や shift(-n) を絶対に使わないこと。

指標に予測力があるかどうかは、ここでは主張しない。
それを測るのがバックテストの仕事であって、指標そのものは単なる変換にすぎない。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """単純移動平均。"""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移動平均。adjust=False で逐次更新型にする（実運用と同じ計算）。"""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI（Wilder方式）。

    単純平均ではなく Wilder の平滑化（alpha = 1/period）を使う。
    これが本来の定義で、単純移動平均で代用すると値がずれる。
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    # 下落が一度もない区間では avg_loss が 0 になり、RSI は 100 に収束する
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.where(avg_loss != 0.0, 100.0).where(avg_gain.notna())


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """真の値幅。前日終値とのギャップを含めた変動幅。"""
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """ATR（Wilder方式）。損切り幅を相場のボラティリティに合わせるために使う。

    固定幅（例: 常に1%）の損切りは、静かな相場では広すぎ、
    荒れた相場では狭すぎる。ATRの倍数で置くと、その両方を避けられる。
    """
    return true_range(high, low, close).ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD。戻り値は (MACD線, シグナル線, ヒストグラム)。"""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return macd_line, signal_line, macd_line - signal_line


def bollinger(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ボリンジャーバンド。戻り値は (中心線, 上限, 下限)。"""
    mid = sma(close, period)
    sd = close.rolling(window=period, min_periods=period).std(ddof=0)
    return mid, mid + num_std * sd, mid - num_std * sd


def realized_volatility(close: pd.Series, period: int = 20) -> pd.Series:
    """対数リターンの標準偏差。バーあたりのボラティリティ。"""
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(window=period, min_periods=period).std(ddof=0)
