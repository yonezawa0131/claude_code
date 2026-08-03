"""本番で動かす前に通す関門。

## なぜドキュメントではなくコードなのか

「検証してから使うこと」「上限を守ること」を注意書きに書いても、守られない。
守られないことを前提に、**コードが拒否する**形にする。

このプロジェクトで測ってきたことを踏まえると、最も危ないのは
「優位性のない戦略を、自動で、休みなく実行すること」になる。
手で回していれば途中で疑うが、自動化するとその機会がなくなる。

実データで測った5戦略は、元本30万円で平均11.5万円を失う成績だった。
自動化していれば、その損失は確実に、正確に、休みなく実現していた。

**だから第一の関門は「この戦略は検証を通ったか」になる。**
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from .broker import Order


@dataclass(frozen=True)
class Violation:
    """関門に引っかかった内容。"""

    rule: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.detail}"


@dataclass(frozen=True)
class Limits:
    """本番で許す範囲。

    既定値は**わざと小さくしてある**。
    大きくするのは、小さい額で動くことを確かめてからにすること。
    """

    #: 1回の実行で動かせる金額の上限（円）
    max_notional_per_run: float = 50_000.0
    #: 1注文の上限（円）
    max_notional_per_order: float = 20_000.0
    #: 建てられる総額の上限（円）
    max_total_exposure: float = 100_000.0
    #: 初期資金からこの率まで減ったら止める
    max_drawdown: float = 0.20
    #: 検証の合格記録が、この日数より古ければ本番を認めない
    validation_max_age_days: int = 90
    #: 1回の実行で出せる注文数の上限。暴走の歯止め
    max_orders_per_run: int = 20

    def __post_init__(self) -> None:
        if self.max_notional_per_order > self.max_notional_per_run:
            raise ValueError("1注文の上限が、1回の実行の上限を超えています")
        if not 0 < self.max_drawdown < 1:
            raise ValueError("max_drawdown は0と1の間である必要があります")


@dataclass
class ValidationRecord:
    """事前登録した検定の結果。本番の前提になる。"""

    strategy: str
    passed: bool
    date: dt.date
    script: str
    note: str = ""

    @classmethod
    def load(cls, path: Path) -> ValidationRecord:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return cls(
            strategy=raw["strategy"],
            passed=bool(raw["passed"]),
            date=dt.date.fromisoformat(raw["date"]),
            script=raw.get("script", "unknown"),
            note=raw.get("note", ""),
        )

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "strategy": self.strategy,
                    "passed": self.passed,
                    "date": self.date.isoformat(),
                    "script": self.script,
                    "note": self.note,
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )


@dataclass
class GuardContext:
    """関門が判断に使う材料。"""

    strategy: str
    orders: list[Order]
    prices: dict[str, float]
    #: 現在の総資産（円換算）
    equity: float
    #: 運用開始時の資産（円）
    initial_equity: float
    #: 建玉の合計（円換算）。現金を除く
    exposure: float
    limits: Limits = field(default_factory=Limits)
    validation: ValidationRecord | None = None
    today: dt.date = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).date())


def check(context: GuardContext) -> list[Violation]:
    """本番で動かしてよいかを判定する。空リストなら通過。"""
    v: list[Violation] = []

    # --- 1. 検証を通っているか ------------------------------------------
    record = context.validation
    if record is None:
        v.append(Violation(
            "未検証",
            f"戦略「{context.strategy}」の検証記録がありません。"
            "事前登録した検定を通してから本番にしてください",
        ))
    else:
        if record.strategy != context.strategy:
            v.append(Violation(
                "検証の不一致",
                f"検証記録は「{record.strategy}」のものです"
                f"（動かそうとしているのは「{context.strategy}」）",
            ))
        if not record.passed:
            v.append(Violation(
                "検証で不合格",
                f"「{record.strategy}」は {record.script} で不合格でした。"
                "**優位性のない戦略を自動化すると、損失が確実に実現します**",
            ))
        age = (context.today - record.date).days
        if age > context.limits.validation_max_age_days:
            v.append(Violation(
                "検証が古い",
                f"検証から {age} 日経っています"
                f"（上限 {context.limits.validation_max_age_days} 日）。"
                "優位性は消えます。測り直してください",
            ))

    # --- 2. 損失の上限 ---------------------------------------------------
    if context.initial_equity > 0:
        drawdown = 1.0 - context.equity / context.initial_equity
        if drawdown >= context.limits.max_drawdown:
            v.append(Violation(
                "損失の上限",
                f"開始時から {drawdown * 100:.1f}% 減っています"
                f"（上限 {context.limits.max_drawdown * 100:.0f}%）。"
                "止めて、原因を確かめてください",
            ))

    # --- 3. 注文の大きさと数 ---------------------------------------------
    if len(context.orders) > context.limits.max_orders_per_run:
        v.append(Violation(
            "注文数",
            f"{len(context.orders)} 件は多すぎます"
            f"（上限 {context.limits.max_orders_per_run} 件）",
        ))

    total = 0.0
    for order in context.orders:
        price = context.prices.get(order.pair)
        if price is None or price <= 0:
            v.append(Violation("価格不明", f"{order.pair} の価格が取れていません"))
            continue
        notional = order.notional(price)
        total += notional
        if notional > context.limits.max_notional_per_order:
            v.append(Violation(
                "1注文の上限",
                f"{order.pair} {order.side} {notional:,.0f} 円は上限"
                f"{context.limits.max_notional_per_order:,.0f} 円を超えます",
            ))

    if total > context.limits.max_notional_per_run:
        v.append(Violation(
            "1回の実行の上限",
            f"合計 {total:,.0f} 円は上限 "
            f"{context.limits.max_notional_per_run:,.0f} 円を超えます",
        ))

    # --- 4. 建玉の総額 ---------------------------------------------------
    buy_side = sum(
        o.notional(context.prices.get(o.pair, 0.0)) for o in context.orders if o.side == "buy"
    )
    if context.exposure + buy_side > context.limits.max_total_exposure:
        v.append(Violation(
            "建玉の上限",
            f"実行後の建玉 {context.exposure + buy_side:,.0f} 円は上限 "
            f"{context.limits.max_total_exposure:,.0f} 円を超えます",
        ))

    return v


def describe(violations: list[Violation]) -> str:
    if not violations:
        return "すべての関門を通過しました。"
    lines = [f"**{len(violations)} 件の関門で止まりました。本番では実行しません。**", ""]
    lines += [f"  - {v}" for v in violations]
    return "\n".join(lines)
