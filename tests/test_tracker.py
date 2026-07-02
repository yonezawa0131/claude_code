"""adops.tracker のテスト。

tmp_path にスキーマ準拠の order.yaml / plan.yaml / actuals.csv を自作して検証する。
adops.planner には依存しない。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from adops import io, tracker

ACTUALS_HEADER = "date,media,cost,impressions,views,completed_views,clicks,reach\n"


def _write_order(campaign_dir: Path, **overrides) -> dict:
    order = {
        "campaign_id": campaign_dir.name,
        "advertiser": "テスト広告主株式会社",
        "product": "テスト商品",
        "objective": "awareness",
        "kpi": "reach",
        "period": {"start": "2026-08-01", "end": "2026-08-10"},
        "budget_total": 500000,
        "target": {"age": [20, 34], "gender": "female", "interests": [], "area": "全国"},
        "preferred_media": [],
        "excluded_media": [],
        "notes": "",
    }
    order.update(overrides)
    io.save_yaml(order, campaign_dir / "order.yaml")
    return order


def _write_plan(campaign_dir: Path, **overrides) -> dict:
    plan = {
        "campaign_id": campaign_dir.name,
        "generated_at": "2026-07-02T10:00:00",
        "objective": "awareness",
        "strategy_summary": "テスト用プラン",
        "allocations": [
            {
                "media": "youtube",
                "media_name": "YouTube（テスト）",
                "budget": 300000,
                "share": 0.6,
                "score": 1.0,
                "optimization": "tCPM",
                "targeting": {"age": [20, 34], "gender": "female", "segments": []},
                "operation_notes": [],
            },
            {
                "media": "tiktok",
                "media_name": "TikTok（テスト）",
                "budget": 200000,
                "share": 0.4,
                "score": 0.9,
                "optimization": "min",
                "targeting": {"age": [20, 34], "gender": "female", "segments": []},
                "operation_notes": [],
            },
        ],
        "simulation": {
            "total": {
                "budget": 500000,
                "impressions": 1000000,
                "views": 300000,
                "completed_views": 200000,
                "reach": 250000,
                "cpm": 500.0,
                "cpv": 500000 / 300000,
            },
            "by_media": [
                {
                    "media": "youtube",
                    "budget": 300000,
                    "impressions": 600000,
                    "views": 180000,
                    "completed_views": 120000,
                    "reach": 150000,
                    "cpm": 500.0,
                    "cpv": 300000 / 180000,
                    "vtr": 0.3,
                    "view_definition": "30秒視聴",
                },
                {
                    "media": "tiktok",
                    "budget": 200000,
                    "impressions": 400000,
                    "views": 120000,
                    "completed_views": 80000,
                    "reach": 100000,
                    "cpm": 500.0,
                    "cpv": 200000 / 120000,
                    "vtr": 0.3,
                    "view_definition": "6秒視聴",
                },
            ],
        },
    }
    plan.update(overrides)
    io.save_yaml(plan, campaign_dir / "plan.yaml")
    return plan


def _write_actuals(campaign_dir: Path, rows: list[str]) -> None:
    content = ACTUALS_HEADER + "\n".join(rows) + ("\n" if rows else "")
    (campaign_dir / "actuals.csv").write_text(content, encoding="utf-8")


@pytest.fixture
def campaign_dir(tmp_path) -> Path:
    d = tmp_path / "2026-08_test"
    d.mkdir()
    return d


BASIC_ROWS = [
    "2026-08-01,youtube,110000,200000,70000,50000,300,50000",
    "2026-08-02,youtube,110000,200000,70000,50000,300,50000",
    "2026-08-01,tiktok,60000,100000,25000,15000,200,",
    "2026-08-02,tiktok,60000,100000,25000,15000,200,",
]


def test_campaign_status_total_aggregation(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, BASIC_ROWS)

    status = tracker.campaign_status(campaign_dir)

    assert status["campaign_id"] == campaign_dir.name
    assert status["days_total"] == 10
    assert status["days_elapsed"] == 2
    assert status["pace"] == pytest.approx(0.2)

    total = status["total"]
    assert total["cost"] == 340000
    assert total["impressions"] == 600000
    assert total["views"] == 190000
    assert total["completed_views"] == 130000
    assert total["reach"] == 100000  # youtube 50000+50000, tiktok は全行 None なので0扱い
    assert total["cpm"] == pytest.approx(340000 / 600000 * 1000)
    assert total["vtr"] == pytest.approx(190000 / 600000)
    assert total["cpv"] == pytest.approx(340000 / 190000)

    assert total["budget"] == 500000
    assert total["spend_ratio"] == pytest.approx(0.68)
    assert total["imp_ratio"] == pytest.approx(0.6)
    assert total["view_ratio"] == pytest.approx(0.633)
    assert total["completed_view_ratio"] == pytest.approx(0.65)
    assert total["reach_ratio"] == pytest.approx(0.4)
    assert total["cpm_ratio"] == pytest.approx(1.133)
    assert total["vtr_ratio"] == pytest.approx(1.056)
    assert total["cpv_ratio"] == pytest.approx(1.074)


def test_campaign_status_by_media(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, BASIC_ROWS)

    status = tracker.campaign_status(campaign_dir)
    by_media = {m["media"]: m for m in status["by_media"]}
    assert set(by_media) == {"youtube", "tiktok"}

    yt = by_media["youtube"]
    assert yt["media_name"] == "YouTube（テスト）"
    assert yt["budget"] == 300000
    assert yt["cost"] == 220000
    assert yt["impressions"] == 400000
    assert yt["views"] == 140000
    assert yt["completed_views"] == 100000
    assert yt["reach"] == 100000
    assert yt["cpm"] == pytest.approx(550.0)
    assert yt["vtr"] == pytest.approx(0.35)
    assert yt["cpv"] == pytest.approx(220000 / 140000)
    assert yt["imp_ratio"] == pytest.approx(0.667)
    assert yt["cpm_ratio"] == pytest.approx(1.1)
    assert yt["vtr_ratio"] == pytest.approx(1.167)

    tk = by_media["tiktok"]
    assert tk["cost"] == 120000
    assert tk["impressions"] == 200000
    assert tk["views"] == 50000
    assert tk["completed_views"] == 30000
    assert tk["reach"] is None  # 全行 None -> None
    assert tk["reach_ratio"] is None
    assert tk["cpm"] == pytest.approx(600.0)
    assert tk["cpm_ratio"] == pytest.approx(1.2)
    assert tk["vtr_ratio"] == pytest.approx(0.833)


def test_days_elapsed_and_pace_zero_when_no_actuals(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, [])

    status = tracker.campaign_status(campaign_dir)
    assert status["days_elapsed"] == 0
    assert status["pace"] == 0.0
    assert status["total"]["cost"] == 0
    assert status["total"]["reach"] is None
    assert status["total"]["cpm"] is None
    assert status["total"]["spend_ratio"] == 0.0


def test_days_elapsed_missing_actuals_file(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    # actuals.csv を作らない -> io.load_actuals は空リストを返す
    status = tracker.campaign_status(campaign_dir)
    assert status["days_elapsed"] == 0
    assert status["pace"] == 0.0


def test_days_elapsed_clamped_to_period_end(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, [
        "2026-08-01,youtube,10000,20000,7000,5000,30,5000",
        # 期間(8/10まで)を超過した日付。end でクランプされる。
        "2026-08-15,youtube,10000,20000,7000,5000,30,5000",
    ])

    status = tracker.campaign_status(campaign_dir)
    assert status["days_elapsed"] == 10
    assert status["pace"] == 1.0


def test_media_not_in_plan_included_with_none_sim(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, [
        "2026-08-01,youtube,10000,20000,7000,5000,30,5000",
        "2026-08-01,line_video,5000,10000,2000,1000,10,",
    ])

    status = tracker.campaign_status(campaign_dir)
    by_media = {m["media"]: m for m in status["by_media"]}
    assert "line_video" in by_media
    lv = by_media["line_video"]
    assert lv["media_name"] == "line_video"  # plan にないので media キーそのまま
    assert lv["sim_impressions"] is None
    assert lv["imp_ratio"] is None
    assert lv["budget"] is None
    assert lv["cost"] == 5000


def test_campaign_status_raises_schema_error_when_plan_missing(campaign_dir):
    _write_order(campaign_dir)
    with pytest.raises(io.SchemaError):
        tracker.campaign_status(campaign_dir)


def test_portfolio_status_filters_and_sorts(tmp_path):
    root = tmp_path / "campaigns"
    root.mkdir()

    d_b = root / "2026-09_b"
    d_b.mkdir()
    _write_order(d_b)
    _write_plan(d_b)
    _write_actuals(d_b, [])

    d_a = root / "2026-08_a"
    d_a.mkdir()
    _write_order(d_a)
    _write_plan(d_a)
    _write_actuals(d_a, [])

    d_no_plan = root / "2026-07_no_plan"
    d_no_plan.mkdir()
    _write_order(d_no_plan)

    statuses = tracker.portfolio_status(root)
    ids = [s["campaign_id"] for s in statuses]
    assert ids == sorted(ids)
    assert ids == ["2026-08_a", "2026-09_b"]


def test_portfolio_status_empty_root(tmp_path):
    assert tracker.portfolio_status(tmp_path / "no_such_dir") == []


def test_format_status_table_contains_campaign_and_pct(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, BASIC_ROWS)

    status = tracker.campaign_status(campaign_dir)
    table = tracker.format_status_table([status])
    assert campaign_dir.name in table
    assert "campaign_id" in table
    assert "%" in table


def test_format_status_table_shows_dash_for_none(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, [])

    status = tracker.campaign_status(campaign_dir)
    table = tracker.format_status_table([status])
    assert "-" in table


def test_format_campaign_detail_contains_media_rows(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, BASIC_ROWS)

    status = tracker.campaign_status(campaign_dir)
    detail = tracker.format_campaign_detail(status)
    assert campaign_dir.name in detail
    assert "合計" in detail
    assert "YouTube（テスト）" in detail
    assert "TikTok（テスト）" in detail
