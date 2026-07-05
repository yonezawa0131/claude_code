"""モデルカタログと価格。

価格・モデルIDの出典: platform.claude.com モデル一覧(2026-06-24 時点キャッシュ)。
架空のモデルは登録しない。価格改定時はこのファイルだけを更新する。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    input_per_mtok: float   # USD / 1M input tokens
    output_per_mtok: float  # USD / 1M output tokens
    context_window: int
    max_output: int
    supports_effort: bool   # output_config.effort が使えるか
    tier: int               # 1=最安 → 4=最高性能


CATALOG: dict[str, ModelInfo] = {
    m.id: m
    for m in [
        ModelInfo(
            id="claude-haiku-4-5",
            display_name="Claude Haiku 4.5",
            input_per_mtok=1.00,
            output_per_mtok=5.00,
            context_window=200_000,
            max_output=64_000,
            supports_effort=False,
            tier=1,
        ),
        ModelInfo(
            id="claude-sonnet-5",
            display_name="Claude Sonnet 5",
            # 定価。2026-08-31 まで導入価格 $2/$10 が適用される
            input_per_mtok=3.00,
            output_per_mtok=15.00,
            context_window=1_000_000,
            max_output=128_000,
            supports_effort=True,
            tier=2,
        ),
        ModelInfo(
            id="claude-opus-4-8",
            display_name="Claude Opus 4.8",
            input_per_mtok=5.00,
            output_per_mtok=25.00,
            context_window=1_000_000,
            max_output=128_000,
            supports_effort=True,
            tier=3,
        ),
        ModelInfo(
            id="claude-fable-5",
            display_name="Claude Fable 5",
            input_per_mtok=10.00,
            output_per_mtok=50.00,
            context_window=1_000_000,
            max_output=128_000,
            supports_effort=True,
            tier=4,
        ),
    ]
}

# ティア順(安い → 高い)。予算制約でのステップダウンに使う
TIER_ORDER = sorted(CATALOG.values(), key=lambda m: m.tier)


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    m = CATALOG[model_id]
    cost = (
        input_tokens / 1_000_000 * m.input_per_mtok
        + output_tokens / 1_000_000 * m.output_per_mtok
    )
    return round(cost, 6)


def cheaper_alternative(model_id: str) -> str | None:
    """1ティア安いモデルを返す。最安なら None。"""
    current = CATALOG[model_id]
    candidates = [m for m in TIER_ORDER if m.tier < current.tier]
    return candidates[-1].id if candidates else None
