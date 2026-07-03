"""媒体プランニング: order.yaml + benchmarks.yaml から plan.yaml 相当の dict を生成する（v2）。

スキーマは docs/SCHEMAS.md を正とする。v2 では「媒体×最適化モード」単位のライン構成、
予約型追加ルール（基準2）、重複排除ベースの純リーチモデル（基準4）を実装する。
アルゴリズムの根拠（reach_model / mode_split / reserved）は config/benchmarks.yaml 冒頭コメント参照。
"""
from __future__ import annotations

import math
from datetime import datetime

from . import io

# 目的別の運用共通ノート（媒体固有の operation_notes に追記する）
COMMON_OPERATION_NOTES = {
    "awareness": "リーチ×フリークエンシーを週次で確認し、FQ超過時は配信調整",
    "reach": "ユニークリーチの伸びが鈍化したらターゲット/面の拡張を検討",
    "video_views": "CPVと視聴率を日次確認し、低VTR素材は早期に差し替え",
    "consideration": "視聴後の指名検索/サイト流入をあわせてモニタリング",
}

# strategy_summary 用の目的ラベル
OBJECTIVE_LABELS = {
    "awareness": "認知拡大",
    "reach": "リーチ最大化",
    "video_views": "動画視聴最大化",
    "consideration": "比較検討促進",
}

# モード配分における role のラベル（strategy_summary 用）
_ROLE_LABELS = {"reach": "リーチ最適", "view": "視聴最適"}

# 小ライン防止の下限（secondary への配分がこれ未満ならラインを立てない）
_MIN_LINE_BUDGET = 200_000

# 1ヶ月あたりの日数換算係数（予約型ルールの月額予算換算に使用）
_DAYS_PER_MONTH = 30.4

# kpi -> simulation.total の対応キー
_KPI_FIELD_MAP = {
    "reach": "reach",
    "impressions": "impressions",
    "views": "views",
    "completed_views": "completed_views",
    "cpm": "cpm",
    "cpv": "cpv",
}
# 値が小さいほど良い（達成率は target/projected で算出）指標
_KPI_COST_METRICS = {"cpm", "cpv"}
_KPI_LABELS = {
    "reach": ("純リーチ", "人"),
    "impressions": ("インプレッション", "imp"),
    "views": ("視聴数", "View"),
    "completed_views": ("完全視聴数", "View"),
    "cpm": ("CPM", "円"),
    "cpv": ("CPV", "円"),
}


def _round1000(value: float) -> int:
    return int(round(value / 1000.0)) * 1000


# ---------------------------------------------------------------------------
# 媒体選定（v1から変更なし）
# ---------------------------------------------------------------------------

def _age_coefficient(age_rows, target_min: int, target_max: int) -> float:
    """audience_affinity.age の各行とターゲット年齢範囲の重なり年数で加重平均した係数を返す。"""
    total_overlap = 0
    weighted_sum = 0.0
    for row_min, row_max, multiplier in age_rows:
        overlap = min(row_max, target_max) - max(row_min, target_min) + 1
        if overlap > 0:
            total_overlap += overlap
            weighted_sum += overlap * multiplier
    if total_overlap <= 0:
        return 0.5
    return weighted_sum / total_overlap


def _score_media(media: dict, objective: str, gender: str, age_min: int, age_max: int) -> float:
    fit = media["objective_fit"][objective]
    gender_coef = media["audience_affinity"]["gender"].get(gender, 1.0)
    age_coef = _age_coefficient(media["audience_affinity"]["age"], age_min, age_max)
    return fit * gender_coef * age_coef


def _select_media_count(budget_total: int) -> int:
    if budget_total < 5_000_000:
        return 2
    if budget_total < 15_000_000:
        return 3
    return 4


def _select_media(candidates: dict, scores: dict, budget_total: int, preferred: list[str]) -> list[str]:
    n = min(_select_media_count(budget_total), len(candidates))
    ranked = sorted(candidates.keys(), key=lambda k: (-scores[k], k))
    selected = ranked[:n]

    preferred_set = set(preferred)
    for pm in preferred:
        if pm not in selected:
            swappable = [m for m in selected if m not in preferred_set]
            if swappable:
                lowest = min(swappable, key=lambda m: scores[m])
                selected[selected.index(lowest)] = pm
            else:
                selected.append(pm)
    return selected


