import pytest

from orchestrator.loop import ExecutionLoop
from orchestrator.memory import MemoryStore
from orchestrator.router import Router, Task
from orchestrator.state import StateManager
from orchestrator.verification import VerificationEngine


def build_loop(fake_provider, tmp_path, budget=10.0, max_retries=3):
    memory = MemoryStore(tmp_path / "ep.json")
    state = StateManager("t", budget_usd=budget, directory=tmp_path)
    return ExecutionLoop(
        provider=fake_provider,
        router=Router(memory),
        verifier=VerificationEngine(fake_provider),
        state=state,
        memory=memory,
        max_retries=max_retries,
    ), memory, state


@pytest.mark.asyncio
async def test_success_first_attempt(fake_provider, tmp_path):
    loop, memory, state = build_loop(fake_provider, tmp_path)
    fake_provider.executor_responses = ["良い分析結果です"]
    fake_provider.verifier_scores = [{}]  # 全基準 1.0 → 合格

    result = await loop.run(Task(description="市場を分析して", task_type="analysis"))

    assert result.status == "success"
    assert result.attempts == 1
    assert result.output == "良い分析結果です"
    assert result.final_score == 1.0
    assert memory.count_similar_successes("analysis") == 1
    assert state.total_cost > 0


@pytest.mark.asyncio
async def test_retry_with_improvement_then_success(fake_provider, tmp_path):
    loop, _, _ = build_loop(fake_provider, tmp_path)
    fake_provider.executor_responses = ["雑な出力", "改善された出力"]
    fake_provider.verifier_scores = [
        {"factual_accuracy": 0.2, "logical_consistency": 0.3,
         "completeness": 0.2, "actionability": 0.2},  # 不合格
        {},  # 合格
    ]

    result = await loop.run(Task(description="データを分析する", task_type="analysis"))

    assert result.status == "success"
    assert result.attempts == 2
    assert result.output == "改善された出力"
    # 2回目の実行者呼び出しには改善指示が注入されている
    executor_calls = [c for c in fake_provider.calls if not c["is_verifier"]]
    assert len(executor_calls) == 2
    second_messages = executor_calls[1]["messages"]
    assert any("修正してください" in str(m.get("content")) for m in second_messages)


@pytest.mark.asyncio
async def test_escalates_after_max_retries(fake_provider, tmp_path):
    loop, memory, _ = build_loop(fake_provider, tmp_path, max_retries=2)
    low = {"factual_accuracy": 0.1, "logical_consistency": 0.1,
           "completeness": 0.1, "actionability": 0.1}
    fake_provider.executor_responses = ["だめ1", "だめ2"]
    fake_provider.verifier_scores = [low, dict(low, factual_accuracy=0.5)]

    result = await loop.run(Task(description="難しい分析", task_type="analysis"))

    assert result.status == "escalate"
    assert result.attempts == 2
    assert result.output == "だめ2"  # ベストスコアの出力を返す
    # 失敗もエピソードとして記録される(失敗は資産)
    assert memory.best_model_for_type("analysis")["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_verifier_uses_different_model(fake_provider, tmp_path):
    loop, _, _ = build_loop(fake_provider, tmp_path)
    fake_provider.executor_responses = ["設計書です"]
    fake_provider.verifier_scores = [{}]

    await loop.run(Task(description="システムのアーキテクチャを設計する"))

    executor = [c for c in fake_provider.calls if not c["is_verifier"]][0]
    verifier = [c for c in fake_provider.calls if c["is_verifier"]][0]
    assert executor["model"] == "claude-opus-4-8"
    assert verifier["model"] == "claude-haiku-4-5"
    assert executor["model"] != verifier["model"]
