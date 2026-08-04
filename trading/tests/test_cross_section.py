"""銘柄横断の検定の検証。

単一銘柄の戦略が実データで全滅したあと、残った仮説クラスがこれになる。
**使う情報源が違う。** 他の銘柄の値動きで、ある銘柄の将来を予測する。

この検定には、これまでになかった固有の落とし穴が1つある。

## ベータの罠

暗号資産では、**上昇率の高い銘柄はたいていベータの高い銘柄**である。
上げ相場で「直近上がった銘柄」を買えば勝つ。しかしそれは予測力ではなく、
市場感応度の高いものを選んで市場に乗っているだけになる。

上位群のリターンだけを見ていると、これを優位性と読む。
そして暗号資産の観測期間はたいてい上げ相場を含むので、**ほぼ必ず読む**。

だからこの検定の本体は「上位群 − 下位群」になる。
市場の動きが両側で相殺され、順位づけの予測力だけが残る。

ここで確かめるのは3つ。
  1. 本物の横断モメンタムを検出できるか
  2. 無いときに無いと言えるか
  3. **ベータのばらつきを優位性と誤認しないか**

3つ目がこのファイルの主眼になる。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts.make_synthetic_panel import make_panel  # noqa: E402
from trading.src.cross_section import (  # noqa: E402
    build_panel,
    cross_sectional_test,
)

ASSETS, DAYS, SEED = 30, 600, 1
LOOKBACK, HOLDING = 7, 7


def _panel(**kw) -> pd.DataFrame:
    frames = make_panel(ASSETS, DAYS, SEED, **kw)
    for f in frames.values():
        f["timestamp"] = pd.to_datetime(f["timestamp"], utc=True, format="ISO8601")
        f.set_index("timestamp", inplace=True)
    return build_panel(frames)


def _t(series: pd.Series) -> float:
    s = series.dropna()
    return float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s))))


def _run(panel: pd.DataFrame, **kw):
    return cross_sectional_test(panel, lookback=LOOKBACK, holding=HOLDING, **kw)


# ---------------------------------------------------------------------------
# 1. 本物を検出できるか
# ---------------------------------------------------------------------------


def test_detects_a_real_cross_sectional_effect():
    result = _run(_panel(theme_scale=0.010))
    assert _t(result.spread) > 4.0, f"t = {_t(result.spread):.2f}"
    assert result.spread.mean() > 0


def test_a_stronger_effect_gives_a_wider_spread():
    """埋め込んだ強さと検出した幅が連動すること。

    連動しないなら、拾っているのはテーマではない別の何かになる。
    """
    spreads = [
        _run(_panel(theme_scale=s)).spread.mean() for s in (0.0, 0.005, 0.010, 0.020)
    ]
    assert spreads == sorted(spreads), spreads


# ---------------------------------------------------------------------------
# 2. 無いときに無いと言えるか
# ---------------------------------------------------------------------------


def test_finds_nothing_when_there_is_no_theme():
    result = _run(_panel(theme_scale=0.0))
    assert abs(_t(result.spread)) < 2.0, f"t = {_t(result.spread):.2f}"


# ---------------------------------------------------------------------------
# 3. ベータの罠
# ---------------------------------------------------------------------------


def test_beta_dispersion_in_a_bull_market_is_not_called_an_edge():
    """**このファイルの主眼。**

    テーマ（＝予測できる固有の動き）はゼロ。あるのは
    ベータのばらつきと、上げ相場だけ。

    このとき上位群は市場を大きく上回って見える。
    しかしそれは高ベータ銘柄を選んで市場に乗っただけで、予測力ではない。
    """
    result = _run(_panel(theme_scale=0.0, beta_spread=0.5, market_drift=0.004))

    # 上位群だけを見ると、優秀な戦略に見える
    assert result.top.mean() > 0
    assert _t(result.top) > 2.0, "この対照は上位群が儲かって見えないと意味がない"

    # しかし本体（上位 − 下位）は無であること
    assert abs(_t(result.spread)) < 2.0, (
        f"ベータのばらつきを優位性と誤認しています（spread の t = {_t(result.spread):+.2f}）"
    )


def test_the_spread_removes_the_market_move():
    """市場が大きく動いても、spread はそれに引きずられないこと。"""
    up = _run(_panel(theme_scale=0.0, market_drift=+0.004))
    down = _run(_panel(theme_scale=0.0, market_drift=-0.004))

    assert up.market.mean() > 0 > down.market.mean(), "対照の作りが意図どおりでない"
    # 市場が正反対でも spread はどちらも0付近
    assert abs(up.spread.mean() - down.spread.mean()) < 0.02


# ---------------------------------------------------------------------------
# 因果性と欠損の扱い
# ---------------------------------------------------------------------------


def test_ranking_never_uses_the_holding_period():
    """順位づけに使うのは保有開始までに確定した価格だけであること。

    パネルの「保有期間の中身」を書き換えても順位が変わらないなら、
    順位づけは未来を見ていない。
    """
    panel = _panel(theme_scale=0.010)
    base = _run(panel)

    tampered = panel.copy()
    # 最後の保有期間ぶんだけ価格を大きく動かす
    tampered.iloc[-HOLDING:] = tampered.iloc[-HOLDING:] * 5.0
    after = _run(tampered)

    # 最後の期を除けば、上位群の成績は完全に一致するはず
    n = min(len(base.top), len(after.top)) - 1
    assert np.allclose(base.top.values[:n], after.top.values[:n]), "先読みしています"


def test_assets_not_yet_listed_are_excluded_not_filled():
    """上場前の欠損を前方補完しないこと。

    無かった価格を作ると、できなかった取引ができてしまう。
    """
    panel = _panel(theme_scale=0.010)
    panel.iloc[:200, :5] = np.nan  # 5銘柄が途中から上場した想定

    result = _run(panel, min_universe=10)
    early = result.universe_size[result.universe_size.index < panel.index[200]]
    assert (early <= ASSETS - 5).all(), "上場前の銘柄を数えています"
    assert result.universe_size.iloc[-1] == ASSETS


def test_thin_universe_periods_are_skipped():
    panel = _panel(theme_scale=0.010)
    panel.iloc[:, 8:] = np.nan  # 8銘柄しか残らない
    result = _run(panel, min_universe=10)
    assert result.spread.empty, "銘柄数が足りない期間を使っています"


# ---------------------------------------------------------------------------
# コストと設定
# ---------------------------------------------------------------------------


def test_costs_reduce_the_spread():
    panel = _panel(theme_scale=0.010)
    free = _run(panel, cost_per_side=0.0).spread.mean()
    paid = _run(panel, cost_per_side=0.0012).spread.mean()
    assert paid < free
    # 回転率ぶんのコストが、買い側と売り側の両方にかかっている
    turnover = _run(panel).turnover.mean()
    assert free - paid == pytest.approx(turnover * 0.0012 * 4, rel=0.05)


def test_turnover_is_reported():
    result = _run(_panel(theme_scale=0.010))
    assert 0.0 <= result.turnover.mean() <= 1.0
    assert "売買回転率" in result.summary()


def test_a_universe_too_small_for_the_grouping_is_rejected():
    """各分位に2銘柄も入らない設定を認めない。

    1銘柄の値動きが分位の成績になってしまう。
    """
    with pytest.raises(ValueError, match="min_universe"):
        cross_sectional_test(_panel(), lookback=7, holding=7, n_groups=5, min_universe=8)


def test_summary_leads_with_the_spread():
    text = _run(_panel(theme_scale=0.010)).summary()
    assert "上位 − 下位" in text
    assert "市場（等加重）" in text


# ---------------------------------------------------------------------------
# 無作為割当の対照
# ---------------------------------------------------------------------------


def test_random_group_null_credits_a_real_ranking():
    from trading.src.cross_section import random_group_null

    result = random_group_null(_panel(theme_scale=0.010), n_runs=100)
    assert result.percentile >= 95
    assert "順位づけに意味があります" in result.summary()


def test_random_group_null_rejects_the_beta_trap():
    """**ベータの罠は、無作為割当でも弾かれること。**

    t 検定と無作為割当は独立な2つの関門になる。
    暗号資産のリターンは銘柄間で強く相関し分散も変わるので、
    独立同分布を前提にした t 値だけでは足りない。
    """
    from trading.src.cross_section import random_group_null

    result = random_group_null(
        _panel(theme_scale=0.0, beta_spread=0.5, market_drift=0.004), n_runs=100
    )
    assert result.percentile < 95, f"上位 {100 - result.percentile:.1f}%"
    assert "説明できません" in result.summary()


def test_random_group_null_preserves_the_market_move():
    """無作為割当でも、市場の動きは対照側に残っていること。

    残っていなければ「市場に乗っただけ」を差し引けない。
    """
    from trading.src.cross_section import random_group_null

    result = random_group_null(
        _panel(theme_scale=0.0, beta_spread=0.5, market_drift=0.004), n_runs=60
    )
    # 無作為でも分位間の差はばらつく。中央値0付近・幅ありが正しい姿
    assert abs(np.median(result.null_spreads)) < 0.01
    assert result.null_spreads.std() > 0


def test_random_group_null_requires_enough_runs():
    from trading.src.cross_section import random_group_null

    with pytest.raises(ValueError, match="20回以上"):
        random_group_null(_panel(), n_runs=5)


# ---------------------------------------------------------------------------
# 前後半の比較は、パネルを切らずに結果を分ける
# ---------------------------------------------------------------------------


def test_halves_always_reconcile_with_the_whole():
    """**前半と後半を合わせたら、全期間に一致すること。**

    実データで、全期間 −0.742%/期 に対して前半 −0.012% / 後半 +0.898% という
    部分集合として成立しない数字が出た。

    原因はパネルを切ってから測り直していたこと。944日を472日で切ると、
    後半の検定は479日目から始まる。479 を7で割った余りは3なので、
    **全期間とは3日ずれた週を測っていた。**

    結果を分けるだけなら、この食い違いは起きない。
    """
    result = _run(_panel(theme_scale=0.008))
    first, second = result.split_halves()

    assert len(first) + len(second) == len(result.spread.dropna())
    combined = pd.concat([first, second])
    assert combined.mean() == pytest.approx(result.spread.dropna().mean())


def test_halves_do_not_overlap():
    result = _run(_panel(theme_scale=0.008))
    first, second = result.split_halves()
    assert first.index.max() < second.index.min()


# ---------------------------------------------------------------------------
# 平均が少数の期に支配されていないか
# ---------------------------------------------------------------------------


def test_robustness_flags_a_mean_driven_by_one_period():
    """**1期を除くと符号が変わる平均を、そうと言うこと。**

    暗号資産の週次リターンは大きく裾を引く。1期の暴落だけで
    全期間の平均の符号が変わるとき、その平均と t 値は
    実質的に1個の観測を報告しているにすぎない。
    """
    result = _run(_panel(theme_scale=0.0))
    # 1期だけ極端な値を入れる
    spiked = result.spread.copy()
    spiked.iloc[len(spiked) // 2] = -abs(spiked).max() * 60
    result.top = spiked + result.bottom

    text = result.robustness()
    assert "符号が変わります" in text or "頑健ではありません" in text
    assert "中央値" in text


def test_robustness_reports_the_median_alongside_the_mean():
    text = _run(_panel(theme_scale=0.010)).robustness()
    assert "平均" in text and "中央値" in text
    assert "最大の1期を除く" in text


def test_robustness_needs_enough_periods():
    result = _run(_panel(theme_scale=0.010))
    result.top = result.top.iloc[:3]
    result.bottom = result.bottom.iloc[:3]
    assert "測れません" in result.robustness()
