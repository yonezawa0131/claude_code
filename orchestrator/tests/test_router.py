from orchestrator.models import CATALOG
from orchestrator.router import Complexity, Router, Task


def test_simple_task_routes_to_haiku():
    d = Router().route(Task(description="この文章を要約してください"))
    assert d.model == "claude-haiku-4-5"
    assert d.complexity == Complexity.SIMPLE
    assert d.effort is None  # Haiku は effort 非対応


def test_analysis_routes_to_sonnet():
    d = Router().route(Task(description="競合5社のSNS運用を分析して比較する"))
    assert d.model == "claude-sonnet-5"
    assert d.task_type == "analysis"


def test_architecture_routes_to_opus():
    d = Router().route(Task(description="決済システムのアーキテクチャを設計する"))
    assert d.model == "claude-opus-4-8"
    assert d.effort == "high"


def test_verification_always_haiku():
    d = Router().route(
        Task(description="本番リリース前の最終レビュー", task_type="verification")
    )
    assert d.model == "claude-haiku-4-5"


def test_maximum_quality_routes_to_fable():
    d = Router().route(
        Task(description="簡単な変換タスク", required_quality="maximum")
    )
    assert d.model == "claude-fable-5"


def test_budget_constraint_downgrades():
    # opus 相当のタスクに極小予算 → 安いモデルへ
    d = Router().route(
        Task(
            description="大規模な戦略設計",
            budget_usd=0.001,
            estimated_tokens=100_000,
        )
    )
    assert d.model == "claude-haiku-4-5"
    assert "ダウングレード" in d.reasoning


def test_all_routed_models_exist_in_catalog():
    for desc in ["要約して", "分析して", "設計して", "整形して"]:
        d = Router().route(Task(description=desc))
        assert d.model in CATALOG


def test_learned_preference_overrides_default(tmp_path):
    from orchestrator.memory import MemoryStore

    memory = MemoryStore(tmp_path / "ep.json")
    for _ in range(3):
        memory.store_episode(
            task_type="analysis",
            description="市場分析",
            model="claude-haiku-4-5",
            success=True,
            quality_score=0.95,
            cost_usd=0.01,
        )
    d = Router(memory).route(Task(description="新しい市場を分析する"))
    assert d.model == "claude-haiku-4-5"
    assert "実績" in d.reasoning
