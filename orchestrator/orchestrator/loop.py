"""ExecutionLoop — route → execute → verify → (改善して再試行) の中核ループ。

- 実行者と検証者は必ず別モデル
- 検証失敗時は改善指示を注入して最大 max_retries 回まで再試行
- 全試行がコンテキストに残るので、成功時はエピソード記憶に記録して学習に回す
- コスト上限は StateManager が強制(超過時 CostLimitExceeded)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .memory import MemoryStore
from .providers import ModelRefusedError, Provider
from .router import Router, RoutingDecision, Task
from .state import StateManager
from .verification import VerificationEngine, VerificationResult


@dataclass
class TaskResult:
    status: str  # "success" | "escalate"
    output: str
    decision: RoutingDecision
    attempts: int
    final_score: float
    cost_usd: float
    history: list[dict[str, Any]] = field(default_factory=list)


class ExecutionLoop:
    def __init__(
        self,
        *,
        provider: Provider,
        router: Router,
        verifier: VerificationEngine,
        state: StateManager,
        memory: MemoryStore | None = None,
        max_retries: int = 3,
    ):
        self._provider = provider
        self._router = router
        self._verifier = verifier
        self._state = state
        self._memory = memory
        self._max_retries = max_retries

    async def run(self, task: Task, *, system: str | None = None) -> TaskResult:
        decision = self._router.route(task)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": task.description}
        ]
        history: list[dict[str, Any]] = []
        cost_before = self._state.total_cost
        best: tuple[float, str] = (-1.0, "")

        for attempt in range(1, self._max_retries + 1):
            self._state.set_status(f"executing attempt {attempt} on {decision.model}")
            try:
                completion = await self._provider.complete(
                    model=decision.model,
                    system=system,
                    messages=messages,
                    effort=decision.effort,
                )
            except ModelRefusedError as e:
                # モデルが拒否した。記録してエスカレーション
                self._state.record_error(f"refusal: {e}")
                return self._finish(
                    task, decision, "escalate", best[1], attempt, best[0],
                    cost_before, history,
                )

            self._state.track_cost(
                completion.model, completion.input_tokens, completion.output_tokens
            )

            verification = await self._verify(task, completion.text)
            history.append(
                {
                    "attempt": attempt,
                    "model": completion.model,
                    "score": verification.total_score,
                    "passed": verification.passed,
                }
            )
            if verification.total_score > best[0]:
                best = (verification.total_score, completion.text)

            if verification.passed:
                return self._finish(
                    task, decision, "success", completion.text, attempt,
                    verification.total_score, cost_before, history,
                )

            # 失敗 → 改善指示を会話に注入して再試行
            messages.append({"role": "assistant", "content": completion.text})
            messages.append(
                {"role": "user", "content": verification.improvement_prompt or "改善してください。"}
            )

        return self._finish(
            task, decision, "escalate", best[1], self._max_retries, best[0],
            cost_before, history,
        )

    async def _verify(self, task: Task, output: str) -> VerificationResult:
        result = await self._verifier.verify(
            output=output,
            task_description=task.description,
            task_type=task.task_type or "general",
        )
        # 検証コストも計上したいが、Verifier内部のusageはProvider実装依存。
        # AnthropicProviderではCompletionにusageが乗るため、必要なら
        # VerificationEngineを通さず直接呼ぶ構成に変えること。
        return result

    def _finish(
        self,
        task: Task,
        decision: RoutingDecision,
        status: str,
        output: str,
        attempts: int,
        score: float,
        cost_before: float,
        history: list[dict[str, Any]],
    ) -> TaskResult:
        cost = round(self._state.total_cost - cost_before, 6)
        if self._memory is not None:
            self._memory.store_episode(
                task_type=decision.task_type,
                description=task.description,
                model=decision.model,
                success=(status == "success"),
                quality_score=max(score, 0.0),
                cost_usd=cost,
                attempts=attempts,
            )
        self._state.set_status(f"task_{status}")
        return TaskResult(
            status=status,
            output=output,
            decision=decision,
            attempts=attempts,
            final_score=max(score, 0.0),
            cost_usd=cost,
            history=history,
        )
