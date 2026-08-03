"""銘柄横断の検定。

## なぜこれが「別の仮説」なのか

これまで測ってきたのは、**1つの資産の価格履歴から、その資産の将来を当てる**
という形だった。EMAクロスも、RSIも、日中モメンタムもすべてそうで、
実データではどれも優位性がなかった。自己相関はどの時間軸でもゼロだった。

ここで使う情報源は違う。**他の銘柄の値動き**を使う。

Guo, Sang, Tu & Wang（*Journal of Economic Dynamics and Control*, 2024）は、
ある暗号資産の将来リターンが**他の暗号資産の過去リターン**で予測できることを報告した。
機構は「共通ショック＋限定的注意による情報伝播の遅れ」とされる。

## 信号と実装を分けて測る

実装（何を買うか、どう約定させるか、コストはいくらか）を考える前に、
**信号がそもそも存在するか**を測る。順番を逆にすると、
実装の巧拙と信号の有無が混ざって判別できなくなる。

そのため、この module の中心は「上位群と下位群のリターン差」（spread）になる。
これは資金も執行も要らない、純粋な予測力の測定になる。

## ベータとの分離が要る

暗号資産の横断モメンタムには落とし穴がある。
**上昇率の高い銘柄は、たいていベータの高い銘柄**である。
上げ相場で上位群を買えば勝つが、それは予測力ではなく市場感応度でしかない。

だからこの module は必ず3つを並べて出す。
  - 上位群のリターン
  - 全銘柄等加重（＝市場）のリターン
  - **上位群 − 下位群**（市場の動きが相殺され、予測力だけが残る）

3つ目が本体になる。1つ目だけを見て判断してはいけない。

## 生存バイアス

いま上場している銘柄だけを集めると、**途中で消えた銘柄が抜ける**。
消えるのはたいてい値下がりした銘柄なので、成績は上振れする。
このバイアスは、現在の上場銘柄リストからデータを取る限り避けられない。
結果を読むときに必ず割り引くこと。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class CrossSectionResult:
    """横断検定の結果。"""

    #: リバランス期ごとの、上位群・下位群・市場のリターン
    top: pd.Series
    bottom: pd.Series
    market: pd.Series
    #: 期ごとの銘柄数
    universe_size: pd.Series
    lookback: int
    holding: int
    n_groups: int
    #: 1期あたりの売買回転率（0〜2）
    turnover: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    @property
    def spread(self) -> pd.Series:
        """上位群 − 下位群。**市場の動きが相殺され、予測力だけが残る。**"""
        return self.top - self.bottom

    @property
    def excess(self) -> pd.Series:
        """上位群 − 市場。ベータが完全には抜けない点に注意。"""
        return self.top - self.market

    def _t_stat(self, x: pd.Series) -> float:
        x = x.dropna()
        if len(x) < 3 or x.std(ddof=1) == 0:
            return float("nan")
        return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))

    def summary(self, periods_per_year: float | None = None) -> str:
        if periods_per_year is None:
            periods_per_year = 365.0 / self.holding

        lines = [
            f"銘柄横断の検定（ルックバック {self.lookback}日 / 保有 {self.holding}日 / "
            f"{self.n_groups}分位）",
            "",
            f"  期間数     : {len(self.spread.dropna())}",
            f"  銘柄数     : 中央値 {self.universe_size.median():.0f} "
            f"（{self.universe_size.min():.0f}〜{self.universe_size.max():.0f}）",
            "",
        ]
        for label, series in (
            ("上位群", self.top),
            ("下位群", self.bottom),
            ("市場（等加重）", self.market),
            ("上位 − 下位  ★", self.spread),
            ("上位 − 市場", self.excess),
        ):
            s = series.dropna()
            if s.empty:
                continue
            ann = s.mean() * periods_per_year
            vol = s.std(ddof=1) * np.sqrt(periods_per_year)
            t = self._t_stat(series)
            lines.append(
                f"  {label:<14} 1期 {s.mean() * 100:+7.3f}%  "
                f"年率 {ann * 100:+8.1f}%  シャープ {ann / vol if vol else float('nan'):5.2f}  "
                f"t = {t:+5.2f}"
            )

        if not self.turnover.empty:
            lines += [
                "",
                f"  売買回転率 : 1期あたり {self.turnover.mean():.2f}"
                f"（片道。1.0なら毎回全入れ替え）",
            ]
        return "\n".join(lines)


@dataclass
class RandomGroupNull:
    """順位づけを壊した対照の結果。"""

    observed_spread: float
    null_spreads: np.ndarray

    @property
    def percentile(self) -> float:
        return float((self.null_spreads < self.observed_spread).mean() * 100)

    def summary(self) -> str:
        n = len(self.null_spreads)
        lines = [
            "無作為割当の対照（順位づけだけを壊す）",
            "",
            f"  試行回数     : {n} 回",
            f"  実際の spread: {self.observed_spread * 100:+.3f} %/期",
            f"  無作為の場合 : 中央値 {np.median(self.null_spreads) * 100:+.3f} % "
            f"（{np.percentile(self.null_spreads, 5) * 100:+.3f} 〜 "
            f"{np.percentile(self.null_spreads, 95) * 100:+.3f} %）",
            f"  → 上位 {100 - self.percentile:.1f} %",
            "",
        ]
        if self.percentile >= 95:
            lines.append(
                "  → 無作為に分けたのでは再現しません。**順位づけに意味があります。**"
            )
        else:
            lines.append(
                "  → **銘柄を無作為に2群へ分けても、同じくらいの差が出ます。**"
                "この差は順位づけの予測力では説明できません。"
            )
        return "\n".join(lines)


def random_group_null(
    panel: pd.DataFrame,
    lookback: int = 7,
    holding: int = 7,
    n_groups: int = 5,
    min_universe: int = 10,
    n_runs: int = 200,
    seed: int = 0,
) -> RandomGroupNull:
    """順位づけの代わりに、銘柄を無作為に分けたときの spread を集める。

    ## なぜ理論的な t 値だけでは足りないか

    暗号資産のリターンは、銘柄間で強く相関し、分散も期間ごとに大きく変わる。
    独立同分布を前提にした t 検定は、この状況で有意になりやすい。

    無作為割当なら、**銘柄の相関も、期間ごとの分散も、市場全体の動きも
    そのまま残る**。壊れるのは「過去のリターンで並べた」という一点だけになる。
    だから差が出れば、それは順位づけに由来する。

    ローテーション検定（validate.rotation_null）と同じ考え方を、
    時間方向ではなく銘柄方向に適用したものになる。
    """
    if n_runs < 20:
        raise ValueError("回数が少なすぎます。20回以上にしてください")

    observed = cross_sectional_test(
        panel, lookback=lookback, holding=holding,
        n_groups=n_groups, min_universe=min_universe,
    ).spread.mean()

    prices = panel.sort_index()
    n = len(prices)
    rng = np.random.default_rng(seed)
    spreads = []

    for _ in range(n_runs):
        diffs = []
        for t in range(lookback, n - holding, holding):
            past = prices.iloc[t] / prices.iloc[t - lookback] - 1.0
            future = prices.iloc[t + holding] / prices.iloc[t] - 1.0
            valid = past.notna() & future.notna() & np.isfinite(past) & np.isfinite(future)
            future = future[valid]
            if len(future) < min_universe:
                continue
            k = max(1, len(future) // n_groups)
            # 過去リターンではなく、くじ引きで分ける
            picked = rng.permutation(len(future))
            diffs.append(
                float(future.iloc[picked[:k]].mean() - future.iloc[picked[-k:]].mean())
            )
        if diffs:
            spreads.append(float(np.mean(diffs)))

    return RandomGroupNull(
        observed_spread=float(observed), null_spreads=np.array(spreads)
    )


def build_panel(frames: dict[str, pd.DataFrame], column: str = "close") -> pd.DataFrame:
    """銘柄ごとの OHLCV から、終値のパネル（行=日付、列=銘柄）を作る。

    上場前や欠損は NaN のままにする。**前方補完してはいけない。**
    存在しなかった価格を作ると、存在しなかった取引ができてしまう。
    """
    series = {}
    for name, df in frames.items():
        if column not in df.columns:
            raise ValueError(f"{name} に {column} 列がありません")
        s = df[column].astype(float)
        if not isinstance(s.index, pd.DatetimeIndex):
            raise ValueError(f"{name} の index が DatetimeIndex ではありません")
        series[name] = s[~s.index.duplicated(keep="first")].sort_index()
    panel = pd.DataFrame(series).sort_index()
    return panel


def cross_sectional_test(
    panel: pd.DataFrame,
    lookback: int = 7,
    holding: int = 7,
    n_groups: int = 5,
    min_universe: int = 10,
    cost_per_side: float = 0.0,
    skip: int = 0,
) -> CrossSectionResult:
    """過去 lookback 期のリターンで銘柄を並べ、上位群と下位群を作る。

    Parameters
    ----------
    panel:
        行=日付、列=銘柄の終値。NaN は「その時点で取引できない」を意味する
    lookback:
        何期分のリターンで順位をつけるか
    holding:
        何期ごとに入れ替えるか
    n_groups:
        何分位に分けるか（5なら上位20%と下位20%）
    min_universe:
        この銘柄数を下回る時点は使わない。
        少なすぎる分位はノイズしか出さない
    cost_per_side:
        片道の取引コスト（率）。回転率に掛けて差し引く
    skip:
        順位づけの終点と保有開始の間に空ける期数。
        1にすると、直近1期の値動きを順位に使わない。
        **短期反転（買った直後に反転する動き）と混ざるのを避けるため**

    Notes
    -----
    順位づけに使うのは t 時点までに確定したリターンだけで、
    保有は t+1 以降になる。先読みは構造的に起きない。
    """
    if lookback < 1 or holding < 1:
        raise ValueError("lookback と holding は1以上である必要があります")
    if n_groups < 2:
        raise ValueError("n_groups は2以上である必要があります")
    if min_universe < n_groups * 2:
        raise ValueError(
            f"min_universe は n_groups の2倍（{n_groups * 2}）以上にしてください。"
            "各分位に最低2銘柄ないと、1銘柄の値動きが分位の成績になります"
        )

    prices = panel.sort_index()
    n = len(prices)
    tops, bottoms, markets, sizes, turns, stamps = [], [], [], [], [], []
    prev_top: set[str] = set()

    start = lookback + skip
    for t in range(start, n - holding, holding):
        rank_end = t - skip
        rank_start = rank_end - lookback
        if rank_start < 0:
            continue

        past = prices.iloc[rank_end] / prices.iloc[rank_start] - 1.0
        future = prices.iloc[t + holding] / prices.iloc[t] - 1.0

        # 順位づけにも保有にも使えるのは、両方の時点で価格がある銘柄だけ
        valid = past.notna() & future.notna() & np.isfinite(past) & np.isfinite(future)
        past, future = past[valid], future[valid]
        if len(past) < min_universe:
            continue

        k = max(1, len(past) // n_groups)
        order = past.sort_values(ascending=False)
        top_names = list(order.index[:k])
        bottom_names = list(order.index[-k:])

        tops.append(float(future[top_names].mean()))
        bottoms.append(float(future[bottom_names].mean()))
        markets.append(float(future.mean()))
        sizes.append(len(past))
        stamps.append(prices.index[t])

        current = set(top_names)
        turns.append(len(current - prev_top) / max(len(current), 1))
        prev_top = current

    idx = pd.DatetimeIndex(stamps)
    top = pd.Series(tops, index=idx)
    bottom = pd.Series(bottoms, index=idx)
    turnover = pd.Series(turns, index=idx)

    if cost_per_side > 0:
        # 入れ替えた銘柄ぶんだけ、買いと売りの両方でコストがかかる
        drag = turnover * cost_per_side * 2
        top = top - drag
        bottom = bottom + drag  # 下位群を売る側も同じだけ払う

    return CrossSectionResult(
        top=top,
        bottom=bottom,
        market=pd.Series(markets, index=idx),
        universe_size=pd.Series(sizes, index=idx),
        lookback=lookback,
        holding=holding,
        n_groups=n_groups,
        turnover=turnover,
    )
