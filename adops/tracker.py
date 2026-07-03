"""実績トラッキング: plan.yaml（シミュレーション）と actuals.csv（実績）を突合してステータスを算出する。

スキーマは docs/SCHEMAS.md の「ステータス dict」を正とする。
"""
from __future__ import annotations

from pathlib import Path

from . import io


def _ratio(actual, sim):
    """*_ratio = 実績 / シミュ。分母が None または 0 のときは None。round 3。"""
    if actual is None or sim is None or sim == 0:
        return None
    return round(actual / sim, 3)


def _aggregate(rows: list[dict]) -> dict:
    """actuals の行リストを合計する。None は 0 扱い。ただし reach は全行 None なら None。"""
    cost = sum((r["cost"] or 0) for r in rows)
    impressions = sum((r["impressions"] or 0) for r in rows)
    views = sum((r["views"] or 0) for r in rows)
    completed_views = sum((r["completed_views"] or 0) for r in rows)

    if rows and any(r["reach"] is not None for r in rows):
        reach = sum((r["reach"] or 0) for r in rows)
    else:
        reach = None

    cpm = (cost / impressions * 1000) if impressions else None
    vtr = (views / impressions) if impressions else None
    cpv = (cost / views) if views else None

    return {
        "cost": cost,
        "impressions": impressions,
        "views": views,
        "completed_views": completed_views,
        "reach": reach,
        "cpm": cpm,
        "vtr": vtr,
        "cpv": cpv,
    }


def _build_metrics(budget, agg: dict, sim: dict) -> dict:
    """1つの集計単位（合計 or 媒体）分のステータス dict を組み立てる。"""
    sim_impressions = sim.get("impressions")
    sim_views = sim.get("views")
    sim_completed_views = sim.get("completed_views")
    sim_reach = sim.get("reach")
    sim_cpm = sim.get("cpm")
    sim_cpv = sim.get("cpv")
    sim_vtr = sim.get("vtr")
    if sim_vtr is None and sim_impressions:
        sim_vtr = sim_views / sim_impressions if sim_views is not None else None

    cost = agg["cost"]

    return {
        "budget": budget,
        "cost": cost,
        "spend_ratio": _ratio(cost, budget),
        "impressions": agg["impressions"],
        "sim_impressions": sim_impressions,
        "imp_ratio": _ratio(agg["impressions"], sim_impressions),
        "views": agg["views"],
        "sim_views": sim_views,
        "view_ratio": _ratio(agg["views"], sim_views),
        "completed_views": agg["completed_views"],
        "sim_completed_views": sim_completed_views,
        "completed_view_ratio": _ratio(agg["completed_views"], sim_completed_views),
        "reach": agg["reach"],
        "sim_reach": sim_reach,
        "reach_ratio": _ratio(agg["reach"], sim_reach),
        "cpm": agg["cpm"],
        "sim_cpm": sim_cpm,
        "cpm_ratio": _ratio(agg["cpm"], sim_cpm),
        "cpv": agg["cpv"],
        "sim_cpv": sim_cpv,
        "cpv_ratio": _ratio(agg["cpv"], sim_cpv),
        "vtr": agg["vtr"],
        "sim_vtr": sim_vtr,
        "vtr_ratio": _ratio(agg["vtr"], sim_vtr),
    }