def _allocate_budget(
    selected: list[str], scores: dict, min_budgets: dict, preferred_set: set, budget_total: int
) -> dict:
    """score 比例で配分し、min_budget を下回る媒体を落として再配分する（対象は呼び出し側が渡す予算）。"""
    active = list(selected)
    while True:
        if len(active) == 1:
            return {active[0]: budget_total}

        total_score = sum(scores[m] for m in active)
        raw = {m: budget_total * scores[m] / total_score for m in active}
        rounded = {m: _round1000(raw[m]) for m in active}

        diff = budget_total - sum(rounded.values())
        if diff:
            max_media = max(active, key=lambda m: rounded[m])
            rounded[max_media] += diff

        violators = [m for m in active if rounded[m] < min_budgets[m]]
        if not violators:
            return rounded

        # スコアの低い順に落とす。preferred_media は満たせる限り保護する。
        non_preferred_violators = [m for m in violators if m not in preferred_set]
        drop_pool = non_preferred_violators if non_preferred_violators else violators
        drop = min(drop_pool, key=lambda m: scores[m])
        active.remove(drop)


# ---------------------------------------------------------------------------
# 予約型ルール（基準2）
# ---------------------------------------------------------------------------

def _compute_reserved(order: dict, benchmarks: dict, objective: str, candidates: dict, scores: dict,
                       budget_total: int) -> dict:
    """予約型（role: reserved）ラインの確保可否と予算を判定する。

    返り値: {media, mode, mode_label, media_name, budget, warning, monthly_budget, eligible, applied}
    - eligible: 目的・月額予算の条件を満たすか
    - applied: 実際に予約型ラインを確保したか（eligible かつ min_budget を満たした場合のみ True）
    """
    reserved_cfg = benchmarks.get("reserved") or {}
    period = order.get("period") or {}
    monthly_budget = None
    if period.get("start") is not None and period.get("end") is not None:
        start = io._to_date(period["start"])
        end = io._to_date(period["end"])
        days = (end - start).days + 1
        months = days / _DAYS_PER_MONTH
        monthly_budget = budget_total / max(months, 0.5)

    info = {
        "media": None, "mode": None, "mode_label": None, "media_name": None,
        "budget": 0, "warning": None, "monthly_budget": monthly_budget,
        "eligible": False, "applied": False,
    }

    if objective not in ("awareness", "reach"):
        return info
    if monthly_budget is None or monthly_budget < reserved_cfg.get("monthly_budget_threshold", float("inf")):
        return info

    info["eligible"] = True

    reserved_candidates = []
    for key, media in candidates.items():
        for mode_key, mode_def in (media.get("modes") or {}).items():
            if mode_def.get("role") == "reserved":
                reserved_candidates.append((key, mode_key, mode_def))
                break
    if not reserved_candidates:
        return info

    best_key, best_mode_key, best_mode_def = max(reserved_candidates, key=lambda t: scores[t[0]])
    info["media"] = best_key
    info["mode"] = best_mode_key
    info["mode_label"] = best_mode_def.get("label")
    info["media_name"] = candidates[best_key]["name"]

    reserved_budget = _round1000(budget_total * reserved_cfg.get("share_of_total", 0.0))
    min_budget = best_mode_def.get("min_budget", 0)
    if reserved_budget < min_budget:
        info["warning"] = (
            "予約型の最低出稿金額に満たないため見送り"
            f"（{info['media_name']}: 確保予定額{io.fmt_yen(reserved_budget)} < 最低出稿{io.fmt_yen(min_budget)}）"
        )
        return info

    info["budget"] = reserved_budget
    info["applied"] = True
    return info


# ---------------------------------------------------------------------------
# モード分割（媒体予算 → ライン）
# ---------------------------------------------------------------------------

def _primary_secondary_roles(objective: str) -> tuple[str, str]:
    if objective in ("awareness", "reach"):
        return "reach", "view"
    return "view", "reach"


