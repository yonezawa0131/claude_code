"""Router — タスクの複雑度・種別・予算から最適なモデルを選ぶ。

過去実行(MemoryStore)から学習したモデル選好があればそれを優先する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from .models import CATALOG, cheaper_alternative, estimate_cost

if TYPE_CHECKING:
    from .memory import MemoryStore


class Complexity(IntEnum):
    TRIVIAL = 1
    SIMPLE = 2
    MODERATE = 3
    COMPLEX = 4
    CRITICAL = 5


@dataclass
class Task:
    description: str
    task_type: str | None = None       # code / analysis / writing / planning / verification
    required_quality: str = "standard"  # standard / high / critical / maximum
    budget_usd: float | None = None     # このタスク単体の上限
    estimated_tokens: int = 4_000
    context: dict = field(default_factory=dict)


@dataclass
class RoutingDecision:
    model: str
    complexity: Complexity
    task_type: str
    effort: str | None
    estimated_cost_usd: float
    reasoning: str


_COMPLEXITY_PATTERNS: list[tuple[Complexity, list[str]]] = [
    # 上から順に強い判定。先にマッチした複雑度を採用する
    (Complexity.CRITICAL, [r"最高品質", r"本番", r"納品", r"critical", r"production"]),
    (Complexity.COMPLEX, [r"設計", r"アーキテクチャ", r"戦略", r"リファクタ", r"design", r"architect", r"strategy", r"refactor"]),
    (Complexity.MODERATE, [r"分析", r"比較", r"調査", r"analyz", r"compar", r"evaluat", r"research"]),
    (Complexity.SIMPLE, [r"要約", r"分類", r"翻訳", r"summariz", r"classif", r"translat"]),
    (Complexity.TRIVIAL, [r"整形", r"変換", r"format", r"convert"]),
]

_TYPE_PATTERNS: dict[str, list[str]] = {
    "verification": [r"検証", r"レビュー", r"チェック", r"verif", r"review", r"check"],
    "code": [r"コード", r"実装", r"スクリプト", r"バグ", r"code", r"implement", r"script", r"debug"],
    "planning": [r"計画", r"分解", r"タスク設計", r"plan", r"decompos", r"break.?down"],
    "writing": [r"執筆", r"記事", r"文章", r"レポート作成", r"writ", r"draft", r"article"],
    "analysis": [r"分析", r"調査", r"比較", r"analyz", r"research", r"compar"],
}

# 複雑度 → 既定モデル。CRITICAL でも既定は Opus 4.8。
# claude-fable-5 (Opus の2倍の単価) は required_quality="maximum" の明示指定のみ。
_MODEL_BY_COMPLEXITY: dict[Complexity, str] = {
    Complexity.TRIVIAL: "claude-haiku-4-5",
    Complexity.SIMPLE: "claude-haiku-4-5",
    Complexity.MODERATE: "claude-sonnet-5",
    Complexity.COMPLEX: "claude-opus-4-8",
    Complexity.CRITICAL: "claude-opus-4-8",
}

_EFFORT_BY_COMPLEXITY: dict[Complexity, str | None] = {
    Complexity.TRIVIAL: "low",
    Complexity.SIMPLE: "low",
    Complexity.MODERATE: "medium",
    Complexity.COMPLEX: "high",
    Complexity.CRITICAL: "xhigh",
}


class Router:
    # 記憶からの選好を採用する最低ライン
    MIN_LEARNED_SUCCESS_RATE = 0.9
    MIN_LEARNED_SAMPLES = 3

    def __init__(self, memory: "MemoryStore | None" = None):
        self._memory = memory

    def route(self, task: Task) -> RoutingDecision:
        complexity = self._estimate_complexity(task)
        task_type = task.task_type or self._detect_task_type(task.description)

        model, why = self._select_model(task, complexity, task_type)

        # 予算制約: 見積りが上限を超えるなら安いティアへ下げる
        est = self._estimate(model, task.estimated_tokens)
        while task.budget_usd is not None and est > task.budget_usd:
            cheaper = cheaper_alternative(model)
            if cheaper is None:
                break
            model = cheaper
            why += f" / 予算${task.budget_usd}のため{model}へダウングレード"
            est = self._estimate(model, task.estimated_tokens)

        effort = _EFFORT_BY_COMPLEXITY[complexity] if CATALOG[model].supports_effort else None
        return RoutingDecision(
            model=model,
            complexity=complexity,
            task_type=task_type,
            effort=effort,
            estimated_cost_usd=est,
            reasoning=f"type={task_type}, complexity={complexity.name}: {why}",
        )

    def _select_model(self, task: Task, complexity: Complexity, task_type: str) -> tuple[str, str]:
        # 明示的な最高品質指定のみ Fable 5
        if task.required_quality == "maximum":
            return "claude-fable-5", "required_quality=maximum の明示指定"

        # 検証タスクは常に最安モデル(実行者と別モデルにする意味もある)
        if task_type == "verification":
            return "claude-haiku-4-5", "検証タスクは低コストモデルで十分"

        # 過去実績からの学習(エピソード記憶)
        if self._memory is not None:
            learned = self._memory.best_model_for_type(task_type)
            if (
                learned is not None
                and learned["samples"] >= self.MIN_LEARNED_SAMPLES
                and learned["success_rate"] >= self.MIN_LEARNED_SUCCESS_RATE
                and learned["model"] in CATALOG
            ):
                return learned["model"], (
                    f"過去{learned['samples']}件で成功率{learned['success_rate']:.0%}の実績"
                )

        model = _MODEL_BY_COMPLEXITY[complexity]
        if task.required_quality in ("high", "critical") and CATALOG[model].tier < CATALOG["claude-opus-4-8"].tier:
            model = "claude-opus-4-8"
            return model, "required_quality指定により上位モデルへ"
        return model, "複雑度からの既定マッピング"

    @staticmethod
    def _estimate(model: str, total_tokens: int) -> float:
        # 入力7:出力3 の比率で概算(実測はStateManagerが行う)
        return estimate_cost(model, int(total_tokens * 0.7), int(total_tokens * 0.3))

    @staticmethod
    def _estimate_complexity(task: Task) -> Complexity:
        if task.required_quality == "critical":
            return Complexity.CRITICAL
        for complexity, patterns in _COMPLEXITY_PATTERNS:
            if any(re.search(p, task.description, re.IGNORECASE) for p in patterns):
                return complexity
        return Complexity.MODERATE

    @staticmethod
    def _detect_task_type(description: str) -> str:
        for task_type, patterns in _TYPE_PATTERNS.items():
            if any(re.search(p, description, re.IGNORECASE) for p in patterns):
                return task_type
        return "general"
