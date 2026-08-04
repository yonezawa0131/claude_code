"""目標の分解の検証。

「1日500円」は金額であって難易度ではない。
難易度は 元本・税制・コスト・優位性 の4つで決まる。

このファイルが固定するのは、**そのうち3つは探さなくても手に入る**
という事実になる。優位性だけが探すものであり、
この基盤はそれを5回探して5回とも見つけられなかった。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.goal import (  # noqa: E402
    BTC_BUY_HOLD_ANNUAL,
    CRYPTO_FROM_2028,
    CRYPTO_UNTIL_2027,
    NISA_GROWTH,
    TOKUTEI_ACCOUNT,
    TaxRegime,
    feasibility_report,
    levers_summary,
    required_gross_annual_return,
    tax_regime_comparison,
)


# ---------------------------------------------------------------------------
# 元本というレバー
# ---------------------------------------------------------------------------


def test_capital_moves_the_bar_more_than_anything_else():
    """同じ金額目標でも、元本で難易度が桁違いに変わること。"""
    small = required_gross_annual_return(500.0, 300_000.0, CRYPTO_UNTIL_2027)
    large = required_gross_annual_return(500.0, 3_000_000.0, CRYPTO_UNTIL_2027)
    assert small / large == pytest.approx(10.0, rel=1e-6)
    assert small > 1.0, "元本30万では年100%超が必要なはず"
    assert large < BTC_BUY_HOLD_ANNUAL, "元本300万なら買い持ちで届くはず"


def test_the_requirement_is_inversely_proportional_to_capital():
    a = required_gross_annual_return(500.0, 1_000_000.0, NISA_GROWTH)
    b = required_gross_annual_return(500.0, 2_000_000.0, NISA_GROWTH)
    assert a == pytest.approx(b * 2)


# ---------------------------------------------------------------------------
# 税というレバー
# ---------------------------------------------------------------------------


def test_tax_more_than_doubles_the_requirement():
    """最も不利な制度と最も有利な制度で、必要な粗利が2倍以上違うこと。

    **これは探さなくても手に入る差になる。**
    """
    worst = required_gross_annual_return(500.0, 1_000_000.0, CRYPTO_UNTIL_2027)
    best = required_gross_annual_return(500.0, 1_000_000.0, NISA_GROWTH)
    assert worst / best > 2.0, f"{worst / best:.2f} 倍"


def test_the_2028_change_materially_lowers_the_bar():
    """2028年からの分離課税移行で、必要な粗利が大きく下がること。"""
    now = required_gross_annual_return(500.0, 1_000_000.0, CRYPTO_UNTIL_2027)
    later = required_gross_annual_return(500.0, 1_000_000.0, CRYPTO_FROM_2028)
    assert later < now * 0.6


def test_crypto_from_2028_matches_listed_securities():
    assert CRYPTO_FROM_2028.rate == pytest.approx(TOKUTEI_ACCOUNT.rate)


def test_net_and_gross_are_inverses():
    for regime in (CRYPTO_UNTIL_2027, CRYPTO_FROM_2028, NISA_GROWTH):
        assert regime.net(regime.gross_needed(0.10)) == pytest.approx(0.10)


def test_losses_are_not_taxed():
    """損失に課税してはいけない。手取りの計算を甘くしないため。"""
    assert CRYPTO_UNTIL_2027.net(-0.30) == pytest.approx(-0.30)


def test_a_full_tax_rate_is_rejected():
    with pytest.raises(ValueError):
        TaxRegime("架空", 1.0, 0, "").gross_needed(0.1)


# ---------------------------------------------------------------------------
# レポート
# ---------------------------------------------------------------------------


def test_report_marks_the_impossible_cases():
    """元本30万・暗号資産の税制では「現実的でない」と言い切ること。

    ここを濁すと、目標の難易度を見誤ったまま資金を入れることになる。
    """
    text = feasibility_report(500.0, tax=CRYPTO_UNTIL_2027)
    assert "現実的でない" in text
    assert "買い持ちで届く" in text


def test_report_always_shows_the_buy_and_hold_benchmark():
    text = feasibility_report(500.0)
    assert "買い持ちの実績" in text
    assert "将来の保証ではない" in text


def test_comparison_names_the_multiple():
    text = tax_regime_comparison(500.0, 1_000_000.0)
    assert "倍違う" in text
    for regime in (CRYPTO_UNTIL_2027, NISA_GROWTH):
        assert regime.name in text


def test_levers_are_ordered_by_certainty():
    """確実な手段が先に来ること。

    優位性を1番目に置くと、探すことが目的化する。
    """
    text = levers_summary()
    assert text.index("元本を増やす") < text.index("優位性を見つける")
    assert "6戦略とも否定" in text


def test_zero_capital_is_rejected():
    with pytest.raises(ValueError):
        required_gross_annual_return(500.0, 0.0, NISA_GROWTH)