def _mode_lines_for_media(media: dict, media_budget: int, primary_role: str, secondary_role: str,
                           mode_split: dict) -> list[tuple[str, dict, int]]:
    """媒体の modes（reserved除く）を primary/secondary に分割し [(mode_key, mode_def, budget), ...] を返す。

    順序は primary → secondary。1本しかラインが立たない場合はそのモードに100%。
    """
    modes = {k: v for k, v in (media.get("modes") or {}).items() if v.get("role") != "reserved"}
    if not modes:
        return []
    if len(modes) == 1:
        (mode_key, mode_def), = modes.items()
        return [(mode_key, mode_def, media_budget)]

    primary_entry = next(((k, v) for k, v in modes.items() if v.get("role") == primary_role), None)
    secondary_entry = next(((k, v) for k, v in modes.items() if v.get("role") == secondary_role), None)

    if primary_entry and not secondary_entry:
        return [(primary_entry[0], primary_entry[1], media_budget)]
    if secondary_entry and not primary_entry:
        return [(secondary_entry[0], secondary_entry[1], media_budget)]
    if not primary_entry and not secondary_entry:
        # 想定外データへのフォールバック: 先頭のモードに100%
        mode_key, mode_def = next(iter(modes.items()))
        return [(mode_key, mode_def, media_budget)]

    # 両方存在する場合: 極小ライン防止 → 1000円丸め・端数はprimaryへ
    secondary_raw = media_budget * mode_split["secondary"]
    if secondary_raw < _MIN_LINE_BUDGET:
        return [(primary_entry[0], primary_entry[1], media_budget)]

    primary_raw_rounded = _round1000(media_budget * mode_split["primary"])
    secondary_rounded = _round1000(secondary_raw)
    diff = media_budget - (primary_raw_rounded + secondary_rounded)
    primary_budget = primary_raw_rounded + diff

    return [
        (primary_entry[0], primary_entry[1], primary_budget),
        (secondary_entry[0], secondary_entry[1], secondary_rounded),
    ]


# ---------------------------------------------------------------------------
# ラインシミュレーション（simulation.by_line）
# ---------------------------------------------------------------------------

def _simulate_line(budget: int, mode_def: dict) -> dict:
    cpm = mode_def["cpm"]
    vtr = mode_def["vtr"]
    completion_rate = mode_def["completion_rate"]
    fq = mode_def["fq"]
    ctr = mode_def.get("ctr")
    engr = mode_def.get("engr")

    impressions = int(budget / cpm * 1000)
    views = int(impressions * vtr)
    completed_views = int(impressions * completion_rate)
    reach = int(impressions / fq) if fq else 0
    clicks = int(impressions * ctr) if ctr is not None else None
    engagements = int(impressions * engr) if engr is not None else None

    cpv = round(budget / views, 2) if views else None
    cpc = round(budget / clicks, 1) if clicks else None
    cpe = round(budget / engagements, 1) if engagements else None
    cpr = round(budget / reach, 2) if reach else None

    return {
        "impressions": impressions,
        "reach": reach,
        "fq": fq,
        "cpr": cpr,
        "views": views,
        "completed_views": completed_views,
        "clicks": clicks,
        "engagements": engagements,
        "cpm": cpm,
        "cpv": cpv,
        "cpc": cpc,
        "cpe": cpe,
        "vtr": vtr,
        "completion_rate": completion_rate,
        "ctr": ctr,
    }


def _build_allocation(key: str, media: dict, mode_key: str, mode_def: dict, line_budget: int, budget_total: int,
                       score: float, target_info: dict, objective: str) -> dict:
    return {
        "media": key,
        "media_name": media["name"],
        "mode": mode_key,
        "optimization": mode_def["label"],
        "budget": line_budget,
        "share": round(line_budget / budget_total, 3),
        "score": round(score, 2),
        "targeting": {
            "age": [target_info["age_min"], target_info["age_max"]],
            "gender": target_info["gender"],
            "segments": target_info["interests"],
            "note": mode_def.get("targeting_note"),
        },
        "operation_notes": list(media.get("operation_notes") or []) + [COMMON_OPERATION_NOTES[objective]],
    }


