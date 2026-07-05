"""Verification Engine — 実行者と別のモデルで出力品質を検証する。

structured outputs (output_config.format) を使うので、検証結果は
常に有効な JSON で返る。既定の検証者は claude-haiku-4-5(最安)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .providers import Provider

VERIFIER_MODEL = "claude-haiku-4-5"
PASS_THRESHOLD = 0.85

# タスク種別ごとの検証基準(名前, 重み)。重みは合計1.0
CRITERIA_SETS: dict[str, list[tuple[str, float]]] = {
    "code": [
        ("logic_correctness", 0.4),
        ("completeness", 0.3),
        ("security", 0.2),
        ("readability", 0.1),
    ],
    "analysis": [
        ("factual_accuracy", 0.35),
        ("logical_consistency", 0.30),
        ("completeness", 0.20),
        ("actionability", 0.15),
    ],
    "writing": [
        ("key_points_covered", 0.40),
        ("tone_appropriate", 0.25),
        ("grammar_correct", 0.20),
        ("length_appropriate", 0.15),
    ],
    "general": [
        ("instruction_followed", 0.5),
        ("logical_consistency", 0.3),
        ("completeness", 0.2),
    ],
}

_VERIFIER_SYSTEM = """あなたは出力品質の検証者です。他のAIの出力を客観的に評価します。

原則:
- 感情ではなく基準に対する達成度で評価する
- 各基準に 0.0〜1.0 のスコアをつけ、問題点は具体的に書く
- 改善指示は「何をどう直すか」まで具体的に書く。抽象的な指摘は不可"""


def _verifier_schema(criteria: list[tuple[str, float]]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "object",
                "properties": {
                    name: {
                        "type": "object",
                        "properties": {
                            "score": {"type": "number"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["score", "issues"],
                        "additionalProperties": False,
                    }
                    for name, _ in criteria
                },
                "required": [name for name, _ in criteria],
                "additionalProperties": False,
            },
            "improvement_instructions": {"type": "string"},
        },
        "required": ["criteria", "improvement_instructions"],
        "additionalProperties": False,
    }


@dataclass
class VerificationResult:
    passed: bool
    total_score: float
    criteria_scores: dict[str, float]
    issues: dict[str, list[str]]
    improvement_prompt: str | None


class VerificationEngine:
    def __init__(self, provider: Provider, model: str = VERIFIER_MODEL):
        self._provider = provider
        self._model = model

    async def verify(
        self, *, output: str, task_description: str, task_type: str = "general"
    ) -> VerificationResult:
        import json

        criteria = CRITERIA_SETS.get(task_type, CRITERIA_SETS["general"])
        prompt = f"""以下の出力を検証してください。

【元のタスク】
{task_description}

【評価基準】
{", ".join(name for name, _ in criteria)}

【検証対象の出力】
{output[:8000]}"""

        completion = await self._provider.complete(
            model=self._model,
            system=_VERIFIER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2_000,
            output_schema=_verifier_schema(criteria),
        )
        data = json.loads(completion.text)

        scores: dict[str, float] = {}
        issues: dict[str, list[str]] = {}
        total = 0.0
        for name, weight in criteria:
            entry = data["criteria"][name]
            score = max(0.0, min(1.0, float(entry["score"])))
            scores[name] = score
            issues[name] = list(entry.get("issues", []))
            total += score * weight

        passed = total >= PASS_THRESHOLD
        improvement = None
        if not passed:
            failed = [
                f"- {name}: {scores[name]:.2f} — {'; '.join(issues[name]) or '基準未達'}"
                for name, _ in criteria
                if scores[name] < PASS_THRESHOLD
            ]
            improvement = (
                "前回の出力は品質基準を満たしませんでした。以下を修正してください。\n\n"
                + "\n".join(failed)
                + f"\n\n検証者からの指示:\n{data['improvement_instructions']}"
            )

        return VerificationResult(
            passed=passed,
            total_score=round(total, 3),
            criteria_scores=scores,
            issues=issues,
            improvement_prompt=improvement,
        )
