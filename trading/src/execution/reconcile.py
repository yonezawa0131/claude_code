"""目標と現在の保有から、出すべき注文を作る。

## 差分だけを出す

戦略が決めるのは「どの銘柄をいくら分持つべきか」（目標）だけにする。
注文はそこから機械的に導く。

    注文 = 目標 − 現在

この形にすると、**二重発注が構造的に起きない**。
同じ処理を2回走らせても、1回目で目標に到達していれば2回目の差分はゼロになる。
プロセスが途中で落ちても、次に動いたときは正しい現在地から差分を取り直す。

「前回何を出したか」を覚えておいて、その続きをやる設計にすると、
記憶と実際がずれた瞬間に壊れる。**覚えない設計のほうが強い。**

## 小さすぎる差分は出さない

目標と現在が 0.1% ずれているからといって注文を出すと、
コストばかり払って何も変わらない。

この基盤で繰り返し測ってきたとおり、**動くこと自体にコストがかかる**。
だから閾値を置いて、意味のある差だけを動かす。
"""

from __future__ import annotations

from dataclasses import dataclass

from .broker import Order


@dataclass(frozen=True)
class TargetPortfolio:
    """持つべき状態。

    weights は「総資産に対する比率」で持つ。金額ではなく比率にするのは、
    資産が増減しても同じ指示が使えるようにするため。
    合計が1未満なら、残りは現金になる。
    """

    #: 銘柄 -> 総資産に対する比率
    weights: dict[str, float]
    #: 建値に使う通貨
    quote: str = "jpy"

    def __post_init__(self) -> None:
        for pair, w in self.weights.items():
            if w < 0:
                raise ValueError(
                    f"{pair} の比率が負です。この基盤は現物のみで、売り建てを扱いません"
                )
        total = sum(self.weights.values())
        if total > 1.0 + 1e-9:
            raise ValueError(
                f"比率の合計が {total:.3f} です。1.0 を超える指示は"
                "レバレッジになるため受け付けません"
            )


def current_weights(
    balances: dict[str, float], prices: dict[str, float], quote: str = "jpy"
) -> tuple[dict[str, float], float]:
    """保有量と価格から、現在の比率と総資産（円）を出す。

    戻り値は (銘柄 -> 比率, 総資産)。
    価格が取れない銘柄は**総資産に数えない**。
    分からないものを勝手に評価すると、比率の計算全体が狂う。
    """
    equity = float(balances.get(quote, 0.0))
    values: dict[str, float] = {}
    for pair, price in prices.items():
        base = pair.split("_")[0]
        amount = float(balances.get(base, 0.0))
        if amount > 0 and price > 0:
            values[pair] = amount * price
            equity += values[pair]

    if equity <= 0:
        return {}, 0.0
    return {pair: value / equity for pair, value in values.items()}, equity


def build_orders(
    target: TargetPortfolio,
    balances: dict[str, float],
    prices: dict[str, float],
    min_trade_jpy: float = 2_000.0,
    limit_offset: float | None = 0.0005,
) -> tuple[list[Order], float]:
    """目標と現在の差分から注文を作る。

    Parameters
    ----------
    min_trade_jpy:
        この金額に満たない差分は動かさない。
        小さな差を追いかけるとコストだけが増える
    limit_offset:
        指値を現在値からどれだけ有利側に置くか。
        None なら成行。**既定は指値**にしてある。
        週次のような入れ替えなら約定を待つ時間があり、
        この基盤の測定では往復コストが 0.18% からほぼ0まで下がる

    Returns
    -------
    (注文のリスト, 現在の総資産)
    """
    current, equity = current_weights(balances, prices, target.quote)
    if equity <= 0:
        return [], 0.0

    orders: list[Order] = []
    pairs = set(target.weights) | set(current)

    for pair in sorted(pairs):
        price = prices.get(pair)
        if price is None or price <= 0:
            continue  # 価格が取れないものは動かさない

        want = target.weights.get(pair, 0.0) * equity
        have = current.get(pair, 0.0) * equity
        diff = want - have

        if abs(diff) < min_trade_jpy:
            continue

        side = "buy" if diff > 0 else "sell"
        amount = abs(diff) / price
        if limit_offset is None:
            limit = None
        else:
            # 買いは下、売りは上に置く。板に並べて待つ
            limit = price * (1 - limit_offset) if side == "buy" else price * (1 + limit_offset)
        orders.append(Order(pair=pair, side=side, amount=amount, price=limit))

    # 売ってから買う。現金が足りずに買えない事態を避ける
    orders.sort(key=lambda o: 0 if o.side == "sell" else 1)
    return orders, equity


def exposure_jpy(balances: dict[str, float], prices: dict[str, float]) -> float:
    """現金以外の評価額の合計（円）。"""
    total = 0.0
    for pair, price in prices.items():
        base = pair.split("_")[0]
        amount = float(balances.get(base, 0.0))
        if amount > 0 and price > 0:
            total += amount * price
    return total