# ---------------------------------------------------------------------------
# 媒体集約（simulation.by_media）/ 合計（simulation.total、純リーチ）
# ---------------------------------------------------------------------------

def _sum_with_none(values: list) -> int | None:
    """全て None なら None、そうでなければ None を0扱いで合算する。"""
    if not values or all(v is None for v in values):
        return None
    return sum((v or 0) for v in values)


def _dedup_reach(reaches: list[int], overlap: float) -> int:
    """降順ソートし、最大値 + (1-overlap) × 残り合計 で重複排除する。"""
    if not reaches:
        return 0
    ordered = sorted(reaches, reverse=True)
    return int(ordered[0] + (1 - overlap) * sum(ordered[1:]))


def _aggregate_by_media(by_line: list[dict], candidates: dict, intra_media_overlap: float) -> list[dict]:
    order: list[str] = []
    groups: dict[str, list[dict]] = {}
    for line in by_line:
        key = line["media"]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(line)

    result = []
    for key in order:
        lines = groups[key]
        budget = sum(l["budget"] for l in lines)
        impressions = sum(l["impressions"] for l in lines)
        views = sum(l["views"] for l in lines)
        completed_views = sum(l["completed_views"] for l in lines)
        clicks = _sum_with_none([l["clicks"] for l in lines])
        reach = _dedup_reach([l["reach"] for l in lines], intra_media_overlap)

        cpm = round(budget / impressions * 1000, 1) if impressions else None
        cpv = round(budget / views, 2) if views else None
        vtr = round(views / impressions, 4) if impressions else None

        result.append({
            "media": key,
            "budget": budget,
            "impressions": impressions,
            "views": views,
            "completed_views": completed_views,
            "reach": reach,
            "clicks": clicks,
            "cpm": cpm,
            "cpv": cpv,
            "vtr": vtr,
            "view_definition": candidates[key]["view_definition"],
        })
    return result


def _universe_size(reach_model: dict, gender: str, age_min: int, age_max: int) -> float:
    """母集団 U = base × age係数（重なり年数按分） × gender_share、下限 floor。"""
    universe = reach_model["universe"]
    age_coef = 0.0
    for row_min, row_max, share in universe["age_share"]:
        overlap = min(row_max, age_max) - max(row_min, age_min) + 1
        width = row_max - row_min + 1
        if overlap > 0 and width > 0:
            age_coef += share * (overlap / width)
    gender_share = universe["gender_share"].get(gender, 1.0)
    u = universe["base"] * age_coef * gender_share
    return max(u, universe["floor"])


def _aggregate_total(by_media: list[dict], budget_total: int, reach_model: dict,
                      gender: str, age_min: int, age_max: int) -> dict:
    impressions = sum(m["impressions"] for m in by_media)
    views = sum(m["views"] for m in by_media)
    completed_views = sum(m["completed_views"] for m in by_media)
    clicks = _sum_with_none([m["clicks"] for m in by_media])

    raw_reach = _dedup_reach([m["reach"] for m in by_media], reach_model["inter_media_overlap"])
    u = _universe_size(reach_model, gender, age_min, age_max)
    total_reach = int(u * (1 - math.exp(-raw_reach / u)))

    cpm = round(budget_total / impressions * 1000, 1) if impressions else None
    cpv = round(budget_total / views, 2) if views else None
    ctr = round(clicks / impressions, 4) if (clicks is not None and impressions) else None

    return {
        "budget": budget_total,
        "impressions": impressions,
        "views": views,
        "completed_views": completed_views,
        "reach": total_reach,
        "clicks": clicks,
        "cpm": cpm,
        "cpv": cpv,
        "ctr": ctr,
    }


# ---------------------------------------------------------------------------
# kpi_projection / warnings（基準6）
# ---------------------------------------------------------------------------