def campaign_status(campaign_dir) -> dict:
    """docs/SCHEMAS.md の「ステータス dict」を返す。plan.yaml が無ければ io.SchemaError。"""
    campaign_dir = Path(campaign_dir)
    plan_path = campaign_dir / "plan.yaml"
    if not plan_path.exists():
        raise io.SchemaError(f"{plan_path}: plan.yaml がありません（先に `adops plan` を実行してください）")

    order = io.load_order(campaign_dir)
    plan = io.load_plan(campaign_dir)
    actuals = io.load_actuals(campaign_dir)

    start = order["period"]["start"]
    end = order["period"]["end"]
    days_total = (end - start).days + 1

    if actuals:
        max_date = max(r["date"] for r in actuals)
        days_elapsed = (min(max_date, end) - start).days + 1
        if days_elapsed < 0:
            days_elapsed = 0
    else:
        days_elapsed = 0

    pace = round(days_elapsed / days_total, 3)

    budget = order["budget_total"]

    simulation = plan.get("simulation") or {}
    sim_total = simulation.get("total") or {}
    total = _build_metrics(budget, _aggregate(actuals), sim_total)

    allocations = plan.get("allocations") or []
    # v2 では1媒体が複数ライン（媒体×モード）に分かれるため、media_name は最初に出た値を採用し、
    # budget はライン予算を合算する（budget が None のラインは0扱い、全ラインNoneならNone）。
    media_names: dict = {}
    media_budget_lines: dict = {}
    for a in allocations:
        media = a["media"]
        media_names.setdefault(media, a.get("media_name", media))
        media_budget_lines.setdefault(media, []).append(a.get("budget"))
    media_budgets = {
        media: (None if all(b is None for b in lines) else sum((b or 0) for b in lines))
        for media, lines in media_budget_lines.items()
    }
    sim_by_media = {m["media"]: m for m in (simulation.get("by_media") or [])}

    # plan にある媒体を先に、actuals にしかない媒体（拾い漏れ防止）を後ろに追加
    media_order = list(media_names.keys())
    for mk in sorted({r["media"] for r in actuals}):
        if mk not in media_order:
            media_order.append(mk)

    by_media = []
    for media in media_order:
        rows = [r for r in actuals if r["media"] == media]
        sim = sim_by_media.get(media, {})
        block = _build_metrics(media_budgets.get(media), _aggregate(rows), sim)
        block["media"] = media
        block["media_name"] = media_names.get(media, media)
        by_media.append(block)

    return {
        "campaign_id": order["campaign_id"],
        "period": {"start": start, "end": end},
        "days_total": days_total,
        "days_elapsed": days_elapsed,
        "pace": pace,
        "total": total,
        "by_media": by_media,
    }


def portfolio_status(root=io.CAMPAIGNS_DIR) -> list[dict]:
    """plan.yaml が存在する全案件の campaign_status のリスト（campaign_id 昇順）"""
    root = Path(root)
    if not root.exists():
        return []
    dirs = sorted(
        (p for p in root.iterdir() if p.is_dir() and (p / "plan.yaml").exists()),
        key=lambda p: p.name,
    )
    return [campaign_status(d) for d in dirs]


def format_status_table(statuses: list[dict]) -> str:
    """全案件横断のテキストテーブル（1案件1行）。

    列: campaign_id / 期間進捗 / 消化率 / imp達成率 / CPM比 / VTR比
    """
    headers = ["campaign_id", "期間進捗", "消化率", "imp達成率", "CPM比", "VTR比"]
    rows = []
    for s in statuses:
        total = s["total"]
        rows.append([
            s["campaign_id"],
            io.fmt_pct(s["pace"]),
            io.fmt_pct(total["spend_ratio"]),
            io.fmt_pct(total["imp_ratio"]),
            io.fmt_pct(total["cpm_ratio"]),
            io.fmt_pct(total["vtr_ratio"]),
        ])

    widths = [
        max([len(headers[i])] + [len(r[i]) for r in rows]) for i in range(len(headers))
    ]
    lines = [" | ".join(h.ljust(w) for h, w in zip(headers, widths))]
    lines.append("-+-".join("-" * w for w in widths))
    for r in rows:
        lines.append(" | ".join(c.ljust(w) for c, w in zip(r, widths)))
    return "\n".join(lines)


def format_campaign_detail(status: dict) -> str:
    """1案件の詳細テキスト: 合計行 + 媒体別行。

    列: 予算 / 消化 / imp / シミュ比 / CPM / シミュCPM / VTR / シミュVTR
    """
    headers = ["区分", "予算", "消化", "imp", "シミュ比", "CPM", "シミュCPM", "VTR", "シミュVTR"]

    def _row(label: str, m: dict) -> list[str]:
        return [
            label,
            io.fmt_yen(m["budget"]),
            io.fmt_yen(m["cost"]),
            io.fmt_num(m["impressions"]),
            io.fmt_pct(m["imp_ratio"]),
            io.fmt_yen(m["cpm"]),
            io.fmt_yen(m["sim_cpm"]),
            io.fmt_pct(m["vtr"]),
            io.fmt_pct(m["sim_vtr"]),
        ]

    rows = [_row("合計", status["total"])]
    for m in status["by_media"]:
        rows.append(_row(m.get("media_name", m.get("media", "")), m))

    widths = [
        max([len(headers[i])] + [len(r[i]) for r in rows]) for i in range(len(headers))
    ]
    lines = [f"■ {status['campaign_id']}"]
    lines.append(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    lines.append("-+-".join("-" * w for w in widths))
    for r in rows:
        lines.append(" | ".join(c.ljust(w) for c, w in zip(r, widths)))
    return "\n".join(lines)
