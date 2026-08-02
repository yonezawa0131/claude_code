"""戦略の実装。

ここにある戦略は「動くお手本」であって、「儲かる戦略」ではない。
優位性があるかどうかは、バックテストで測って初めて分かる。
測る前から効くと分かっている指標があるなら、そもそも公開されていない。

新しい戦略を書いたら、必ず validate.check_causality() を通すこと。
未来を1行でも覗いていたら、その戦略のバックテスト結果は無意味になる。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind


def _empty_signals(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "direction": np.zeros(len(index), dtype=float),
            "stop_loss": np.full(len(index), np.nan),
            "take_profit": np.full(len(index), np.nan),
        },
        index=index,
    )


@dataclass
class BuyAndHold:
    """買って持ち続けるだけ。すべての戦略が超えるべき基準線。

    これを下回る戦略は、手数料とリスクと手間を増やして
    リターンを減らしているだけなので、採用してはいけない。
    """

    name: str = "買い持ち"

    def warmup(self) -> int:
        return 1

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        sig = _empty_signals(df.index)
        sig["direction"] = 1.0
        return sig


@dataclass
class RandomEntry:
    """コイン投げでポジションを決める対照群。

    **これが利益を出したらエンジンのバグを疑うこと。**
    コストを引いた後では、必ず負けるはずの戦略。
    合成データの random レジームと組み合わせて、
    エンジンが幻の利益を作っていないかを検査するために使う。
    """

    seed: int = 0
    flip_probability: float = 0.05
    name: str = "ランダム（対照群）"

    def warmup(self) -> int:
        return 1

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        sig = _empty_signals(df.index)
        direction = np.zeros(len(df), dtype=float)
        current = 0.0
        for i in range(len(df)):
            if rng.random() < self.flip_probability:
                current = float(rng.choice([-1.0, 0.0, 1.0]))
            direction[i] = current
        sig["direction"] = direction
        return sig


@dataclass
class EmaCrossATR:
    """移動平均のクロスで方向を決め、損切りをATRで動的に置く戦略。

    「動的に損切りを精査して柔軟に対応する」という発想を、
    実装可能な形に落とすとこうなる。

    - 速いEMAが遅いEMAを上抜けたらロング、下抜けたらショート
    - 損切りは終値から ATR の stop_atr 倍だけ離れた位置に置く
    - 損切りは有利な方向にだけ動かす（トレーリング）。
      不利な方向に動かすのは「損切りをずらす」ことであり、
      これをやると損失が青天井になる

    ATR を使う理由は、相場のボラティリティに損切り幅を合わせるため。
    固定幅だと、静かな相場では遠すぎ、荒れた相場では近すぎて
    ノイズで刈られる。
    """

    fast: int = 12
    slow: int = 48
    atr_period: int = 14
    stop_atr: float = 2.0
    #: 利確をATRの何倍に置くか。None なら利確しない（損切りとシグナルのみ）
    target_atr: float | None = 3.0
    #: ショートを出すか
    allow_short: bool = False
    name: str = "EMAクロス + ATR損切り"

    def warmup(self) -> int:
        return max(self.slow, self.atr_period) + 1

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        fast_ema = ind.ema(close, self.fast)
        slow_ema = ind.ema(close, self.slow)
        atr = ind.atr(df["high"], df["low"], close, self.atr_period)

        direction = np.where(fast_ema > slow_ema, 1.0, -1.0 if self.allow_short else 0.0)
        direction = np.where(fast_ema.isna() | slow_ema.isna(), 0.0, direction)

        sig = _empty_signals(df.index)
        sig["direction"] = direction

        # 損切り: ロングなら終値の下、ショートなら終値の上
        stop_dist = atr * self.stop_atr
        sig["stop_loss"] = np.where(
            direction > 0,
            close - stop_dist,
            np.where(direction < 0, close + stop_dist, np.nan),
        )

        if self.target_atr is not None:
            target_dist = atr * self.target_atr
            sig["take_profit"] = np.where(
                direction > 0,
                close + target_dist,
                np.where(direction < 0, close - target_dist, np.nan),
            )

        return sig


@dataclass
class RsiMeanReversion:
    """RSIの行き過ぎで逆張りする戦略。

    レンジ相場では機能しやすく、トレンド相場では逆行し続けて損失が伸びる。
    合成データの trend / range レジームで挙動が反転するはずで、
    それが確認できればエンジンが相場付きを正しく反映している証拠になる。
    """

    rsi_period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    exit_level: float = 50.0
    atr_period: int = 14
    stop_atr: float = 2.5
    allow_short: bool = False
    name: str = "RSI逆張り"

    def warmup(self) -> int:
        return max(self.rsi_period, self.atr_period) + 1

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        r = ind.rsi(close, self.rsi_period)
        atr = ind.atr(df["high"], df["low"], close, self.atr_period)

        direction = np.zeros(len(df), dtype=float)
        current = 0.0
        r_values = r.to_numpy(dtype=float)
        for i in range(len(df)):
            v = r_values[i]
            if np.isnan(v):
                direction[i] = 0.0
                continue
            if current == 0.0:
                if v <= self.oversold:
                    current = 1.0
                elif v >= self.overbought and self.allow_short:
                    current = -1.0
            elif current > 0 and v >= self.exit_level:
                current = 0.0
            elif current < 0 and v <= self.exit_level:
                current = 0.0
            direction[i] = current

        sig = _empty_signals(df.index)
        sig["direction"] = direction
        stop_dist = atr * self.stop_atr
        sig["stop_loss"] = np.where(
            direction > 0,
            close - stop_dist,
            np.where(direction < 0, close + stop_dist, np.nan),
        )
        return sig


STRATEGIES: dict[str, type] = {
    "buy_and_hold": BuyAndHold,
    "random": RandomEntry,
    "ema_atr": EmaCrossATR,
    "rsi_reversion": RsiMeanReversion,
}