def _build_kpi_projection(order: dict, total: dict) -> dict:
    kpi = order.get("kpi")
    target = order.get("kpi_target")

    if kpi not in _KPI_FIELD_MAP:
        return {
            "kpi": kpi, "target": target, "projected": None, "achievement": None,
            "note": "このKPIは自動projectionに未対応",
        }

    projected = total[_KPI_FIELD_MAP[kpi]]
    label, unit = _KPI_LABELS[kpi]

    achievement = None
    if target is not None and projected is not None:
        if kpi in _KPI_COST_METRICS:
            if projected:
                achievement = round(target / projected, 3)
        elif target:
            achievement = round(projected / target, 3)

    if target is None:
        note = f"主KPI『{kpi}』→ {label} {io.fmt_num(projected)}{unit}（与件数値未設定のため見込み値のみ提示）"
    else:
        pct = io.fmt_pct(achievement) if achievement is not None else "-"
        note = (
            f"主KPI『{kpi}』→ {label} {io.fmt_num(projected)}{unit}"
            f"（与件 {io.fmt_num(target)}{unit}に対し達成見込み {pct}）"
        )

    return {"kpi": kpi, "target": target, "projected": projected, "achievement": achievement, "note": note}


def _build_warnings(reserved_info: dict, kpi_projection: dict) -> list[str]:
    warnings: list[str] = []
    if reserved_info.get("warning"):
        warnings.append(reserved_info["warning"])

    achievement = kpi_projection.get("achievement")
    if achievement is not None and achievement < 1.0:
        kpi = kpi_projection.get("kpi")
        warnings.append(
            f"主KPI({kpi})の与件達成見込みが100%を下回っています（{io.fmt_pct(achievement)}）。"
            "予算増額または与件調整の相談を推奨"
        )
    return warnings


# ---------------------------------------------------------------------------
# strategy_summary
# ---------------------------------------------------------------------------

def _build_strategy_summary(
    objective: str,
    active_sorted: list[str],
    candidates: dict,
    preferred_set: set,
    primary_role: str,
    secondary_role: str,
    mode_split: dict,
    reserved_info: dict,
) -> str:
    label = OBJECTIVE_LABELS.get(objective, objective)
    score_driven = [m for m in active_sorted if m not in preferred_set]
    preferred_selected = [m for m in active_sorted if m in preferred_set]

    if score_driven:
        names = "・".join(candidates[m]["name"] for m in score_driven)
        base = f"目的「{label}」に対しターゲット適合度とスコアが高い{names}を中心に、計{len(active_sorted)}媒体を選定した。"
    else:
        base = f"目的「{label}」に基づき、計{len(active_sorted)}媒体を選定した。"
    if preferred_selected:
        pref_names = "・".join(candidates[m]["name"] for m in preferred_selected)
        base += f"（希望媒体の{pref_names}を含む）"
    sentences = [base]

    primary_label = _ROLE_LABELS.get(primary_role, primary_role)
    secondary_label = _ROLE_LABELS.get(secondary_role, secondary_role)
    primary_pct = io.fmt_pct(mode_split["primary"], 0)
    secondary_pct = io.fmt_pct(mode_split["secondary"], 0)
    sentences.append(
        f"配信ラインは目的に直結する{primary_label}モードに予算の{primary_pct}、"
        f"補完となる{secondary_label}モードに{secondary_pct}を配分し、効率とリーチの網羅性を両立させる。"
    )

    if reserved_info.get("applied"):
        monthly = io.fmt_yen(reserved_info.get("monthly_budget"))
        sentences.append(
            f"月額換算予算が{monthly}と潤沢なため、{reserved_info['media_name']}の予約型枠"
            f"（{reserved_info['mode_label']}）に{io.fmt_yen(reserved_info['budget'])}を追加確保し、"
            "短期集中でのリーチ最大化を図る。"
        )
    elif reserved_info.get("warning"):
        sentences.append("月額換算予算は潤沢だが、予約型の最低出稿金額に満たないため予約型枠は見送り、通常配信に予算を集中する。")
    else:
        sentences.append("予約型枠の追加条件（目的が認知/リーチ、かつ月額換算予算が潤沢）を満たさないため、通常配信のみで構成する。")

    sentences.append("リーチは媒体内・媒体間の重複を排除した純リーチで評価する。")

    return "".join(sentences)


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------

