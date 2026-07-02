"""adops.reporter のテスト。

tmp_path にスキーマ準拠の order.yaml / plan.yaml / actuals.csv を自作して検証する。
adops.planner には依存しない。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from adops import io, reporter

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


# ---------------------------------------------------------------------------
# findings / next_actions: 合成した status dict でルールを個別に検証する
# ---------------------------------------------------------------------------

def _status(pace, total_overrides=None, by_media=None):
    total = {
        "budget": 500000, "cost": 0, "spend_ratio": None,
        "impressions": 0, "sim_impressions": 1000000, "imp_ratio": None,
        "views": 0, "sim_views": 300000, "view_ratio": None,
        "completed_views": 0, "sim_completed_views": 200000, "completed_view_ratio": None,
        "reach": None, "sim_reach": 250000, "reach_ratio": None,
        "cpm": None, "sim_cpm": 500.0, "cpm_ratio": None,
        "cpv": None, "sim_cpv": 1.667, "cpv_ratio": None,
        "vtr": None, "sim_vtr": 0.3, "vtr_ratio": None,
    }
    if total_overrides:
        total.update(total_overrides)
    return {
        "campaign_id": "2026-08_test",
        "period": {"start": date(2026, 8, 1), "end": date(2026, 8, 10)},
        "days_total": 10,
        "days_elapsed": 2,
        "pace": pace,
        "total": total,
        "by_media": by_media or [],
    }


@pytest.fixture
def order_stub() -> dict:
    return {
        "campaign_id": "2026-08_test",
        "advertiser": "テスト広告主株式会社",
        "product": "テスト商品",
        "objective": "awareness",
        "kpi": "reach",
        "period": {"start": date(2026, 8, 1), "end": date(2026, 8, 10)},
        "budget_total": 500000,
    }


def test_findings_cpm_spike(order_stub):
    status = _status(pace=0.5, total_overrides={"spend_ratio": 0.5, "cpm_ratio": 1.3})
    result = reporter.findings(status)
    assert any("高騰" in f for f in result)


def test_findings_cpm_efficient(order_stub):
    status = _status(pace=0.5, total_overrides={"spend_ratio": 0.5, "cpm_ratio": 0.7})
    result = reporter.findings(status)
    assert any("効率良く" in f for f in result)


def test_findings_no_cpm_finding_when_within_range(order_stub):
    status = _status(pace=0.5, total_overrides={"spend_ratio": 0.5, "cpm_ratio": 1.0})
    result = reporter.findings(status)
    assert not any("高騰" in f or "効率良く" in f for f in result)


def test_findings_spend_delay(order_stub):
    status = _status(pace=0.6, total_overrides={"spend_ratio": 0.3, "cpm_ratio": 1.0})
    result = reporter.findings(status)
    assert any("遅延" in f for f in result)


def test_findings_spend_ahead(order_stub):
    status = _status(pace=0.2, total_overrides={"spend_ratio": 0.6, "cpm_ratio": 1.0})
    result = reporter.findings(status)
    assert any("先行" in f for f in result)


def test_findings_no_deviation(order_stub):
    status = _status(
        pace=0.5,
        total_overrides={"spend_ratio": 0.5, "cpm_ratio": 1.0, "vtr_ratio": 1.0, "vtr": 0.3, "sim_vtr": 0.3},
    )
    result = reporter.findings(status)
    assert result == ["大きな乖離なし。シミュレーション精度は良好です。"]


def test_findings_media_level_cpm_and_vtr(order_stub):
    by_media = [
        {"media": "youtube", "media_name": "YouTube", "cpm_ratio": 1.3, "vtr_ratio": 1.0},
        {"media": "tiktok", "media_name": "TikTok", "cpm_ratio": 1.0, "vtr_ratio": 0.7},
    ]
    status = _status(
        pace=0.5,
        total_overrides={"spend_ratio": 0.5, "cpm_ratio": 1.0, "vtr_ratio": 1.0},
        by_media=by_media,
    )
    result = reporter.findings(status)
    assert any("YouTube" in f and "高騰" in f for f in result)
    assert any("TikTok" in f for f in result)


def test_findings_imp_shortfall_when_finished(order_stub):
    status = _status(
        pace=1.0,
        total_overrides={"spend_ratio": 1.0, "cpm_ratio": 1.0, "vtr_ratio": 1.0, "imp_ratio": 0.8},
    )
    result = reporter.findings(status)
    assert any("未達" in f for f in result)


def test_findings_imp_achieved_when_finished(order_stub):
    status = _status(
        pace=1.0,
        total_overrides={"spend_ratio": 1.0, "cpm_ratio": 1.0, "vtr_ratio": 1.0, "imp_ratio": 1.05},
    )
    result = reporter.findings(status)
    assert any("達成" in f for f in result)


def test_findings_no_imp_finding_before_delivery_finished(order_stub):
    status = _status(
        pace=0.5,
        total_overrides={"spend_ratio": 0.5, "cpm_ratio": 1.0, "vtr_ratio": 1.0, "imp_ratio": 0.2},
    )
    result = reporter.findings(status)
    assert not any("未達" in f or "達成" in f for f in result)


def test_next_actions_cpm_high_media_suggests_shift(order_stub):
    by_media = [{"media": "youtube", "media_name": "YouTube", "cpm_ratio": 1.3, "vtr_ratio": 1.0}]
    status = _status(pace=0.5, total_overrides={"spend_ratio": 0.5}, by_media=by_media)
    result = reporter.next_actions(status, order_stub)
    assert any("YouTube" in a and ("見直し" in a or "シフト" in a) for a in result)


def test_next_actions_vtr_low_media_suggests_creative(order_stub):
    by_media = [{"media": "tiktok", "media_name": "TikTok", "cpm_ratio": 1.0, "vtr_ratio": 0.7}]
    status = _status(pace=0.5, total_overrides={"spend_ratio": 0.5}, by_media=by_media)
    result = reporter.next_actions(status, order_stub)
    assert any("TikTok" in a and "クリエイティブ" in a for a in result)


def test_next_actions_delay_suggests_bid_or_extend(order_stub):
    status = _status(pace=0.6, total_overrides={"spend_ratio": 0.3})
    result = reporter.next_actions(status, order_stub)
    assert any("入札強化" in a or "延長" in a for a in result)


def test_next_actions_ahead_suggests_daily_cap(order_stub):
    status = _status(pace=0.2, total_overrides={"spend_ratio": 0.6})
    result = reporter.next_actions(status, order_stub)
    assert any("日予算キャップ" in a for a in result)


def test_next_actions_kpi_message_reach(order_stub):
    order_stub["kpi"] = "reach"
    status = _status(pace=0.5, total_overrides={"spend_ratio": 0.5})
    result = reporter.next_actions(status, order_stub)
    assert any("ブランドリフト" in a for a in result)


def test_next_actions_kpi_message_impressions(order_stub):
    order_stub["kpi"] = "impressions"
    status = _status(pace=0.5, total_overrides={"spend_ratio": 0.5})
    result = reporter.next_actions(status, order_stub)
    assert any("インプレッション" in a for a in result)


# ---------------------------------------------------------------------------
# build_report / write_report: 実ファイルを使ったエンドツーエンド確認
# ---------------------------------------------------------------------------

def test_build_report_contains_main_sections_and_values(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, BASIC_ROWS)

    report = reporter.build_report(campaign_dir)

    assert "【結果レポート】" in report
    assert campaign_dir.name in report
    assert "## 全体サマリ（シミュレーション比）" in report
    assert "## 媒体別実績" in report
    assert "## 考察（自動生成の素案）" in report
    assert "## NEXT ACTION（素案）" in report
    assert "report-writer" in report
    assert "YouTube（テスト）" in report
    assert "TikTok（テスト）" in report
    assert io.fmt_yen(340000) in report  # 実績消化額合計


def test_build_report_raises_schema_error_when_plan_missing(campaign_dir):
    _write_order(campaign_dir)
    with pytest.raises(io.SchemaError):
        reporter.build_report(campaign_dir)


def test_write_report_creates_file(campaign_dir):
    _write_order(campaign_dir)
    _write_plan(campaign_dir)
    _write_actuals(campaign_dir, BASIC_ROWS)

    path = reporter.write_report(campaign_dir)

    assert path == campaign_dir / "report.md"
    assert path.exists()
    assert path.read_text(encoding="utf-8") == reporter.build_report(campaign_dir)
