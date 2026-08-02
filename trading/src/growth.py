"""成績に応じた拡大と、その前提の検算。

「小さく始めて、うまくいったら大きくする」は、台湾の全取引データを分析した
Barber, Lee, Liu & Odean が、継続的に勝てる少数派の**測定可能な特徴**として
挙げたものそのもの。ここではそれを実装する。

同時に、この考え方が壊れる境界も計算できるようにしてある。
「毎日前日より良く」という目標は、数学的に達成不可能なだけでなく、
**追いかけると危険**である。負けた日に取り返そうとしてサイズを上げる動きは
マーチンゲールであり、破産確率が1に収束する。

だからこのモジュールの拡大ルールは、**負けたあとには絶対に増やさない**。
増やすのは資産が過去最高を更新しているときだけに限る（アンチマーチンゲール）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

_NORM = NormalDist()
_EULER_MASCHERONI = 0.5772156649015329


# ---------------------------------------------------------------------------
# 前提の検算
# ---------------------------------------------------------------------------


def probability_of_monotone_improvement(days: int) -> float:
    """n日連続で「前日より良い成績」が続く確率。

    日々の損益が独立なら、n個の値が単調増加に並ぶ確率は 1/n! になる。
    どの順列も等確率なので、増加順という1通りだけが該当する。

    3日で1/6、10日で360万分の1、30日で 3.8e-33。
    **これは戦略の良し悪しと関係なく成り立つ。**
    優位性がどれだけ大きくても、日々の変動がある限り単調にはならない。
    """
    if days < 1:
        raise ValueError("日数は1以上である必要があります")
    return 1.0 / math.factorial(days)


def win_day_ratio(daily_mean: float, daily_vol: float) -> float:
    """日次の期待リターンとボラティリティから、勝つ日の割合を出す。

    ビットコインの日次ボラティリティは2.5%前後。
    これに対して日次の期待リターンが0.5%（年125%ペース）あっても、
    勝つ日は57.9%にしかならない。**5日に2日は負ける。**

    負ける日があること自体は戦略の失敗ではない。
    負ける日をなくそうとすることが失敗になる。
    """
    if daily_vol <= 0:
        raise ValueError("ボラティリティは正の値である必要があります")
    return _NORM.cdf(daily_mean / daily_vol)


def expected_max_sharpe(
    n_trials: int, n_observations: int, periods_per_year: float = 1.0
) -> float:
    """優位性がまったくない戦略を N 個試したとき、
    最も良く見えたものが示すシャープレシオの期待値。

    Bailey & López de Prado の式にもとづく。
    100個の戦略を試せば、真の優位性がゼロでも
    最良のものはそれなりのシャープを示す。

    **自分が観測したシャープが、この値を超えていなければ、
    それは「たくさん試したから出てきた数字」でしかない。**

    ## 単位を必ず合わせること

    `periods_per_year` は、**比較したいシャープと同じ年率化係数**を渡す。
    既定の 1.0 は「1バーあたり」のシャープに対する閾値を返す。

    `metrics.sharpe_ratio()` は年率化した値を返すので、
    それと比べるなら 1時間足なら 8766、日足なら 365 を渡す必要がある。
    **ここを合わせ忘れると、閾値が実際より約94倍（1時間足の場合）小さくなる。**

    実際にそうなっていた。1時間足5000本・40戦略のとき、
    この関数は 0.031 を返す一方、優位性ゼロの戦略を40個試した実測では
    最良のものが平均 2.42、最悪の回で 4.46 の年率シャープを示した。
    単位を合わせない比較は、安全装置として機能しない。

    合成データでの検証結果（優位性ゼロ・1時間足5000本・ZERO_COST）:

        試行数   実測の最大（平均）   この式（年率化）
           5           1.54              1.58
          10           1.83              2.08
          20           2.29              2.52
          40           2.42              2.90

    試行が互いに相関する場合（同じ戦略のパラメータ探索など）は、
    実測が式を下回る＝**式のほうが厳しい側にずれる**。安全な方向。
    """
    if n_trials < 1 or n_observations < 2:
        raise ValueError("試行数は1以上、観測数は2以上である必要があります")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year は正の値である必要があります")
    if n_trials == 1:
        return 0.0

    # 真のシャープが0のときの、シャープ推定量の標準誤差。
    # 年率化したシャープと比べるなら、標準誤差も同じ係数で年率化する
    se = math.sqrt(periods_per_year / n_observations)

    z1 = _NORM.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _NORM.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return se * ((1 - _EULER_MASCHERONI) * z1 + _EULER_MASCHERONI * z2)


def is_sharpe_meaningful(
    observed_sharpe: float,
    n_trials: int,
    n_observations: int,
    periods_per_year: float = 1.0,
) -> tuple[bool, float]:
    """観測したシャープが、試行数を考慮しても意味があるか。

    戻り値は (意味があるか, 偶然でも到達しうる水準)。

    **observed_sharpe と periods_per_year の単位を必ず揃えること。**
    バックテストの結果から判定するなら、単位を取り違えようのない
    `metrics.multiple_testing_report()` を使うほうが安全。
    """
    threshold = expected_max_sharpe(n_trials, n_observations, periods_per_year)
    return observed_sharpe > threshold, threshold


# ---------------------------------------------------------------------------
# 拡大のルール
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdaptiveSizing:
    """成績に応じてポジションサイズを変える。

    設計上の絶対条件が1つある。**負けたあとに増やさない。**

    負けを取り返そうとしてサイズを上げるのはマーチンゲールで、
    有限の資金では破産確率が1に収束する。
    このクラスは、資産が過去最高を更新しているときにだけ拡大を許し、
    ドローダウン中は必ず縮小する（アンチマーチンゲール）。

    Parameters
    ----------
    base_risk:
        開始時に1トレードで許容する損失（資金比）
    max_risk:
        拡大の上限。実績が良くてもこれを超えない
    min_risk:
        縮小の下限。ここまで下げても回復しなければ止めるべき
    drawdown_floor:
        この率のドローダウンで min_risk まで落とす
    scale_step:
        資産が最高値を更新するたびに、何倍ずつ増やすか
    """

    base_risk: float = 0.005
    max_risk: float = 0.02
    min_risk: float = 0.001
    drawdown_floor: float = 0.20
    scale_step: float = 1.10

    def __post_init__(self) -> None:
        if not 0 < self.min_risk <= self.base_risk <= self.max_risk <= 0.5:
            raise ValueError(
                "min_risk <= base_risk <= max_risk の順で、"
                "いずれも0より大きく0.5以下である必要があります"
            )
        if not 0 < self.drawdown_floor < 1:
            raise ValueError("drawdown_floor は0と1の間である必要があります")
        if self.scale_step < 1.0:
            raise ValueError(
                "scale_step は1以上です。"
                "1未満にすると成功するほど小さく張ることになります"
            )

    def risk_for(self, equity: float, peak_equity: float, highs_made: int) -> float:
        """現在の状態から、1トレードで許容する損失の率を返す。

        Parameters
        ----------
        equity:
            現在の資産
        peak_equity:
            これまでの最高資産
        highs_made:
            最高値を更新した回数。拡大の根拠になる
        """
        if peak_equity <= 0:
            return self.base_risk

        drawdown = max(0.0, 1.0 - equity / peak_equity)

        if drawdown > 0:
            # ドローダウン中は必ず縮小する。深いほど小さく。
            # drawdown_floor に達したら min_risk まで落とす
            ratio = min(1.0, drawdown / self.drawdown_floor)
            risk = self.base_risk + (self.min_risk - self.base_risk) * ratio
            return max(self.min_risk, risk)

        # 最高値を更新している間だけ、段階的に拡大を許す。
        # 指数はそのまま渡すとオーバーフローするので、
        # 上限に達するのに必要な回数で頭打ちにしてから計算する
        if self.scale_step == 1.0 or highs_made <= 0:
            return min(self.max_risk, self.base_risk)

        steps_to_cap = math.log(self.max_risk / self.base_risk) / math.log(self.scale_step)
        effective = min(highs_made, math.ceil(steps_to_cap))
        risk = self.base_risk * (self.scale_step**effective)
        return min(self.max_risk, risk)

    def describe(self) -> str:
        return (
            f"開始 {self.base_risk * 100:.2f}% / 上限 {self.max_risk * 100:.2f}% / "
            f"下限 {self.min_risk * 100:.2f}%、"
            f"最高値更新ごとに ×{self.scale_step:.2f}、"
            f"DD {self.drawdown_floor * 100:.0f}% で下限まで縮小"
        )


def growth_reality_check(
    target_yen_per_day: float,
    capital: float,
    daily_vol: float = 0.025,
) -> str:
    """目標を「毎日の勝率」と「連続改善の確率」に翻訳する。

    数字を見てから目標を決めるためのもの。
    """
    daily_return = target_yen_per_day / capital
    win_ratio = win_day_ratio(daily_return, daily_vol)

    lines = [
        f"元本 {capital:,.0f} 円で 1日 {target_yen_per_day:,.0f} 円を狙う場合",
        "",
        f"  必要な日次リターン : {daily_return * 100:.3f} %",
        f"  年換算（単利250日）: {daily_return * 250 * 100:.0f} %",
        "",
        f"  想定日次ボラティリティ {daily_vol * 100:.1f}% のとき",
        f"  勝つ日   : {win_ratio * 100:.1f} %",
        f"  負ける日 : {(1 - win_ratio) * 100:.1f} %",
        "",
        "「前日より良い成績」が続く確率",
    ]
    for n in (3, 5, 10, 20, 30):
        p = probability_of_monotone_improvement(n)
        if p > 1e-12:
            lines.append(f"  {n:>2}日連続: {p:.2e}（{1 / p:,.0f}回に1回）")
        else:
            lines.append(f"  {n:>2}日連続: {p:.2e}（事実上ゼロ）")
    lines += [
        "",
        "負ける日があることは戦略の失敗ではありません。",
        "負ける日をなくそうとすることが失敗になります。",
    ]
    return "\n".join(lines)
