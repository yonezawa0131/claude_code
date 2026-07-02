"""adops.planner.build_plan のテスト。

実際の config/benchmarks.yaml とサンプル order（campaigns/*/order.yaml）を使う。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from adops import io, planner

REPO_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS_DIR = REPO_ROOT / "campaigns"

COSME_DIR = CAMPAIGNS_DIR / "2026-08_sample-cosme"
DRINK_DIR = CAMPAIGNS_DIR / "2026-06_sample-drink"


@pytest.fixture(scope="module")
def benchmarks() -> dict:
    return io.load_benchmarks()


@pytest.fixture
def cosme_order() -> dict:
    return io.load_order(COSME_DIR)


@pytest.fixture
def drink_order() -> dict:
    return io.load_order(DRINK_DIR)


def _sum_budget(plan: dict) -> int:
    return sum(a["budget"] for a in plan["allocations"])


def test_budget_total_matches(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    assert _sum_budget(plan) == cosme_order["budget_total"]
    assert plan["simulation"]["total"]["budget"] == cosme_order["budget_total"]


def test_budget_total_matches_drink(benchmarks, drink_order):
    plan = planner.build_plan(drink_order, benchmarks)
    assert _sum_budget(plan) == drink_order["budget_total"]


def test_excluded_media_not_in_allocations(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    selected = {a["media"] for a in plan["allocations"]}
    for excluded in cosme_order["excluded_media"]:
        assert excluded not in selected


def test_excluded_media_not_in_allocations_drink(benchmarks, drink_order):
    plan = planner.build_plan(drink_order, benchmarks)
    selected = {a["media"] for a in plan["allocations"]}
    for excluded in drink_order["excluded_media"]:
        assert excluded not in selected


def test_preferred_media_included(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    selected = {a["media"] for a in plan["allocations"]}
    for preferred in cosme_order["preferred_media"]:
        assert preferred in selected


def test_all_allocations_meet_min_budget(benchmarks, cosme_order, drink_order):
    for order in (cosme_order, drink_order):
        plan = planner.build_plan(order, benchmarks)
        for alloc in plan["allocations"]:
            min_budget = benchmarks["media"][alloc["media"]]["min_budget"]
            assert alloc["budget"] >= min_budget, alloc


def test_impressions_consistent_with_budget_and_cpm(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    for row in plan["simulation"]["by_media"]:
        cpm = benchmarks["media"][row["media"]]["cpm"]
        expected = row["budget"] / cpm * 1000
        if expected == 0:
            assert row["impressions"] == 0
        else:
            rel_error = abs(row["impressions"] - expected) / expected
            assert rel_error <= 0.01


def test_total_reach_smaller_than_naive_sum(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    naive_sum = sum(row["reach"] for row in plan["simulation"]["by_media"])
    assert len(plan["allocations"]) > 1  # dedup が効く前提
    assert plan["simulation"]["total"]["reach"] < naive_sum


def test_invalid_objective_raises(benchmarks, cosme_order):
    bad_order = dict(cosme_order)
    bad_order["objective"] = "not_a_real_objective"
    with pytest.raises(io.SchemaError):
        planner.build_plan(bad_order, benchmarks)


def test_all_media_excluded_raises(benchmarks, cosme_order):
    bad_order = dict(cosme_order)
    bad_order["excluded_media"] = list(benchmarks["media"].keys())
    with pytest.raises(io.SchemaError):
        planner.build_plan(bad_order, benchmarks)


def test_small_budget_selects_two_media(benchmarks):
    order = {
        "campaign_id": "2026-09_inline-test",
        "objective": "awareness",
        "budget_total": 3_000_000,
        "target": {"age": [20, 34], "gender": "female", "interests": ["美容"]},
        "preferred_media": [],
        "excluded_media": [],
    }
    plan = planner.build_plan(order, benchmarks)
    assert len(plan["allocations"]) == 2
    assert _sum_budget(plan) == 3_000_000
