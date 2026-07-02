"""結果レポート生成: tracker のステータスをもとに考察・NEXT ACTION の素案と report.md を作る。"""
from __future__ import annotations

from pathlib import Path

from . import io, tracker

_CPM_HIGH = 1.15
_CPM_LOW = 0.85
_VTR_HIGH = 1.15
_VTR_LOW = 0.85
_PACE_GAP = 0.10
_IMP_SHORTFALL = 0.90

_KPI_MESSAGES = {
    "reach": "リーチ計測はブランドリフト調査の併用で精度向上を検討してください。",
    "views": "視聴系KPIは視聴単価（CPV）の推移もあわせてモニタリングしてください。",
    "completed_views": "完全視聴数の積み上げペースを踏まえ、視聴完了率の高い媒体への配分見直しを検討してください。",
    "impressions": "インプレッション最大化のため配信面の追加・入札調整を継続的に見直してください。",
    "cpm": "CPM効率の観点で低単価媒体への配分最適化を継続的に検討してください。",
    "cpv": "CPV効率の観点でクリエイティブ・入札の両面から改善余地を確認してください。",
}
_KPI_MESSAGE_DEFAULT = "KPI達成に向けて配信状況を継続的にモニタリングしてください。"


def findings(status: dict) -> list[str]:
    """ルールベースの考察素材（日本語の文のリスト）を返す。"""
    items: list[str] = []
    total = status["total"]
    pace = status["pace"]
    spend_ratio = total.get("spend_ratio")

    if spend_ratio is not None:
        diff = spend_ratio - pace
        if diff > _PACE_GAP:
            items.append(
                f"予算消化率（{io.fmt_pct(spend_ratio)}）が期間進捗（{io.fmt_pct(pace)}）を上回っており、"
                "消化が先行しています。このペースでは期間終了前に予算を使い切る早期終了リスクがあります。"
            )
        elif diff < -_PACE_GAP:
            items.append(
                f"予算消化率（{io.fmt_pct(spend_ratio)}）が期間進捗（{io.fmt_pct(pace)}）を下回っており、"
                "消化が遅延しています。"
            )

    cpm_ratio = total.get("cpm_ratio")
    if cpm_ratio is not None:
        if cpm_ratio > _CPM_HIGH:
            items.append(f"全体CPMがシミュレーション比{io.fmt_pct(cpm_ratio)}で高騰しています。")
        elif cpm_ratio < _CPM_LOW:
            items.append(f"全体CPMはシミュレーション比{io.fmt_pct(cpm_ratio)}に収まっており、想定より効率良く配信できています。")

    vtr_ratio = total.get("vtr_ratio")
    if vtr_ratio is not None and (vtr_ratio > _VTR_HIGH or vtr_ratio < _VTR_LOW):
        direction = "上回って" if vtr_ratio > 1 else "下回って"
        items.append(
            f"全体VTR（{io.fmt_pct(total.get('vtr'))}）がシミュレーション想定（{io.fmt_pct(total.get('sim_vtr'))}）を"
            f"{direction}おり、シミュレーションからの乖離が見られます。"
        )

    for m in status["by_media"]:
        name = m.get("media_name", m.get("media", ""))
        m_cpm_ratio = m.get("cpm_ratio")
        if m_cpm_ratio is not None and m_cpm_ratio > _CPM_HIGH:
            items.append(f"{name}: CPMがシミュレーション比{io.fmt_pct(m_cpm_ratio)}で高騰しています。")
        m_vtr_ratio = m.get("vtr_ratio")
        if m_vtr_ratio is not None and m_vtr_ratio < _VTR_LOW:
            items.append(f"{name}: VTRがシミュレーション比{io.fmt_pct(m_vtr_ratio)}にとどまっています。")

    if pace >= 1.0:
        imp_ratio = total.get("imp_ratio")
        if imp_ratio is not None:
            if imp_ratio < _IMP_SHORTFALL:
                items.append(f"配信期間終了時点でインプレッション達成率は{io.fmt_pct(imp_ratio)}にとどまり、未達となっています。")
            elif imp_ratio >= 1.0:
                items.append(f"配信期間終了時点でインプレッション達成率は{io.fmt_pct(imp_ratio)}で、目標を達成しています。")

    if not items:
        items.append("大きな乖離なし。シミュレーション精度は良好です。")

    return items