def build_plan(order: dict, benchmarks: dict, generated_at: datetime | None = None) -> dict:
    """order から媒体プラン + シミュレーションを生成し、docs/SCHEMAS.md の plan.yaml v2 スキーマに従った dict を返す。"""
    objective = order.get("objective")
    if objective not in io.VALID_OBJECTIVES:
        raise io.SchemaError(
            f"objective '{objective}' は不正です（{'/'.join(io.VALID_OBJECTIVES)}）"
        )

    all_media = benchmarks.get("media") or {}
    excluded = set(order.get("excluded_media") or [])
    candidates = {key: media for key, media in all_media.items() if key not in excluded}
    if not candidates:
        raise io.SchemaError("除外媒体の指定により候補媒体がありません")

    target = order.get("target") or {}
    gender = target.get("gender", "all")
    age_range = target.get("age", [13, 99])
    age_min, age_max = int(age_range[0]), int(age_range[1])
    interests = list(target.get("interests") or [])
    target_info = {"age_min": age_min, "age_max": age_max, "gender": gender, "interests": interests}

    preferred = [m for m in (order.get("preferred_media") or []) if m in candidates]
    preferred_set = set(preferred)

    scores = {
        key: _score_media(media, objective, gender, age_min, age_max) * (1.3 if key in preferred_set else 1.0)
        for key, media in candidates.items()
    }

    budget_total = int(order["budget_total"])
    selected = _select_media(candidates, scores, budget_total, preferred)
    min_budgets = {key: candidates[key]["min_budget"] for key in candidates}

    # 予約型ルール（基準2）
    reserved_info = _compute_reserved(order, benchmarks, objective, candidates, scores, budget_total)
    remaining_budget = budget_total - (reserved_info["budget"] if reserved_info["applied"] else 0)

    # 残り予算を選定媒体に配分
    allocation = _allocate_budget(selected, scores, min_budgets, preferred_set, remaining_budget)
    active_sorted = sorted(allocation.keys(), key=lambda k: -scores[k])

    primary_role, secondary_role = _primary_secondary_roles(objective)
    mode_split = benchmarks["mode_split"]

    by_line: list[dict] = []
    allocations: list[dict] = []

    for key in active_sorted:
        media = candidates[key]
        media_budget = allocation[key]
        for mode_key, mode_def, line_budget in _mode_lines_for_media(
            media, media_budget, primary_role, secondary_role, mode_split
        ):
            sim = _simulate_line(line_budget, mode_def)
            by_line.append({"media": key, "mode": mode_key, "budget": line_budget, **sim})
            allocations.append(
                _build_allocation(key, media, mode_key, mode_def, line_budget, budget_total,
                                   scores[key], target_info, objective)
            )

    # 予約型ラインは末尾に追加
    if reserved_info["applied"]:
        r_key = reserved_info["media"]
        r_media = candidates[r_key]
        r_mode_def = r_media["modes"][reserved_info["mode"]]
        r_budget = reserved_info["budget"]
        sim = _simulate_line(r_budget, r_mode_def)
        by_line.append({"media": r_key, "mode": reserved_info["mode"], "budget": r_budget, **sim})
        allocations.append(
            _build_allocation(r_key, r_media, reserved_info["mode"], r_mode_def, r_budget, budget_total,
                               scores[r_key], target_info, objective)
        )

    reach_model = benchmarks["reach_model"]
    by_media = _aggregate_by_media(by_line, candidates, reach_model["intra_media_overlap"])
    total = _aggregate_total(by_media, budget_total, reach_model, gender, age_min, age_max)

    kpi_projection = _build_kpi_projection(order, total)
    warnings = _build_warnings(reserved_info, kpi_projection)

    strategy_summary = _build_strategy_summary(
        objective, active_sorted, candidates, preferred_set,
        primary_role, secondary_role, mode_split, reserved_info,
    )

    generated_at = generated_at or datetime.now()

    return {
        "campaign_id": order["campaign_id"],
        "generated_at": generated_at.isoformat(),
        "objective": objective,
        "strategy_summary": strategy_summary,
        "allocations": allocations,
        "simulation": {
            "by_line": by_line,
            "by_media": by_media,
            "total": total,
        },
        "kpi_projection": kpi_projection,
        "warnings": warnings,
    }
