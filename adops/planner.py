"""媒体プランニング: order.yaml + benchmarks.yaml から plan.yaml 相当の dict を生成する。

スキーマは docs/SCHEMAS.md を正とする。
"""
from __future__ import annotations

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
    """score 比例で配分し、min_budget を下回る媒体を落として再配分する。"""
    active = list(selected)
    while True:
        if len(active) == 1:
            return {active[0]: budget_total}

        total_score = sum(scores[m] for m in active)
        raw = {m: budget_total * scores[m] / total_score for m in active}
        rounded = {m: int(round(raw[m] / 1000.0)) * 1000 for m in active}

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


def _build_strategy_summary(
    objective: str,
    active_sorted: list[str],
    candidates: dict,
    preferred_set: set,
) -> str:
    label = OBJECTIVE_LABELS.get(objective, objective)
    score_driven = [m for m in active_sorted if m not in preferred_set]
    preferred_selected = [m for m in active_sorted if m in preferred_set]

    sentences = []
    if score_driven:
        names = "・".join(candidates[m]["name"] for m in score_driven)
        sentences.append(
            f"目的「{label}」に対しターゲット適合度とスコアが高い{names}を中心に、"
            f"計{len(active_sorted)}媒体を選定した。"
        )
    else:
        sentences.append(f"目的「{label}」に基づき、計{len(active_sorted)}媒体を選定した。")

    if preferred_selected:
        pref_names = "・".join(candidates[m]["name"] for m in preferred_selected)
        sentences.append(f"希望媒体として指定された{pref_names}も選定に含めている。")

    sentences.append(
        "予算は各媒体のスコア（目的適合度×ターゲット適合度）比率で配分し、"
        "最低出稿金額を下回る媒体は除外のうえ再配分することで実行可能な構成とした。"
    )
    return "".join(sentences)


def build_plan(order: dict, benchmarks: dict, generated_at: datetime | None = None) -> dict:
    """order から媒体プラン + シミュレーションを生成し、docs/SCHEMAS.md の plan.yaml スキーマに従った dict を返す。"""
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

    preferred = [m for m in (order.get("preferred_media") or []) if m in candidates]
    preferred_set = set(preferred)

    scores = {
        key: _score_media(media, objective, gender, age_min, age_max) * (1.3 if key in preferred_set else 1.0)
        for key, media in candidates.items()
    }

    budget_total = int(order["budget_total"])
    selected = _select_media(candidates, scores, budget_total, preferred)

    min_budgets = {key: candidates[key]["min_budget"] for key in candidates}
    allocation = _allocate_budget(selected, scores, min_budgets, preferred_set, budget_total)

    active_sorted = sorted(allocation.keys(), key=lambda k: -scores[k])

    allocations = []
    by_media = []
    for key in active_sorted:
        media = candidates[key]
        budget = allocation[key]

        impressions = int(round(budget / media["cpm"] * 1000))
        views = int(round(impressions * media["vtr"]))
        completed_views = int(round(impressions * media["completion_rate"]))
        reach = int(round(impressions / media["avg_frequency"]))
        cpv = round(budget / views, 2) if views else None

        allocations.append(
            {
                "media": key,
                "media_name": media["name"],
                "budget": budget,
                "share": round(budget / budget_total, 3),
                "score": round(scores[key], 2),
                "optimization": media["optimization_by_objective"][objective],
                "targeting": {
                    "age": [age_min, age_max],
                    "gender": gender,
                    "segments": interests,
                },
                "operation_notes": list(media.get("operation_notes") or []) + [COMMON_OPERATION_NOTES[objective]],
            }
        )
        by_media.append(
            {
                "media": key,
                "budget": budget,
                "impressions": impressions,
                "views": views,
                "completed_views": completed_views,
                "reach": reach,
                "cpm": media["cpm"],
                "cpv": cpv,
                "vtr": media["vtr"],
                "view_definition": media["view_definition"],
            }
        )

    total_impressions = sum(m["impressions"] for m in by_media)
    total_views = sum(m["views"] for m in by_media)
    total_completed_views = sum(m["completed_views"] for m in by_media)
    reach_sum = sum(m["reach"] for m in by_media)

    overlap_rate = benchmarks.get("reach_overlap_rate", 0.05)
    factor = max(0.5, 1 - overlap_rate * (len(active_sorted) - 1))
    total_reach = int(round(reach_sum * factor))

    total_cpm = round(budget_total / total_impressions * 1000, 1) if total_impressions else None
    total_cpv = round(budget_total / total_views, 2) if total_views else None

    simulation = {
        "total": {
            "budget": budget_total,
            "impressions": total_impressions,
            "views": total_views,
            "completed_views": total_completed_views,
            "reach": total_reach,
            "cpm": total_cpm,
            "cpv": total_cpv,
        },
        "by_media": by_media,
    }

    strategy_summary = _build_strategy_summary(objective, active_sorted, candidates, preferred_set)

    generated_at = generated_at or datetime.now()

    return {
        "campaign_id": order["campaign_id"],
        "generated_at": generated_at.isoformat(),
        "objective": objective,
        "strategy_summary": strategy_summary,
        "allocations": allocations,
        "simulation": simulation,
    }