def next_actions(status: dict, order: dict) -> list[str]:
    """NEXT ACTION 素案（日本語の文のリスト）を返す。

    `order` は order.yaml の dict（KPI別の推奨文の出し分けに "kpi" を使う）。
    """
    items: list[str] = []
    total = status["total"]
    pace = status["pace"]
    spend_ratio = total.get("spend_ratio")

    for m in status["by_media"]:
        name = m.get("media_name", m.get("media", ""))
        cpm_ratio = m.get("cpm_ratio")
        vtr_ratio = m.get("vtr_ratio")
        if cpm_ratio is not None and cpm_ratio > _CPM_HIGH:
            items.append(f"{name}: 配信面・ターゲティングの見直し、または低CPM媒体への予算シフトを検討してください。")
        if vtr_ratio is not None and vtr_ratio < _VTR_LOW:
            items.append(f"{name}: 冒頭3秒のクリエイティブ改善・素材差し替えテストを検討してください。")
        if cpm_ratio is not None and cpm_ratio < _CPM_LOW:
            items.append(f"{name}: 次回は当該媒体への配分増を検討してください。")

    if spend_ratio is not None:
        diff = spend_ratio - pace
        if diff < -_PACE_GAP:
            items.append("消化遅延が見られるため、入札強化 or 配信期間延長を代理店・媒体社と相談してください。")
        elif diff > _PACE_GAP:
            items.append("消化先行が見られるため、日予算キャップの設定を検討してください。")

    kpi = (order or {}).get("kpi")
    items.append(_KPI_MESSAGES.get(kpi, _KPI_MESSAGE_DEFAULT))

    return items


def _summary_table(total: dict) -> list[str]:
    rows = [
        ("imp", total["sim_impressions"], total["impressions"], total["imp_ratio"], io.fmt_num),
        ("views", total["sim_views"], total["views"], total["view_ratio"], io.fmt_num),
        ("completed_views", total["sim_completed_views"], total["completed_views"], total["completed_view_ratio"], io.fmt_num),
        ("reach", total["sim_reach"], total["reach"], total["reach_ratio"], io.fmt_num),
        ("cpm", total["sim_cpm"], total["cpm"], total["cpm_ratio"], io.fmt_yen),
        ("消化額", total["budget"], total["cost"], total["spend_ratio"], io.fmt_yen),
    ]
    lines = ["| 指標 | シミュレーション | 実績 | 達成率 |", "|---|---|---|---|"]
    for label, sim_v, act_v, ratio, fmt in rows:
        lines.append(f"| {label} | {fmt(sim_v)} | {fmt(act_v)} | {io.fmt_pct(ratio)} |")
    return lines


def _media_table(by_media: list[dict]) -> list[str]:
    lines = [
        "| 媒体 | 予算 | 消化 | imp | シミュimp | imp達成率 | CPM | シミュCPM | CPM比 | VTR | シミュVTR | VTR比 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in by_media:
        lines.append(
            "| {name} | {budget} | {cost} | {imp} | {sim_imp} | {imp_ratio} | "
            "{cpm} | {sim_cpm} | {cpm_ratio} | {vtr} | {sim_vtr} | {vtr_ratio} |".format(
                name=m.get("media_name", m.get("media", "")),
                budget=io.fmt_yen(m["budget"]),
                cost=io.fmt_yen(m["cost"]),
                imp=io.fmt_num(m["impressions"]),
                sim_imp=io.fmt_num(m["sim_impressions"]),
                imp_ratio=io.fmt_pct(m["imp_ratio"]),
                cpm=io.fmt_yen(m["cpm"]),
                sim_cpm=io.fmt_yen(m["sim_cpm"]),
                cpm_ratio=io.fmt_pct(m["cpm_ratio"]),
                vtr=io.fmt_pct(m["vtr"]),
                sim_vtr=io.fmt_pct(m["sim_vtr"]),
                vtr_ratio=io.fmt_pct(m["vtr_ratio"]),
            )
        )
    return lines


def build_report(campaign_dir) -> str:
    """report.md の全文（markdown文字列）を返す。"""
    campaign_dir = Path(campaign_dir)
    order = io.load_order(campaign_dir)
    status = tracker.campaign_status(campaign_dir)

    finding_items = findings(status)
    action_items = next_actions(status, order)

    lines: list[str] = []
    lines.append(f"# 【結果レポート】{order['product']}（{order['campaign_id']}）")
    lines.append("")
    lines.append(f"- 広告主: {order['advertiser']}")
    lines.append(f"- 商品: {order['product']}")
    lines.append(f"- 期間: {order['period']['start']} 〜 {order['period']['end']}")
    lines.append(f"- 予算: {io.fmt_yen(order['budget_total'])}")
    lines.append(f"- 目的: {order['objective']}")
    lines.append(f"- 主KPI: {order['kpi']}")
    lines.append("")
    lines.append("## 全体サマリ（シミュレーション比）")
    lines.append("")
    lines.extend(_summary_table(status["total"]))
    lines.append("")
    lines.append("## 媒体別実績")
    lines.append("")
    lines.extend(_media_table(status["by_media"]))
    lines.append("")
    lines.append("## 考察（自動生成の素案）")
    lines.append("")
    for item in finding_items:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## NEXT ACTION（素案）")
    lines.append("")
    for item in action_items:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("---")
    lines.append("※ 考察・NEXT ACTION はルールベースの自動生成素案です。`report-writer` エージェントで文章化・肉付けしてください。")

    return "\n".join(lines) + "\n"


def write_report(campaign_dir) -> Path:
    """build_report の結果を campaign_dir/report.md に保存しパスを返す。"""
    campaign_dir = Path(campaign_dir)
    content = build_report(campaign_dir)
    path = campaign_dir / "report.md"
    path.write_text(content, encoding="utf-8")
    return path
