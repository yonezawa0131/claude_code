"""検証ツール。

バックテストで一番怖いのは「動くけれど嘘をついている」状態なので、
嘘を機械的に見つけるための道具をここに置く。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, Strategy, run_backtest
from .costs import CostModel
from .metrics import Report, evaluate


@dataclass
class CausalityViolation:
    """先読みが見つかった箇所。"""

    cut: int
    column: str
    position: int
    full_value: float
    truncated_value: float

    def __str__(self) -> str:
        return (
            f"{self.cut} 本目までのデータで計算したとき、"
            f"{self.position} 本目の {self.column} が変わりました "
            f"（全データ: {self.full_value} / 打ち切り: {self.truncated_value}）"
        )


def check_causality(
    strategy: Strategy,
    df: pd.DataFrame,
    cuts: int = 5,
    atol: float = 1e-8,
) -> list[CausalityViolation]:
    """戦略が未来を参照していないかを検査する。

    原理は単純で、データを途中で打ち切って計算し直しても、
    重なっている部分の出力が変わらないことを確かめる。

    変わってしまうなら、その戦略は「後から来るデータ」を使って
    過去の判断を作っていることになる。実運用ではそのデータは
    まだ存在しないので、そのバックテスト結果は再現できない。

    戻り値が空リストなら因果的。1件でもあれば、その戦略は使えない。

    典型的な原因:
      - rolling(center=True) を使っている
      - shift(-n) で未来をずらしてきている
      - 全期間の平均・標準偏差・最大最小で正規化している
      - fillna(method="bfill") で後ろから埋めている
    """
    violations: list[CausalityViolation] = []
    full = strategy.generate(df)

    n = len(df)
    warmup = max(strategy.warmup(), 1)
    if n <= warmup + 2:
        raise ValueError("検査に十分なバー数がありません")

    # 打ち切り位置を等間隔に取る
    positions = np.linspace(warmup + 2, n - 1, num=cuts, dtype=int)

    for cut in sorted(set(int(p) for p in positions)):
        truncated = strategy.generate(df.iloc[:cut])
        for column in ("direction", "stop_loss", "take_profit"):
            a = full[column].to_numpy(dtype=float)[:cut]
            b = truncated[column].to_numpy(dtype=float)
            # 両方 NaN は一致とみなす
            both_nan = np.isnan(a) & np.isnan(b)
            diff = ~both_nan & ~np.isclose(a, b, atol=atol, equal_nan=False)
            for idx in np.flatnonzero(diff):
                violations.append(
                    CausalityViolation(
                        cut=cut,
                        column=column,
                        position=int(idx),
                        full_value=float(a[idx]),
                        truncated_value=float(b[idx]),
                    )
                )
                break  # 1つの列につき最初の1件だけ報告すれば十分
    return violations


#: 減衰とみなす標準化スコアの閾値。
#: 合成データ（優位性が一定 vs 線形に消滅、各10シード）で測ったところ、
#: 一定のときは [-0.95, +1.43]、消滅するときは [-1.75, -1.09] に分かれた。
#: -1.0 は両者のちょうど境目で、**余裕はほとんどない**。
#: この値だけで採否を決めず、必ず期間ごとの並びも見ること。
DECAY_Z_THRESHOLD = -1.0

#: この本数を下回る期間があると、期間ごとの成績がノイズに埋もれて
#: 傾向を読めない（metrics.evaluate() の警告と同じ基準）
MIN_TRADES_PER_WINDOW = 30


@dataclass
class WalkForwardResult:
    """ウォークフォワード検証の結果。

    **勝った期間の数だけを見てはいけない。** 数は順番を捨ててしまう。

    優位性が期間の後半にかけて消えていくデータで測ると、
    6分割のうち4期間はプラスのまま残る（10シード中9回）。
    「4/6で勝ち越し」と読めば合格に見えるが、実際には
    最後の2期間で負けていて、**その戦略はもう死んでいる**。

    順番を見る統計量を2つ持たせてある。
      - decay_z : 後半の平均が前半よりどれだけ悪いか（標準偏差で割った値）
      - 最終期間が負で、全体が正か（＝過去の利益が現在の損失を隠していないか）
    """

    windows: list[tuple[pd.Timestamp, pd.Timestamp, Report]]

    @property
    def returns(self) -> np.ndarray:
        return np.array([rep.total_return for _, _, rep in self.windows])

    @property
    def decay(self) -> float:
        """後半の平均リターン − 前半の平均リターン。

        マイナスなら、時間が経つにつれて成績が落ちている。
        """
        arr = self.returns
        if len(arr) < 4:
            return float("nan")
        half = len(arr) // 2
        return float(arr[half:].mean() - arr[:half].mean())

    @property
    def decay_z(self) -> float:
        """decay を期間リターンの標準偏差で割った値。

        効果の大きさに依存しない形にするための標準化。
        リターンそのもので閾値を切ると、
        優位性が大きい戦略ほど誤検知しやすくなる。
        """
        arr = self.returns
        if len(arr) < 4:
            return float("nan")
        sd = arr.std(ddof=1)
        if sd == 0 or np.isnan(sd):
            return float("nan")
        return self.decay / sd

    def warnings(self) -> list[str]:
        """採用してはいけない兆候を並べる。"""
        arr = self.returns
        out: list[str] = []
        if len(arr) == 0:
            return ["検証できた期間がありません。"]

        beat = sum(1 for _, _, r in self.windows if r.excess_over_buy_hold > 0)
        if beat <= len(arr) / 2:
            out.append(
                "過半の期間で買い持ちに勝てていません。"
                "この戦略を採用する根拠は現時点でありません。"
            )

        z = self.decay_z
        if not np.isnan(z) and z < DECAY_Z_THRESHOLD:
            out.append(
                f"後半の成績が前半より落ちています（標準化スコア {z:+.2f}）。"
                "優位性が失われつつある可能性があります。"
                "全期間の平均は、過去の利益が現在の損失を隠して作られたものかもしれません。"
            )

        if len(arr) >= 2 and arr[-1] < 0 < arr.mean():
            out.append(
                f"全期間の平均はプラスですが、最新の期間はマイナスです"
                f"（{arr[-1] * 100:+.2f}%）。"
                "**測っているのは過去の相場で、今の相場ではありません。**"
            )

        thin = [rep.trade_count for _, _, rep in self.windows if rep.trade_count < MIN_TRADES_PER_WINDOW]
        if thin:
            out.append(
                f"取引が {MIN_TRADES_PER_WINDOW} 回に満たない期間が {len(thin)} 個あります"
                f"（最小 {min(thin)} 回）。"
                "期間ごとの成績がノイズに埋もれ、傾向を読めません。"
                "期間を減らすか、データを増やしてください。"
            )
        return out

    def summary(self) -> str:
        lines = ["ウォークフォワード検証", ""]
        for start, end, rep in self.windows:
            mark = "○" if rep.excess_over_buy_hold > 0 else "×"
            lines.append(
                f"{mark} {start:%Y-%m-%d} 〜 {end:%Y-%m-%d}: "
                f"{rep.total_return * 100:+7.2f}% "
                f"(買い持ち {rep.buy_hold_return * 100:+7.2f}%, "
                f"{rep.trade_count} 回)"
            )

        arr = self.returns
        if len(arr):
            positive = int((arr > 0).sum())
            beat = sum(1 for _, _, r in self.windows if r.excess_over_buy_hold > 0)
            sd = arr.std(ddof=1) if len(arr) > 1 else float("nan")
            lines += [
                "",
                f"勝ち越した期間 : {positive} / {len(arr)}",
                f"買い持ちに勝った期間: {beat} / {len(arr)}",
                f"期間リターンの平均 : {arr.mean() * 100:+.2f} %",
                f"期間リターンの標準偏差 : {sd * 100:.2f} %",
            ]
            if not np.isnan(self.decay):
                lines += [
                    "",
                    f"後半 − 前半 : {self.decay * 100:+.2f} pt"
                    f"（標準化 {self.decay_z:+.2f}）",
                    "  ※ 勝った期間の数は順番を捨てます。"
                    "優位性が消えていく戦略でも、前半の貯金で数だけは残ります",
                ]

        issues = self.warnings()
        if issues:
            lines.append("")
            lines.extend(f"→ {w}" for w in issues)
        return "\n".join(lines)


def walk_forward(
    df: pd.DataFrame,
    strategy: Strategy,
    cost: CostModel,
    config: BacktestConfig | None = None,
    n_windows: int = 5,
) -> WalkForwardResult:
    """期間を分割して、それぞれで独立に成績を測る。

    全期間を1本のバックテストで見ると、
    「たまたま良かった1ヶ月」が全体を持ち上げていても気づけない。
    期間を分けて、どの期間でも通用するかを見る。

    どこか1つの期間だけ突出していて他が横ばい以下なら、
    それは戦略の実力ではなく、その期間の相場付きに合っただけの可能性が高い。
    """
    if n_windows < 2:
        raise ValueError("n_windows は2以上にしてください")

    bounds = np.linspace(0, len(df), num=n_windows + 1, dtype=int)
    windows = []
    for i in range(n_windows):
        chunk = df.iloc[bounds[i] : bounds[i + 1]]
        if len(chunk) <= strategy.warmup() + 2:
            continue
        result = run_backtest(chunk, strategy, cost, config)
        windows.append((chunk.index[0], chunk.index[-1], evaluate(result)))
    return WalkForwardResult(windows=windows)


@dataclass
class _FixedSignals:
    """あらかじめ計算したシグナルをそのまま返すだけの戦略。

    ローテーション検定で、ずらした後のシグナルを流すために使う。
    """

    signals: pd.DataFrame
    warmup_bars: int
    name: str = "固定シグナル"

    def warmup(self) -> int:
        return self.warmup_bars

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.signals


@dataclass
class RotationNullResult:
    """ローテーション検定の結果。"""

    strategy_name: str
    observed_return: float
    observed_sharpe: float
    null_returns: np.ndarray
    null_sharpes: np.ndarray

    @property
    def return_percentile(self) -> float:
        return float((self.null_returns < self.observed_return).mean() * 100)

    @property
    def sharpe_percentile(self) -> float:
        return float((self.null_sharpes < self.observed_sharpe).mean() * 100)

    def summary(self) -> str:
        n = len(self.null_returns)
        lines = [
            "ローテーション検定（タイミングだけを壊した対照）",
            "",
            f"  戦略: {self.strategy_name}",
            f"  ずらした回数: {n} 回",
            "",
            f"  実際のリターン : {self.observed_return * 100:+.2f} %",
            f"  ずらした場合   : 中央値 {np.median(self.null_returns) * 100:+.2f} % "
            f"（{np.percentile(self.null_returns, 5) * 100:+.1f} 〜 "
            f"{np.percentile(self.null_returns, 95) * 100:+.1f} %）",
            f"  → 上位 {100 - self.return_percentile:.1f} %",
            "",
            f"  実際のシャープ : {self.observed_sharpe:.2f}",
            f"  ずらした場合   : 中央値 {np.median(self.null_sharpes):.2f} "
            f"（{np.percentile(self.null_sharpes, 5):.2f} 〜 "
            f"{np.percentile(self.null_sharpes, 95):.2f}）",
            f"  → 上位 {100 - self.sharpe_percentile:.1f} %",
            "",
        ]
        if self.return_percentile >= 95:
            lines.append(
                "  → タイミングをずらすと再現しません。"
                "**この相場でこのタイミングだったこと**に意味があった可能性があります。"
            )
        else:
            lines.append(
                "  → **同じ売買パターンをでたらめな時点に置いても、同じくらいの成績が出ます。**"
                "この成績はタイミングの良さでは説明できません。"
            )
        return "\n".join(lines)


def rotation_null(
    df: pd.DataFrame,
    strategy: Strategy,
    cost: CostModel,
    config: BacktestConfig | None = None,
    n_runs: int = 200,
    seed: int = 0,
) -> RotationNullResult:
    """戦略のポジション系列を時間方向にずらして、タイミングの優位性だけを消す。

    ## なぜ理論的な閾値だけでは足りないか

    `growth.expected_max_sharpe` は、リターンが独立同分布であることを前提にした
    理論値を返す。実際の価格系列にはトレンドも自己相関もあるので、
    **その相場だからこそ出た数字**を弾けない。

    実データで対照群（コイン投げ）が買い持ちに勝ったとき、
    それが「タイミングが良かった」のか「上げ相場に居合わせただけ」なのかは、
    理論値では区別できない。

    ## 何を壊し、何を残すか

    ポジション系列を丸ごと時間方向に回転させる。すると

      - **残る**: 取引回数、建玉の保有期間、市場に晒されている時間の割合、
        ロングとショートの比率、そしてこの相場そのもの
      - **壊れる**: 「いつ建てたか」だけ

    残ったものが同じなので、成績の差はタイミングだけに由来する。
    上げ相場に居合わせた効果は対照側にも同じだけ入るため、相殺される。

    損切り・利確は価格水準なので、そのままずらすと無意味になる。
    終値に対する比率に直してからずらし、ずらした先の終値に掛け直している。
    """
    if n_runs < 20:
        raise ValueError("回数が少なすぎます。20回以上にしてください")

    base = strategy.generate(df)
    close = df["close"].to_numpy(dtype=float)
    direction = base["direction"].to_numpy(dtype=float)
    # 価格水準ではなく「終値に対する比率」でずらす
    stop_ratio = base["stop_loss"].to_numpy(dtype=float) / close
    target_ratio = base["take_profit"].to_numpy(dtype=float) / close

    warm = max(strategy.warmup(), 1)
    name = getattr(strategy, "name", type(strategy).__name__)

    observed = evaluate(run_backtest(df, strategy, cost, config))

    n = len(df)
    # 端に寄ったずらし方は元の並びとほとんど同じになるので、十分内側から選ぶ
    candidates = np.arange(warm + 1, n - warm - 1)
    if len(candidates) < 10:
        raise ValueError(
            f"バー数 {n} に対してウォームアップ {warm} が大きく、"
            "ずらせる幅がほとんどありません。データを増やしてください"
        )
    rng = np.random.default_rng(seed)
    # ずらし幅の候補が要求回数より少ないときだけ重複を許す
    offsets = rng.choice(candidates, size=n_runs, replace=n_runs > len(candidates))

    returns, sharpes = [], []
    for offset in offsets:
        rotated = pd.DataFrame(
            {
                "direction": np.roll(direction, offset),
                "stop_loss": np.roll(stop_ratio, offset) * close,
                "take_profit": np.roll(target_ratio, offset) * close,
            },
            index=df.index,
        )
        report = evaluate(
            run_backtest(df, _FixedSignals(rotated, warm, name), cost, config)
        )
        returns.append(report.total_return)
        sharpes.append(report.sharpe)

    return RotationNullResult(
        strategy_name=name,
        observed_return=observed.total_return,
        observed_sharpe=observed.sharpe,
        null_returns=np.array(returns),
        null_sharpes=np.nan_to_num(np.array(sharpes), nan=0.0),
    )


def required_return_table(
    targets_yen_per_day: tuple[float, ...] = (500.0, 1_000.0, 3_000.0),
    capitals: tuple[float, ...] = (100_000.0, 300_000.0, 500_000.0, 1_000_000.0),
    trading_days_per_year: int = 250,
) -> str:
    """「1日いくら」を「元本に対する率」に翻訳した表を作る。

    1日500円という目標は、それ自体では難易度を表さない。
    元本10万円なら日次0.5%（年125%ペース）、
    元本100万円なら日次0.05%（年12.5%ペース）で、意味がまったく違う。
    """
    header = "元本".ljust(12) + "".join(
        f"{int(t):,}円/日".rjust(20) for t in targets_yen_per_day
    )
    lines = [header, "-" * len(header)]
    for cap in capitals:
        row = f"{int(cap):,}円".ljust(12)
        for target in targets_yen_per_day:
            daily = target / cap
            annual = daily * trading_days_per_year
            row += f"{daily * 100:6.3f}%/日 (年{annual * 100:5.0f}%)".rjust(20)
        lines.append(row)
    lines.append("")
    lines.append("※ 年率は単利換算（日次リターン × 250日）。複利ではない")
    return "\n".join(lines)
