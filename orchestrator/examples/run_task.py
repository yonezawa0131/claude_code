"""オーケストレーターのデモ。

API キーなし: ルーティング判断だけを表示するドライラン。
API キーあり(ANTHROPIC_API_KEY): 実際に実行 → 検証 → 必要なら自動改善。

使い方:
    python3 examples/run_task.py "競合3社のSNS戦略を分析して"
    python3 examples/run_task.py --budget 0.50 "この記事を要約して: ..."
"""

import argparse
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator import (
    AnthropicProvider,
    ExecutionLoop,
    MemoryStore,
    Router,
    StateManager,
    Task,
    VerificationEngine,
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("description", help="タスクの内容")
    parser.add_argument("--budget", type=float, default=1.0, help="タスク予算(USD)")
    parser.add_argument("--quality", default="standard",
                        choices=["standard", "high", "critical", "maximum"])
    args = parser.parse_args()

    memory = MemoryStore(".orchestrator/episodes.json")
    router = Router(memory)
    task = Task(
        description=args.description,
        required_quality=args.quality,
        budget_usd=args.budget,
    )

    decision = router.route(task)
    print("── ルーティング判断 ──────────────────")
    print(f"  モデル:   {decision.model} (effort={decision.effort})")
    print(f"  複雑度:   {decision.complexity.name} / 種別: {decision.task_type}")
    print(f"  見積り:   ${decision.estimated_cost_usd}")
    print(f"  理由:     {decision.reasoning}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nANTHROPIC_API_KEY が未設定のためドライランで終了します。")
        return

    state = StateManager(
        f"demo_{uuid.uuid4().hex[:8]}",
        goal=args.description,
        budget_usd=args.budget,
    )
    provider = AnthropicProvider()
    loop = ExecutionLoop(
        provider=provider,
        router=router,
        verifier=VerificationEngine(provider),
        state=state,
        memory=memory,
    )

    result = await loop.run(task)

    print("\n── 実行結果 ──────────────────────────")
    print(f"  ステータス: {result.status}")
    print(f"  試行回数:   {result.attempts}")
    print(f"  品質スコア: {result.final_score}")
    print(f"  コスト:     ${result.cost_usd}")
    print(f"\n{result.output}")


if __name__ == "__main__":
    asyncio.run(main())
