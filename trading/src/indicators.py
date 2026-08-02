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


# ---------------------------------------------------------------------------
# 追加の指標
#
# いずれも OHLCV だけから計算でき、定義が一意に決まるもの（棚卸しのA群）。
# 因果性は tests/test_indicators_extra.py で検査している。
# ---------------------------------------------------------------------------


def directional_movement(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ADX / +DI / -DI（Wilder方式）。戻り値は (ADX, +DI, -DI)。

    ADXは「トレンドがあるかないか」を測る指標で、方向は示さない。
    トレンド追随戦略をレンジ相場で止めるフィルタとして使うのが本来の用途。

    合成データの検証では、レンジ相場でEMAクロス戦略が -94% になった。
    ADXでレンジを弾ければ、その損失の一部は避けられるはずで、
    これは実データで検証する価値がある。
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index
    )

    alpha = 1 / period
    atr_ = true_range(high, low, close).ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr_

    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denom
    adx = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    return adx, plus_di, minus_di


def donchian(high: pd.Series, low: pd.Series, period: int = 20) -> tuple[pd.Series, pd.Series]:
    """ドンチャンチャネル。戻り値は (上限, 下限)。

    **現在のバーを含めない**（shift(1)）のが要点。
    含めてしまうと、そのバーの高値は必ずチャネル上限と等しくなり、
    「上抜けた」という判定が成立しなくなる。
    """
    upper = high.rolling(window=period, min_periods=period).max().shift(1)
    lower = low.rolling(window=period, min_periods=period).min().shift(1)
    return upper, lower


def pivot_points(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """ピボットポイント。戻り値は (P, R1, S1, R2, S2)。

    前のバーの高値・安値・終値だけから算術的に決まるので、
    水準系の手法では珍しく**引き方に判断が入らない**。
    サポート/レジスタンスを機械的に扱いたい場合の出発点になる。
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    p = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * p - prev_low
    s1 = 2 * p - prev_high
    r2 = p + (prev_high - prev_low)
    s2 = p - (prev_high - prev_low)
    return p, r1, s1, r2, s2


def ichimoku(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> dict[str, pd.Series]:
    """一目均衡表。

    「難解」と言われるが、計算そのものは完全に機械的で定義は一意。

    先行スパンは通常「未来にずらして描画」されるため先読みに見えるが、
    **時刻 t に表示される雲は t-26 のデータから計算された値**であり、
    ここでは shift(+displacement) として実装している。これは過去参照なので因果的。

    遅行スパンも同様で、「時刻 t の終値が t-26 の終値を上回っているか」
    という比較として扱えば因果的になる。描画上のずらしと計算を混同しないこと。
    """

    def midpoint(period: int) -> pd.Series:
        highest = high.rolling(window=period, min_periods=period).max()
        lowest = low.rolling(window=period, min_periods=period).min()
        return (highest + lowest) / 2

    tenkan = midpoint(tenkan_period)
    kijun = midpoint(kijun_period)

    return {
        "tenkan": tenkan,
        "kijun": kijun,
        # 時刻 t の雲は displacement 本前の値から作られる（過去参照＝因果的）
        "senkou_a": ((tenkan + kijun) / 2).shift(displacement),
        "senkou_b": midpoint(senkou_b_period).shift(displacement),
        # 「現在の終値が displacement 本前の終値を上回るか」の比較用
        "chikou_reference": close.shift(displacement),
    }
