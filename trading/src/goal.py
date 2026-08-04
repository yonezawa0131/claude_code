"""目標を、達成条件に翻訳する。

「1日500円」は金額であって、難易度ではない。
難易度は **元本・税制・コスト・優位性** の4つで決まる。

この module の役割は、その4つを分解して、
**どれが確実な手段で、どれが不確実な手段か**をはっきりさせることにある。

## 4つの手段を、確実な順に並べる

1. **元本** — 完全に確実。1日500円は、元本30万なら年42%、元本150万なら年8%。
   同じ金額目標が、元本を5倍にするだけで「ほぼ不可能」から「債券並み」に変わる
2. **税制** — 確実かつ構造的。同じ粗利でも、手取りは制度で2倍以上変わる
3. **コスト** — 測定可能。この基盤で測った（成行の往復0.18%、週次なら指値でほぼ0）
4. **優位性** — 不確実。**この基盤では6戦略を実データで測り、すべて否定された。**
   7つ目は、日本のアルトコイン市場が若すぎて**確かめる手段がなかった**

上から3つは、探さなくても手に入る。4つ目だけが探すものになる。
そして4つ目に賭ける前に、上の3つを使い切っているかを確かめるべきになる。
"""

from __future__ import annotations

from dataclasses import dataclass

#: この基盤が実データで測った、ビットコイン買い持ちの成績
#: （BTC/JPY 2024-01-01 〜 2026-08-01、944日）
BTC_BUY_HOLD_ANNUAL = 0.179
BTC_BUY_HOLD_SHARPE = 0.38
BTC_BUY_HOLD_MAX_DD = -0.502


@dataclass(frozen=True)
class TaxRegime:
    """課税の枠組み。手取りに直結する。"""

    name: str
    #: 利益にかかる率
    rate: float
    #: 損失を繰り越せる年数
    loss_carryforward_years: int
    note: str

    def net(self, gross: float) -> float:
        """粗利から手取りを出す。損失には課税されない。"""
        return gross * (1.0 - self.rate) if gross > 0 else gross

    def gross_needed(self, net_target: float) -> float:
        """手取りで net_target を得るのに必要な粗利。"""
        if self.rate >= 1.0:
            raise ValueError("税率が100%以上です")
        return net_target / (1.0 - self.rate)


#: 2026年8月時点。雑所得・総合課税。住民税込みで最高約55%
CRYPTO_UNTIL_2027 = TaxRegime(
    "暗号資産（2027年まで）", 0.55, 0,
    "雑所得・総合課税。所得により最高約55%。**損失の繰越控除ができない**",
)

#: 2026年3月31日に改正法成立。2028年1月1日から適用見込み
#: （金商法改正が2026年通常国会で成立し2027年中に施行されることが条件）
CRYPTO_FROM_2028 = TaxRegime(
    "暗号資産（2028年〜見込み）", 0.20315, 3,
    "申告分離課税。損失は3年繰越可。ただし繰越の相殺は暗号資産の中だけ",
)

TOKUTEI_ACCOUNT = TaxRegime(
    "上場株式等・特定口座", 0.20315, 3,
    "申告分離課税。損失は3年繰越可。他の上場株式等の利益と相殺できる",
)

NISA_GROWTH = TaxRegime(
    "NISA成長投資枠", 0.0, 0,
    "非課税。年240万円・生涯1,200万円まで。**損失は繰り越せないが、そもそも課税されない**",
)

REGIMES = (CRYPTO_UNTIL_2027, CRYPTO_FROM_2028, TOKUTEI_ACCOUNT, NISA_GROWTH)


def required_gross_annual_return(
    target_yen_per_day: float,
    capital_yen: float,
    tax: TaxRegime,
    days_per_year: int = 365,
) -> float:
    """目標金額を、必要な**税引前**の年率リターンに翻訳する。

    手取りで日いくらを狙うなら、税のぶんだけ多く稼ぐ必要がある。
    ここを忘れると、達成条件を半分に見誤る。
    """
    if capital_yen <= 0:
        raise ValueError("元本は正の値である必要があります")
    net_annual = target_yen_per_day * days_per_year / capital_yen
    return tax.gross_needed(net_annual)


