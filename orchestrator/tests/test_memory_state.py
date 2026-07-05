import pytest

from orchestrator.memory import MemoryStore
from orchestrator.state import CostLimitExceeded, StateManager


def test_memory_best_model_prefers_quality(tmp_path):
    m = MemoryStore(tmp_path / "ep.json")
    for _ in range(3):
        m.store_episode(
            task_type="code", description="実装", model="claude-sonnet-5",
            success=True, quality_score=0.9, cost_usd=0.05,
        )
    m.store_episode(
        task_type="code", description="実装", model="claude-haiku-4-5",
        success=False, quality_score=0.3, cost_usd=0.01,
    )
    best = m.best_model_for_type("code")
    assert best["model"] == "claude-sonnet-5"
    assert best["samples"] == 3
    assert best["success_rate"] == 1.0


def test_memory_persists_across_instances(tmp_path):
    path = tmp_path / "ep.json"
    MemoryStore(path).store_episode(
        task_type="writing", description="記事執筆", model="claude-sonnet-5",
        success=True, quality_score=0.9, cost_usd=0.02,
    )
    assert MemoryStore(path).count_similar_successes("writing") == 1


def test_find_similar_matches_japanese(tmp_path):
    m = MemoryStore(tmp_path / "ep.json")
    m.store_episode(
        task_type="analysis", description="競合他社のSNS戦略を分析",
        model="claude-sonnet-5", success=True, quality_score=0.92, cost_usd=0.1,
    )
    hits = m.find_similar("SNS戦略の分析をやり直す")
    assert len(hits) == 1


def test_state_checkpoint_and_resume(tmp_path):
    s = StateManager("sess1", goal="テスト", directory=tmp_path)
    s.checkpoint("phase_1", {"items": ["a", "b"]})
    s.checkpoint("phase_2", {"partial": "x"})

    # 再開: 同じ session_id で作り直すと状態が戻る
    s2 = StateManager("sess1", directory=tmp_path)
    assert s2.completed_phases() == ["phase_1", "phase_2"]
    assert s2.resume_data("phase_1") == {"items": ["a", "b"]}
    assert (tmp_path / "STATE.md").read_text().startswith("# STATE.md")


def test_cost_limit_enforced(tmp_path):
    s = StateManager("sess2", budget_usd=0.01, directory=tmp_path)
    with pytest.raises(CostLimitExceeded):
        # opus 4.8: 1M in = $5 → 楽々上限超え
        s.track_cost("claude-opus-4-8", 1_000_000, 0)
    assert s.state["status"] == "halted_cost_limit"


def test_cost_accumulates(tmp_path):
    s = StateManager("sess3", budget_usd=100.0, directory=tmp_path)
    s.track_cost("claude-haiku-4-5", 10_000, 5_000)
    # $1/M * 10k + $5/M * 5k = 0.01 + 0.025
    assert s.total_cost == pytest.approx(0.035)
