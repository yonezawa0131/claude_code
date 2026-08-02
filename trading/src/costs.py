"""取引コストのモデル。

バックテストが嘘をつく最大の原因はコストの過小評価なので、
ここは保守側（コストを多めに見る側）に倒してある。

料率は調査時点（2026年8月）に公開情報から拾ったもの。
**確認できたものと、できなかったものを区別して記載している。**
実際に口座を開いたら管理画面の数字で上書きすること。
料率が0.05%違うだけで、日に数回転する戦略の損益は大きく変わる。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderType(Enum):
    """注文の種類。

    TAKER: 板を食う成行/不利指値。約定は確実だがスプレッドを払う
    MAKER: 板に並べる指値。手数料は安い（マイナスのこともある）が、
           約定するとは限らず、しかも「約定したときは不利な側」という
           逆選択（adverse selection）がある
    """

    TAKER = "taker"
    MAKER = "maker"


@dataclass(frozen=True)
class CostModel:
    """1取引所ぶんのコスト設定。

    すべて「率」で持つ。bps ではなく小数（0.0005 = 0.05%）で統一する。
    単位を混ぜると事故になるので、bps を使いたい場合は from_bps を使う。
    """

    name: str

    #: 板を食う側の手数料率
    taker_fee: float

    #: 板に並べる側の手数料率。マイナスなら受け取り（リベート）
    maker_fee: float

    #: 成行で払う片道スプレッド。仲値からの乖離として片道分
    half_spread: float

    #: 約定価格のさらなる不利側へのズレ。板の薄さ・急変時の滑り
    slippage: float

    #: この設定の出典・確度メモ。数字を信じてよい度合いを持ち歩く
    note: str = ""

    #: 未確認の数字を含むか。True ならレポートに警告を出す
    unverified: bool = False

    @staticmethod
    def from_bps(
        name: str,
        taker_fee_bps: float,
        maker_fee_bps: float,
        half_spread_bps: float,
        slippage_bps: float,
        note: str = "",
        unverified: bool = False,
    ) -> "CostModel":
        return CostModel(
            name=name,
            taker_fee=taker_fee_bps / 10_000,
            maker_fee=maker_fee_bps / 10_000,
            half_spread=half_spread_bps / 10_000,
            slippage=slippage_bps / 10_000,
            note=note,
            unverified=unverified,
        )

    def cost_rate(self, order_type: OrderType) -> float:
        """片道の実効コスト率。約定価格に対する不利側への上乗せ分。

        MAKER は指値が板に並ぶので、理屈の上ではスプレッドを払わない。

        **ただしこの計算は「並べたら必ず約定する」前提に立っている。**
        約定確率はモデル化していない（未実装）。実際には、指値が約定するのは
        価格が自分に向かってきたとき＝不利な側であることが多く（逆選択）、
        約定しなかった取引は機会損失として消える。

        したがって MAKER の結果は**上振れしている前提で読むこと。**
        合成データで測った検出限界（成行 beta=0.376 / 指値 beta=0.042）の
        9倍差も、この前提の上に立った上限値であって、実現値ではない。
        """
        if order_type is OrderType.TAKER:
            return self.taker_fee + self.half_spread + self.slippage
        return self.maker_fee + self.slippage

    def round_trip_rate(self, order_type: OrderType) -> float:
        """往復の実効コスト率。損益分岐に必要な値幅の下限になる。"""
        return 2 * self.cost_rate(order_type)


# ---------------------------------------------------------------------------
# 国内取引所のプリセット
#
# 板取引（取引所形式）と販売所形式ではコストが2桁違う。
# 販売所でのデイトレードは、下の数字を見れば分かるとおり成立しない。
# ---------------------------------------------------------------------------

#: GMOコイン 取引所形式（BTC/ETH/XRP/DAI）
#: Maker -0.01% / Taker 0.05% は公開情報で確認できた
GMO_EXCHANGE = CostModel.from_bps(
    name="GMOコイン（取引所・BTC_JPY）",
    taker_fee_bps=5.0,
    maker_fee_bps=-1.0,
    half_spread_bps=2.0,
    slippage_bps=2.0,
    note="Maker -0.01% / Taker 0.05% は確認済み。スプレッドと滑りは保守的な仮置き",
)

#: bitbank 取引所形式
#: Maker -0.02% は確認できたが、**Taker は確認できなかった**
BITBANK_EXCHANGE = CostModel.from_bps(
    name="bitbank（取引所・BTC_JPY）",
    taker_fee_bps=12.0,
    maker_fee_bps=-2.0,
    half_spread_bps=1.0,
    slippage_bps=2.0,
    note="Maker -0.02% は確認済み。Taker 0.12% は未確認の仮置き。要・管理画面での確認",
    unverified=True,
)

#: Coincheck 取引所形式（Maker/Taker とも無料との情報）
COINCHECK_EXCHANGE = CostModel.from_bps(
    name="Coincheck（取引所・BTC_JPY）",
    taker_fee_bps=0.0,
    maker_fee_bps=0.0,
    half_spread_bps=3.0,
    slippage_bps=3.0,
    note="手数料無料との情報。ただし板が薄い時間帯の滑りは別途かかる",
)

#: 販売所形式（どの社も片道3〜6%程度）
#: これは「使ってはいけない」ことを数字で示すための対照用プリセット
DEALER_DESK = CostModel.from_bps(
    name="販売所形式（対照用・使ってはいけない例）",
    taker_fee_bps=0.0,
    maker_fee_bps=0.0,
    half_spread_bps=450.0,  # 片道4.5% = 往復9%
    slippage_bps=0.0,
    note="bitFlyer約5.9% / Coincheck約5〜6% / GMO約3.8〜6.0% の中間を採用",
)

#: コストゼロ。エンジンの検算専用。実運用の判断に使ってはいけない
ZERO_COST = CostModel(
    name="コストゼロ（エンジン検算用）",
    taker_fee=0.0,
    maker_fee=0.0,
    half_spread=0.0,
    slippage=0.0,
    note="テスト専用",
)


PRESETS: dict[str, CostModel] = {
    "gmo": GMO_EXCHANGE,
    "bitbank": BITBANK_EXCHANGE,
    "coincheck": COINCHECK_EXCHANGE,
    "dealer": DEALER_DESK,
    "zero": ZERO_COST,
}


def breakeven_move(cost: CostModel, order_type: OrderType = OrderType.TAKER) -> float:
    """損益分岐に必要な値幅（率）。

    往復コストをちょうど取り返すのに必要な価格変動。
    「1回の取引でこれだけ動かないと、勝っても手数料負けする」という下限。
    """
    return cost.round_trip_rate(order_type)


def required_daily_return(target_yen_per_day: float, capital_yen: float) -> float:
    """1日あたり目標金額を、元本に対する日次リターン率に変換する。

    「1日500円」という目標は、元本とセットでないと意味を持たない。
    元本10万円なら0.5%/日（年125%ペース）、
    元本100万円なら0.05%/日（年12.5%ペース）で、難易度がまったく違う。
    """
    if capital_yen <= 0:
        raise ValueError("元本は正の値である必要があります")
    return target_yen_per_day / capital_yen