def feasibility_report(
    target_yen_per_day: float = 500.0,
    capitals: tuple[float, ...] = (300_000.0, 500_000.0, 1_000_000.0, 3_000_000.0),
    tax: TaxRegime = CRYPTO_UNTIL_2027,
) -> str:
    """目標・元本・税制から、必要な粗リターンの表を作る。

    ビットコインを持っていただけの実績（この基盤の実測値）を併記する。
    **必要な水準がそれを大きく超えるなら、足りない分は優位性で埋めるしかない。**
    そして優位性は、この基盤が5回探して5回とも見つからなかったものになる。
    """
    lines = [
        f"手取りで1日 {target_yen_per_day:,.0f} 円を得るには（{tax.name}・税率 {tax.rate * 100:.1f}%）",
        "",
        f"  {'元本':>12}{'必要な粗利(年率)':>18}{'買い持ち実績との差':>20}   判定",
        "  " + "-" * 62,
    ]
    for cap in capitals:
        need = required_gross_annual_return(target_yen_per_day, cap, tax)
        gap = need - BTC_BUY_HOLD_ANNUAL
        if gap <= 0:
            verdict = "買い持ちで届く"
        elif gap < 0.15:
            verdict = "やや足りない"
        elif gap < 0.50:
            verdict = "優位性が要る"
        else:
            verdict = "**現実的でない**"
        lines.append(
            f"  {cap:>11,.0f}円{need * 100:>17.1f}%{gap * 100:>+19.1f}pt   {verdict}"
        )

    lines += [
        "",
        f"  ※ 買い持ちの実績 = 年 {BTC_BUY_HOLD_ANNUAL * 100:.1f}%"
        f"（シャープ {BTC_BUY_HOLD_SHARPE:.2f}、最大下落 {BTC_BUY_HOLD_MAX_DD * 100:.1f}%）。",
        "    BTC/JPY 2024-01-01 〜 2026-08-01 の実測値であり、将来の保証ではない。",
        f"  ※ {tax.note}",
    ]
    return "\n".join(lines)


def tax_regime_comparison(
    target_yen_per_day: float = 500.0, capital_yen: float = 1_000_000.0
) -> str:
    """同じ目標・同じ元本で、制度によって必要な粗利がどれだけ変わるかを出す。

    **これは探さなくても手に入る差になる。**
    優位性を探すより先に、ここを使い切っているかを確かめること。
    """
    lines = [
        f"元本 {capital_yen:,.0f} 円で、手取り1日 {target_yen_per_day:,.0f} 円を狙う場合",
        "",
        f"  {'制度':<26}{'税率':>8}{'必要な粗利(年率)':>18}",
        "  " + "-" * 52,
    ]
    for regime in REGIMES:
        need = required_gross_annual_return(target_yen_per_day, capital_yen, regime)
        lines.append(f"  {regime.name:<26}{regime.rate * 100:>7.2f}%{need * 100:>17.1f}%")

    base = required_gross_annual_return(target_yen_per_day, capital_yen, CRYPTO_UNTIL_2027)
    best = required_gross_annual_return(target_yen_per_day, capital_yen, NISA_GROWTH)
    lines += [
        "",
        f"  最も不利な制度と最も有利な制度で、必要な粗利は {base / best:.2f} 倍違う。",
        "  **同じ運用成績でも、制度が違えば手取りが倍以上変わる。**",
        "  暗号資産は2027年まで最も不利な側にあり、2028年から改善する見込み。",
    ]
    return "\n".join(lines)


def levers_summary() -> str:
    """4つの手段を、確実な順に並べる。"""
    return "\n".join([
        "目標に近づく手段を、確実な順に並べる",
        "",
        "  1. 元本を増やす         確実      1日500円は元本30万で年42%、150万で年8%",
        "  2. 税制を選ぶ           確実      同じ粗利で手取りが最大2.2倍変わる",
        "  3. コストを下げる       測定可能  週次リバランス＋指値で往復0.18%→ほぼ0",
        "  4. 優位性を見つける     不確実    **6戦略を測り6戦略とも否定。7つ目は測る手段がない**",
        "",
        "  上から3つは探さなくても手に入る。4つ目だけが探すものになる。",
        "  そして4つ目に賭ける前に、上の3つを使い切っているかを確かめるべきになる。",
    ])
