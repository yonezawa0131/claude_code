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
from .growth import is_sharpe_meaningful


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
    #: 年率化したシャープレシオ
    sharpe: float
    #: sharpe の年率化に使った係数。試行数を考慮した判定で単位を合わせるのに要る
    periods_per_year: float
    #: シャープの計算に使ったリターンの本数
    n_observations: int

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

    periods_per_year = _periods_per_year(equity.index)

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
        sharpe=sharpe_ratio(equity, periods_per_year),
        periods_per_year=periods_per_year,
        n_observations=max(len(equity) - 1, 0),
        trade_count=len(result.trades),
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_cost_yen=total_cost,
        cost_ratio_of_gross=cost_ratio,
        days=days,
        yen_per_day=(final - initial) / days,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# 資金管理の算術
#
# いずれも実証研究で裏付けのある関係を、計算できる形にしたもの。
# ---------------------------------------------------------------------------


def breakeven_win_rate(reward_risk_ratio: float) -> float:
    """損益比から、損益分岐に必要な勝率を出す。

    必要勝率 = 1 / (1 + 損益比)

    勝率30%でも、平均利益が平均損失の2.33倍あれば期待値はプラスになる。
    逆に損益比1:1なら勝率50%を超えないと成立しない。
    「勝率が高い戦略が良い戦略」ではない。
    """
    if reward_risk_ratio <= 0:
        raise ValueError("損益比は正の値である必要があります")
    return 1.0 / (1.0 + reward_risk_ratio)


def required_reward_risk(win_rate: float) -> float:
    """勝率から、損益分岐に必要な損益比を出す。"""
    if not 0 < win_rate < 1:
        raise ValueError("勝率は0と1の間である必要があります")
    return (1.0 - win_rate) / win_rate


def recovery_return(drawdown: float) -> float:
    """ドローダウンから回復するのに必要なリターン。

    必要リターン = 1 / (1 - DD) - 1

    -50%から戻すには+100%が要る。この非対称性が、
    ポジションサイズを抑えるべき最大の理由になる。
    """
    if not 0 <= abs(drawdown) < 1:
        raise ValueError("ドローダウンは0以上1未満である必要があります")
    dd = abs(drawdown)
    return 1.0 / (1.0 - dd) - 1.0


def kelly_fraction(trades: list) -> float:
    """トレード履歴からケリー基準の賭け金比率を推定する。

    f* = 勝率 - (1 - 勝率) / 損益比

    **この値をそのまま使ってはいけない。**
    賭け金を最適値の c 倍にすると長期成長率は概ね c(2-c) 倍になり、
    2倍賭けると成長率はゼロ、半分なら最大の約75%を保てる。
    実務では 1/2 か 1/4 に落として使う。

    さらに、この推定は過去のトレード分布が将来も続く前提に立っている。
    サンプルが少ないと勝率も損益比もぶれるため、
    取引回数が少ないうちは信用してはいけない。
    """
    if not trades:
        return 0.0
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [abs(t.pnl) for t in trades if t.pnl <= 0]
    if not wins or not losses:
        return 0.0

    p = len(wins) / len(trades)
    avg_win = sum(wins) / len(wins)
    avg_loss = sum(losses) / len(losses)
    if avg_loss == 0:
        return 0.0

    b = avg_win / avg_loss
    return p - (1 - p) / b


def multiple_testing_report(report: Report, n_trials: int) -> str:
    """試した戦略の数を考慮して、観測したシャープに意味があるかを判定する。

    **単位を取り違えようがないので、素の数値を渡す
    `growth.is_sharpe_meaningful()` より、こちらを使うこと。**
    年率化係数も観測数も Report が持っているものを使う。

    n_trials には「この結果を出すまでに試した戦略・パラメータの総数」を渡す。
    採用した1個ではなく、**捨てた分も含めた数**。
    数え忘れると、閾値が実際より低く出て、偶然を実力と読むことになる。
    """
    if n_trials < 1:
        raise ValueError("試行数は1以上である必要があります")

    ok, threshold = is_sharpe_meaningful(
        report.sharpe,
        n_trials=n_trials,
        n_observations=max(report.n_observations, 2),
        periods_per_year=report.periods_per_year,
    )

    lines = [
        "試行数を考慮した判定",
        "",
        f"  試した戦略・設定の数 : {n_trials}",
        f"  観測数               : {report.n_observations} 本",
        f"  観測したシャープ     : {report.sharpe:.2f}（年率）",
        f"  優位性ゼロでも到達しうる水準: {threshold:.2f}",
        "",
    ]
    if n_trials == 1:
        lines.append(
            "  ※ 試行数を1として計算しています。"
            "**実際に試した数を数えて渡さないと、この判定は意味を持ちません。**"
        )
    elif ok:
        lines.append(
            f"  → 偶然の水準を {report.sharpe - threshold:.2f} 上回っています。"
            "ただしこれは「偶然では説明しにくい」というだけで、"
            "将来も続くことの根拠にはなりません。"
        )
    else:
        lines.append(
            "  → **この成績は、たくさん試したことだけで説明がつきます。**"
            "優位性の証拠にはなりません。"
        )
    return "\n".join(lines)


def money_management_report(result: BacktestResult) -> str:
    """資金管理の観点からの補足レポート。"""
    trades = result.trades
    if not trades:
        return "トレードがありません。"

    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [abs(t.pnl) for t in trades if t.pnl <= 0]
    win_rate = len(wins) / len(trades)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    rr = avg_win / avg_loss if avg_loss else float("inf")

    equity = result.equity.dropna()
    dd = abs(max_drawdown(equity))
    kelly = kelly_fraction(trades)

    lines = [
        "資金管理の観点",
        "",
        f"  勝率           : {win_rate * 100:.1f} %",
        f"  平均利益/平均損失: {rr:.2f}",
        f"  損益分岐に必要な勝率: {breakeven_win_rate(rr) * 100:.1f} %"
        + ("  （足りている）" if win_rate > breakeven_win_rate(rr) else "  （足りていない）"),
        "",
        f"  最大ドローダウン: {dd * 100:.1f} %",
        f"  そこから戻すのに必要なリターン: {recovery_return(dd) * 100:.1f} %",
        "",
        f"  ケリー基準の推定値: {kelly * 100:.1f} %",
        f"  推奨（半分に落とす）: {max(kelly, 0) / 2 * 100:.1f} %",
    ]
    if kelly <= 0:
        lines.append("")
        lines.append("  ケリー値が0以下です。この戦略に賭けるべき資金はありません。")
    if len(trades) < 100:
        lines.append("")
        lines.append(
            f"  ※ 取引 {len(trades)} 回では勝率も損益比も安定しません。"
            "ケリー値は参考程度に。"
        )
    return "\n".join(lines)
