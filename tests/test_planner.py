"""adops.planner.build_plan のテスト（v2仕様）。

実際の config/benchmarks.yaml とサンプル order（campaigns/*/order.yaml）を使う。
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from adops import io, planner

REPO_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS_DIR = REPO_ROOT / "campaigns"

COSME_DIR = CAMPAIGNS_DIR / "2026-08_sample-cosme"
DRINK_DIR = CAMPAIGNS_DIR / "2026-06_sample-drink"

# 過去資産（knowledge/archive/2026-07/media_plan.md）実物の純リーチ。再現ケースの基準値として使う。
PAST_ASSET_REACH = 18_186_631


@pytest.fixture(scope="module")
def benchmarks() -> dict:
    return io.load_benchmarks()


@pytest.fixture
def cosme_order() -> dict:
    return io.load_order(COSME_DIR)


@pytest.fixture
def drink_order() -> dict:
    return io.load_order(DRINK_DIR)


def _media_set(plan: dict) -> set:
    return {a["media"] for a in plan["allocations"]}


def _sum_budget(plan: dict) -> int:
    return sum(a["budget"] for a in plan["allocations"])


def _lines_for(plan: dict, media: str) -> list[dict]:
    return [line for line in plan["simulation"]["by_line"] if line["media"] == media]


# ---------------------------------------------------------------------------
# 過去資産再現ケース
#
# knowledge/archive/2026-07/media_plan.md は youtube/meta/tiktok のみで構成された実物プラン
# （目的=reach、予算45,000,000円、3ヶ月弱、予約型としてYouTubeマストヘッドを追加）。
# 同じ媒体構成を再現するため、それ以外の媒体は excluded_media で明示的に除外する
# （target=all/[20,59] という広いターゲットでは、素の適合度スコアだけだと line_video/tver が
#   tiktok よりスコア上位に来てしまい、過去資産と異なる媒体構成になってしまうため）。
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def repro_order() -> dict:
    return {
        "campaign_id": "2026-09_repro-reach",
        "advertiser": "テスト広告主株式会社",
        "product": "テスト商品",
        "objective": "reach",
        "kpi": "reach",
        "period": {"start": date(2026, 9, 1), "end": date(2026, 11, 30)},  # 91日
        "budget_total": 45_000_000,
        "kpi_target": 20_000_000,
        "target": {"age": [20, 59], "gender": "all", "interests": [], "area": "全国"},
        "preferred_media": [],
        "excluded_media": ["x_video", "line_video", "tver", "abema", "display_video"],
        "notes": "",
    }


@pytest.fixture(scope="module")
def repro_plan(benchmarks, repro_order) -> dict:
    return planner.build_plan(repro_order, benchmarks, generated_at=datetime(2026, 7, 3, 10, 0, 0))


def test_repro_reserved_masthead_line_budget(repro_plan):
    reserved = [a for a in repro_plan["allocations"] if a["mode"] == "masthead"]
    assert len(reserved) == 1
    assert reserved[0]["media"] == "youtube"
    assert reserved[0]["budget"] == 8_100_000


def test_repro_youtube_meta_tiktok_have_reach_and_view_lines(repro_plan):
    for media in ("youtube", "meta", "tiktok"):
        modes = {line["mode"] for line in _lines_for(repro_plan, media)}
        assert "reach_opt" in modes, f"{media} に reach_opt ラインがない: {modes}"
        assert "view_opt" in modes, f"{media} に view_opt ラインがない: {modes}"


def test_repro_reach_opt_is_75pct_of_normal_media_budget(repro_plan):
    for media in ("youtube", "meta", "tiktok"):
        by_mode = {
            a["mode"]: a["budget"]
            for a in repro_plan["allocations"]
            if a["media"] == media and a["mode"] != "masthead"
        }
        media_total = sum(by_mode.values())
        ratio = by_mode["reach_opt"] / media_total
        assert ratio == pytest.approx(0.75, abs=0.01), (media, by_mode)


def test_repro_total_line_budget_matches_order_budget(repro_plan, repro_order):
    assert _sum_budget(repro_plan) == repro_order["budget_total"] == 45_000_000
    assert repro_plan["simulation"]["total"]["budget"] == repro_order["budget_total"]


def test_repro_total_reach_within_past_asset_range(repro_plan):
    reach = repro_plan["simulation"]["total"]["reach"]
    # 過去実物 18,186,631 の ±20%程度として与えられた許容レンジ
    assert 14_000_000 <= reach <= 20_000_000, reach


def test_repro_total_reach_smaller_than_raw_sums(repro_plan):
    naive_line_sum = sum(line["reach"] for line in repro_plan["simulation"]["by_line"])
    naive_media_sum = sum(m["reach"] for m in repro_plan["simulation"]["by_media"])
    total_reach = repro_plan["simulation"]["total"]["reach"]
    assert total_reach < naive_media_sum < naive_line_sum


# ---------------------------------------------------------------------------
# video_views + 潤沢でない月額予算 -> マストヘッドなし、view_opt が主モードで約75%
#
# campaigns/2026-06_sample-drink は budget_total=8,000,000円/期間1ヶ月/objective=video_views
# という、まさにこのシナリオのオーダー。
# ---------------------------------------------------------------------------

def test_drink_no_masthead_line(benchmarks, drink_order):
    plan = planner.build_plan(drink_order, benchmarks)
    assert not any(a["mode"] == "masthead" for a in plan["allocations"])
    assert plan["warnings"] == [] or all("予約型" not in w for w in plan["warnings"])


def test_drink_view_opt_is_about_75pct_where_present(benchmarks, drink_order):
    plan = planner.build_plan(drink_order, benchmarks)
    checked_any = False
    for media in _media_set(plan):
        by_mode = {a["mode"]: a["budget"] for a in plan["allocations"] if a["media"] == media}
        if "view_opt" in by_mode and "reach_opt" in by_mode:
            checked_any = True
            media_total = by_mode["view_opt"] + by_mode["reach_opt"]
            ratio = by_mode["view_opt"] / media_total
            assert ratio == pytest.approx(0.75, abs=0.01), (media, by_mode)
    assert checked_any, "reach_opt/view_opt構成の媒体が1つも選定されていない"


# ---------------------------------------------------------------------------
# kpi_target 検証
# ---------------------------------------------------------------------------

def test_kpi_target_extreme_triggers_achievement_warning(benchmarks, cosme_order):
    order = dict(cosme_order)
    order["kpi_target"] = 100_000_000  # 現実的にありえない極端に高い目標
    plan = planner.build_plan(order, benchmarks)

    assert plan["kpi_projection"]["achievement"] is not None
    assert plan["kpi_projection"]["achievement"] < 1.0
    assert any(
        "与件達成見込みが100%を下回っています" in w for w in plan["warnings"]
    ), plan["warnings"]


def test_kpi_projection_note_present_value_only_when_no_target(benchmarks, cosme_order):
    order = dict(cosme_order)
    order.pop("kpi_target", None)
    plan = planner.build_plan(order, benchmarks)
    assert plan["kpi_projection"]["target"] is None
    assert plan["kpi_projection"]["achievement"] is None
    assert "見込み値のみ提示" in plan["kpi_projection"]["note"]


# ---------------------------------------------------------------------------
# 予算規模による媒体数
# ---------------------------------------------------------------------------

def test_small_budget_selects_two_media(benchmarks):
    order = {
        "campaign_id": "2026-09_inline-test",
        "objective": "awareness",
        "period": {"start": "2026-09-01", "end": "2026-09-30"},
        "budget_total": 3_000_000,
        "target": {"age": [20, 34], "gender": "female", "interests": ["美容"]},
        "preferred_media": [],
        "excluded_media": [],
    }
    plan = planner.build_plan(order, benchmarks)
    assert len(_media_set(plan)) == 2
    assert _sum_budget(plan) == 3_000_000


def test_missing_period_does_not_crash_and_skips_reserved(benchmarks):
    """period が無い（旧v1形式の）order でもクラッシュせず、予約型判定は単にスキップされる。"""
    order = {
        "campaign_id": "2026-09_inline-no-period",
        "objective": "awareness",
        "budget_total": 3_000_000,
        "target": {"age": [20, 34], "gender": "female", "interests": ["美容"]},
        "preferred_media": [],
        "excluded_media": [],
    }
    plan = planner.build_plan(order, benchmarks)
    assert len(_media_set(plan)) == 2
    assert not any(a["mode"] == "masthead" for a in plan["allocations"])


# ---------------------------------------------------------------------------
# excluded_media / preferred_media / min_budget / 合計一致 / SchemaError系
# ---------------------------------------------------------------------------

def test_budget_total_matches(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    assert _sum_budget(plan) == cosme_order["budget_total"]
    assert plan["simulation"]["total"]["budget"] == cosme_order["budget_total"]


def test_budget_total_matches_drink(benchmarks, drink_order):
    plan = planner.build_plan(drink_order, benchmarks)
    assert _sum_budget(plan) == drink_order["budget_total"]


def test_excluded_media_not_in_allocations(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    selected = _media_set(plan)
    for excluded in cosme_order["excluded_media"]:
        assert excluded not in selected


def test_excluded_media_not_in_allocations_drink(benchmarks, drink_order):
    plan = planner.build_plan(drink_order, benchmarks)
    selected = _media_set(plan)
    for excluded in drink_order["excluded_media"]:
        assert excluded not in selected


def test_preferred_media_included(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    selected = _media_set(plan)
    for preferred in cosme_order["preferred_media"]:
        assert preferred in selected


def test_all_normal_lines_meet_media_min_budget(benchmarks, cosme_order, drink_order):
    """予約型（role: reserved）ラインを除く、媒体ごとのライン予算合計が min_budget を満たすこと。

    v2ではラインが媒体×モードに分かれるため、min_budgetのチェックは媒体単位の合計に対して行う。
    """
    for order in (cosme_order, drink_order):
        plan = planner.build_plan(order, benchmarks)
        totals: dict[str, int] = {}
        for a in plan["allocations"]:
            mode_def = benchmarks["media"][a["media"]]["modes"][a["mode"]]
            if mode_def.get("role") == "reserved":
                continue
            totals[a["media"]] = totals.get(a["media"], 0) + a["budget"]
        for media, total in totals.items():
            min_budget = benchmarks["media"][media]["min_budget"]
            assert total >= min_budget, (media, total, min_budget)


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


# ---------------------------------------------------------------------------
# ライン整合性 / 純リーチモデル
# ---------------------------------------------------------------------------

def test_line_impressions_consistent_with_budget_and_mode_cpm(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    for line in plan["simulation"]["by_line"]:
        mode_def = benchmarks["media"][line["media"]]["modes"][line["mode"]]
        expected = line["budget"] / mode_def["cpm"] * 1000
        assert line["impressions"] == int(expected)


def test_by_media_reach_less_than_line_sum_when_multiple_lines(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    checked_any = False
    for m in plan["simulation"]["by_media"]:
        lines = _lines_for(plan, m["media"])
        if len(lines) > 1:
            checked_any = True
            assert m["reach"] < sum(line["reach"] for line in lines)
    assert checked_any, "複数ラインを持つ媒体が1つもない（テスト条件を満たせない）"


def test_total_reach_smaller_than_naive_media_sum(benchmarks, cosme_order):
    plan = planner.build_plan(cosme_order, benchmarks)
    naive_sum = sum(row["reach"] for row in plan["simulation"]["by_media"])
    assert len(_media_set(plan)) > 1  # dedup が効く前提
    assert plan["simulation"]["total"]["reach"] < naive_sum


def test_total_reach_capped_by_universe_for_out_of_range_age(benchmarks):
    """reach_model.universe.age_share の範囲(13-69)外のターゲットでは age係数=0 -> U=floor。

    total.reach は U (= floor) を超えない。
    """
    order = {
        "campaign_id": "2026-09_narrow-test",
        "objective": "awareness",
        "period": {"start": "2026-09-01", "end": "2026-09-30"},
        "budget_total": 3_000_000,
        "target": {"age": [70, 75], "gender": "female", "interests": []},
        "preferred_media": [],
        "excluded_media": [],
    }
    plan = planner.build_plan(order, benchmarks)
    floor = benchmarks["reach_model"]["universe"]["floor"]
    assert plan["simulation"]["total"]["reach"] < floor
