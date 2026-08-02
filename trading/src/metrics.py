"""バックテスト結果の評価。

数字を良く見せないことを優先している。特に次の2点。

1. **買い持ちを必ず併記する。**
   戦略の成績だけを見ると、上げ相場ではどんな戦略も良く見える。
   同じ期間ただ持っていた場合と比べて初めて、その戦略に意味があるか分かる。

2. **取引回数とコスト総額を必ず出す。**
   「勝率60%」でも、コストが利益を食っていれば手取りはマイナスになる。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import BacktestResult, Side


def _periods_per_year(index: pd.DatetimeIndex) -> float:
    """バーの間隔から年間バー数を推定する。"""
    if len(index) < 2:
        return 365.0
    median_delta = pd.Series(index).diff().median()
    if pd.isna(median_delta) or median_delta.total_seconds() <= 0:
        return 365.0
    return (365.0 * 24 * 3600) / median_delta.total_seconds()


def max_drawdown(equity: pd.Series) -> float:
    """最大ドローダウン（率）。ピークからの最大下落幅。

    平均リターンより、この数字のほうが「続けられるか」を決める。
    50%落ちた時点で多くの人は降りる。
    """
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min())


def sharpe_ratio(equity: pd.Series, periods_per_year: float) -> float:
    """シャープレシオ（無リスク金利ゼロと仮定）。

    リターンのばらつきに対して、どれだけリターンを得たか。
    暗号資産のようにボラティリティが高い対象では、
    リターンの大きさより、この比率のほうが実力を反映しやすい。
    """
    returns = equity.pct_change().dropna()
    if len(returns) < 2:
        return float("nan")
    sd = returns.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return float("nan")
    return float(returns.mean() / sd * np.sqrt(periods_per_year))


@dataclass
class Report:
    """1回のバックテストの評価結果。"""

    strategy_name: str
    cost_model_name: str

    initial_capital: float
    final_equity: float
    total_return: float
    #: 買い持ちした場合の総リターン
    buy_hold_return: float
    #: 戦略が買い持ちをどれだけ上回ったか。マイナスなら負けている
    excess_over_buy_hold: float

    max_drawdown: float
    buy_hold_max_drawdown: float
    sharpe: float

    trade_count: int
    win_rate: float
    profit_factor: float
    total_cost_yen: float
    #: コストが総利益（グロス）の何割を食ったか
    cost_ratio_of_gross: float

    days: float
    yen_per_day: float

    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"戦略           : {self.strategy_name}",
            f"コストモデル   : {self.cost_model_name}",
            f"期間           : {self.days:.0f} 日",
            "",
            f"初期資金       : {self.initial_capital:,.0f} 円",
            f"最終資産       : {self.final_equity:,.0f} 円",
            f"総リターン     : {self.total_return * 100:+.2f} %",
            f"1日あたり      : {self.yen_per_day:+,.0f} 円",
            "",
            f"買い持ち       : {self.buy_hold_return * 100:+.2f} %",
            f"買い持きとの差 : {self.excess_over_buy_hold * 100:+.2f} %"
            + ("  ← 買い持ちに負けている" if self.excess_over_buy_hold < 0 else ""),
            "",
            f"最大DD         : {self.max_drawdown * 100:.2f} %"
            f"（買い持ち {self.buy_hold_max_drawdown * 100:.2f} %）",
            f"シャープ       : {self.sharpe:.2f}",
            "",
            f"取引回数       : {self.trade_count} 回",
            f"勝率           : {self.win_rate * 100:.1f} %",
            f"プロフィットファクタ: {self.profit_factor:.2f}",
            f"支払コスト合計 : {self.total_cost_yen:,.0f} 円"
            f"（総利益の {self.cost_ratio_of_gross * 100:.1f}%）",
        ]
        if self.warnings:
            lines.append("")
            lines.append("警告:")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)


def evaluate(result: BacktestResult) -> Report:
    """バックテスト結果を評価してレポートにする。"""
    equity = result.equity.dropna()
    if equity.empty:
        raise ValueError("エクイティカーブが空です")

    initial = result.config.initial_capital
    final = float(equity.iloc[-1])
    total_return = final / initial - 1.0

    price = result.price.dropna()
    buy_hold_return = float(price.iloc[-1] / price.iloc[0] - 1.0)
    bh_equity = initial * (price / price.iloc[0])

    span = equity.index[-1] - equity.index[0]
    days = max(span.total_seconds() / 86400.0, 1e-9)

    wins = [t for t in result.trades if t.pnl > 0]
    losses = [t for t in result.trades if t.pnl <= 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    total_cost = sum(t.cost for t in result.trades)

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    win_rate = len(wins) / len(result.trades) if result.trades else 0.0
    cost_ratio = total_cost / gross_profit if gross_profit > 0 else float("inf")

    warnings = list(result.warnings)
    if result.trades and total_cost > abs(final - initial):
        warnings.append(
            "支払ったコストが最終損益より大きくなっています。"
            "取引回数を減らすか、より狭いスプレッドの執行を検討してください。"
        )
    if len(result.trades) < 30:
        warnings.append(
            f"取引回数が {len(result.trades)} 回しかありません。"
            "この回数では、成績が実力か偶然かを判別できません。"
        )

    return Report(
        strategy_name=result.strategy_name,
        cost_model_name=result.cost_model.name,
        initial_capital=initial,
        final_equity=final,
        total_return=total_return,
        buy_hold_return=buy_hold_return,
        excess_over_buy_hold=total_return - buy_hold_return,
        max_drawdown=max_drawdown(equity),
        buy_hold_max_drawdown=max_drawdown(bh_equity),
        sharpe=sharpe_ratio(equity, _periods_per_year(equity.index)),
        trade_count=len(result.trades),
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_cost_yen=total_cost,
        cost_ratio_of_gross=cost_ratio,
        days=days,
        yen_per_day=(final - initial) / days,
        warnings=warnings,
    )
