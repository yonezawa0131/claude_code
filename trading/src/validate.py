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


@dataclass
class WalkForwardResult:
    """ウォークフォワード検証の結果。"""

    windows: list[tuple[pd.Timestamp, pd.Timestamp, Report]]

    def summary(self) -> str:
        lines = ["ウォークフォワード検証", ""]
        returns = []
        for start, end, rep in self.windows:
            returns.append(rep.total_return)
            mark = "○" if rep.excess_over_buy_hold > 0 else "×"
            lines.append(
                f"{mark} {start:%Y-%m-%d} 〜 {end:%Y-%m-%d}: "
                f"{rep.total_return * 100:+7.2f}% "
                f"(買い持ち {rep.buy_hold_return * 100:+7.2f}%, "
                f"{rep.trade_count} 回)"
            )
        if returns:
            arr = np.array(returns)
            positive = int((arr > 0).sum())
            beat = sum(1 for _, _, r in self.windows if r.excess_over_buy_hold > 0)
            lines += [
                "",
                f"勝ち越した期間 : {positive} / {len(arr)}",
                f"買い持ちに勝った期間: {beat} / {len(arr)}",
                f"期間リターンの平均 : {arr.mean() * 100:+.2f} %",
                f"期間リターンの標準偏差 : {arr.std(ddof=1) * 100 if len(arr) > 1 else float('nan'):.2f} %",
            ]
            if beat <= len(arr) / 2:
                lines.append("")
                lines.append(
                    "→ 過半の期間で買い持ちに勝てていません。"
                    "この戦略を採用する根拠は現時点でありません。"
                )
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
