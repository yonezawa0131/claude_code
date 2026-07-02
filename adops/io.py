"""共有I/O: order.yaml / plan.yaml / actuals.csv / benchmarks.yaml の読み書き。

スキーマは docs/SCHEMAS.md を正とする。
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARKS = REPO_ROOT / "config" / "benchmarks.yaml"
CAMPAIGNS_DIR = REPO_ROOT / "campaigns"

VALID_OBJECTIVES = ("awareness", "reach", "video_views", "consideration")

ACTUALS_INT_COLS = ("cost", "impressions", "views", "completed_views", "clicks", "reach")


class SchemaError(ValueError):
    """入力ファイルがスキーマを満たさない場合のエラー。"""


def _to_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def load_yaml(path: Path | str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(data: dict, path: Path | str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def load_benchmarks(path: Path | str = DEFAULT_BENCHMARKS) -> dict:
    data = load_yaml(path)
    if "media" not in data or not data["media"]:
        raise SchemaError(f"{path}: 'media' が定義されていません")
    return data


def load_order(campaign_dir: Path | str) -> dict:
    path = Path(campaign_dir) / "order.yaml"
    order = load_yaml(path)

    for key in ("campaign_id", "objective", "period", "budget_total", "target"):
        if key not in order:
            raise SchemaError(f"{path}: 必須キー '{key}' がありません")
    if order["objective"] not in VALID_OBJECTIVES:
        raise SchemaError(
            f"{path}: objective '{order['objective']}' は不正です（{'/'.join(VALID_OBJECTIVES)}）"
        )
    order["period"]["start"] = _to_date(order["period"]["start"])
    order["period"]["end"] = _to_date(order["period"]["end"])
    if order["period"]["end"] < order["period"]["start"]:
        raise SchemaError(f"{path}: period.end が period.start より前です")
    if int(order["budget_total"]) <= 0:
        raise SchemaError(f"{path}: budget_total は正の整数にしてください")

    order.setdefault("preferred_media", []) or order.update(preferred_media=[])
    order.setdefault("excluded_media", []) or order.update(excluded_media=[])
    target = order["target"]
    target.setdefault("gender", "all")
    target.setdefault("age", [13, 99])
    target.setdefault("interests", []) or target.update(interests=[])
    return order


def load_plan(campaign_dir: Path | str) -> dict:
    return load_yaml(Path(campaign_dir) / "plan.yaml")


def save_plan(plan: dict, campaign_dir: Path | str) -> Path:
    path = Path(campaign_dir) / "plan.yaml"
    save_yaml(plan, path)
    return path


def load_actuals(campaign_dir: Path | str) -> list[dict]:
    """actuals.csv を行のリストで返す。ファイルがなければ空リスト。

    各行: {"date": date, "media": str, "cost": int, ...}（空欄の数値列は None）
    """
    path = Path(campaign_dir) / "actuals.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            if not (row.get("date") or "").strip():
                continue
            parsed = {"date": _to_date(row["date"].strip()), "media": row["media"].strip()}
            for col in ACTUALS_INT_COLS:
                raw = (row.get(col) or "").strip()
                parsed[col] = int(raw) if raw else None
            if parsed["cost"] is None:
                raise SchemaError(f"{path}:{i}: cost 列は必須です")
            rows.append(parsed)
    return rows


def list_campaigns(root: Path | str = CAMPAIGNS_DIR) -> list[Path]:
    root = Path(root)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "order.yaml").exists())


def fmt_yen(value) -> str:
    return "-" if value is None else f"¥{round(value):,}"


def fmt_num(value) -> str:
    return "-" if value is None else f"{round(value):,}"


def fmt_pct(value, digits: int = 1) -> str:
    return "-" if value is None else f"{value * 100:.{digits}f}%"
