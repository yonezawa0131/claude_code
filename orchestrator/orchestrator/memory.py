"""エピソード記憶 — 実行結果を保存し、Router の学習と類似事例の想起に使う。

JSON ファイル1つのシンプルな実装。ベクトル検索が必要になったら
find_similar() の中身だけ差し替えればよい。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_EPISODES = 1000


class MemoryStore:
    def __init__(self, path: str | Path = ".orchestrator/episodes.json"):
        self._path = Path(path)
        self._episodes: list[dict[str, Any]] = self._load()

    # ── 記録 ──────────────────────────────────────────────

    def store_episode(
        self,
        *,
        task_type: str,
        description: str,
        model: str,
        success: bool,
        quality_score: float,
        cost_usd: float,
        attempts: int = 1,
    ) -> None:
        self._episodes.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_type": task_type,
                "description": description[:500],
                "model": model,
                "success": success,
                "quality_score": quality_score,
                "cost_usd": cost_usd,
                "attempts": attempts,
            }
        )
        if len(self._episodes) > MAX_EPISODES:
            self._episodes = self._episodes[-MAX_EPISODES:]
        self._save()

    # ── 想起 ──────────────────────────────────────────────

    def best_model_for_type(self, task_type: str) -> dict[str, Any] | None:
        """タスク種別ごとに品質/コストのバランスが最良のモデルを返す。"""
        relevant = [e for e in self._episodes if e["task_type"] == task_type]
        if not relevant:
            return None

        stats: dict[str, dict[str, float]] = {}
        for e in relevant:
            s = stats.setdefault(e["model"], {"n": 0, "ok": 0, "quality": 0.0, "cost": 0.0})
            s["n"] += 1
            s["ok"] += 1 if e["success"] else 0
            s["quality"] += e["quality_score"]
            s["cost"] += e["cost_usd"]

        def score(item: tuple[str, dict[str, float]]) -> float:
            s = item[1]
            avg_quality = s["quality"] / s["n"]
            avg_cost = s["cost"] / s["n"]
            # 品質重視・コストで微調整
            return avg_quality * 0.7 - min(avg_cost, 1.0) * 0.3

        model, s = max(stats.items(), key=score)
        return {
            "model": model,
            "samples": int(s["n"]),
            "success_rate": s["ok"] / s["n"],
            "avg_quality": s["quality"] / s["n"],
        }

    def find_similar(self, description: str, task_type: str | None = None, limit: int = 3) -> list[dict[str, Any]]:
        """キーワード重なりによる簡易類似検索。成功例を品質順で返す。"""
        words = set(_tokenize(description))
        if not words:
            return []
        candidates = [
            e
            for e in self._episodes
            if e["success"] and (task_type is None or e["task_type"] == task_type)
        ]

        def similarity(e: dict[str, Any]) -> float:
            overlap = words & set(_tokenize(e["description"]))
            return len(overlap) / len(words)

        scored = [(similarity(e), e) for e in candidates]
        scored = [(s, e) for s, e in scored if s > 0]
        scored.sort(key=lambda x: (x[0], x[1]["quality_score"]), reverse=True)
        return [e for _, e in scored[:limit]]

    def count_similar_successes(self, task_type: str) -> int:
        return sum(1 for e in self._episodes if e["task_type"] == task_type and e["success"])

    # ── 永続化 ────────────────────────────────────────────

    def _load(self) -> list[dict[str, Any]]:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._episodes, ensure_ascii=False, indent=2))


def _tokenize(text: str) -> list[str]:
    # 英単語と、日本語は2文字ごとのbi-gramで雑に分割(依存ライブラリなし)
    ascii_words = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    cjk = re.findall(r"[぀-ヿ一-鿿]+", text)
    bigrams = [chunk[i : i + 2] for chunk in cjk for i in range(len(chunk) - 1)]
    return ascii_words + bigrams
