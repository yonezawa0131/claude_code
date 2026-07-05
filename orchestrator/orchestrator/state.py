"""StateManager — 長時間実行の状態管理。

STATE.md(人間が読む)と state.json(機械が再開に使う)の両方を書く。
コスト追跡と上限強制もここが担当する。
運用ルールは .claude/skills/long-task-state/SKILL.md に準拠。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import estimate_cost


class CostLimitExceeded(Exception):
    pass


class StateManager:
    def __init__(
        self,
        session_id: str,
        *,
        goal: str = "",
        budget_usd: float = 10.0,
        directory: str | Path = ".orchestrator",
    ):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._md_path = self._dir / "STATE.md"
        self._json_path = self._dir / f"state_{session_id}.json"
        self._start = time.monotonic()

        if self._json_path.exists():
            self.state: dict[str, Any] = json.loads(self._json_path.read_text())
        else:
            self.state = {
                "session_id": session_id,
                "goal": goal,
                "status": "initialized",
                "current_phase": None,
                "checkpoints": [],
                "errors": [],
                "cost": {"input_tokens": 0, "output_tokens": 0, "usd": 0.0, "limit_usd": budget_usd},
                "started_at": _now(),
            }
            self._write()

    # ── チェックポイント / 再開 ─────────────────────────────

    def checkpoint(self, phase: str, data: dict[str, Any] | None = None) -> None:
        self.state["checkpoints"].append(
            {"phase": phase, "at": _now(), "data": data or {}}
        )
        self.state["current_phase"] = phase
        self._write()

    def resume_data(self, phase: str) -> dict[str, Any] | None:
        """指定フェーズの最新チェックポイントデータ(再開用)。無ければ None。"""
        for cp in reversed(self.state["checkpoints"]):
            if cp["phase"] == phase:
                return cp["data"]
        return None

    def completed_phases(self) -> list[str]:
        return [cp["phase"] for cp in self.state["checkpoints"]]

    # ── コスト ────────────────────────────────────────────

    def track_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        cost = estimate_cost(model, input_tokens, output_tokens)
        c = self.state["cost"]
        c["input_tokens"] += input_tokens
        c["output_tokens"] += output_tokens
        c["usd"] = round(c["usd"] + cost, 6)
        self._write()
        if c["usd"] >= c["limit_usd"]:
            self.set_status("halted_cost_limit")
            raise CostLimitExceeded(
                f"コスト上限到達: ${c['usd']:.4f} / ${c['limit_usd']:.2f}"
            )
        return cost

    @property
    def total_cost(self) -> float:
        return self.state["cost"]["usd"]

    @property
    def remaining_budget(self) -> float:
        c = self.state["cost"]
        return max(0.0, c["limit_usd"] - c["usd"])

    # ── その他 ────────────────────────────────────────────

    def record_error(self, message: str) -> None:
        self.state["errors"].append({"at": _now(), "message": message})
        self._write()

    def set_status(self, status: str) -> None:
        self.state["status"] = status
        self._write()

    def elapsed_seconds(self) -> int:
        return int(time.monotonic() - self._start)

    # ── 出力 ──────────────────────────────────────────────

    def _write(self) -> None:
        self._json_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2)
        )
        self._md_path.write_text(self._render_md())

    def _render_md(self) -> str:
        s = self.state
        c = s["cost"]
        lines = [
            f"# STATE.md — {s['session_id']}",
            "",
            "## ゴール(開始時に固定)",
            s["goal"] or "(未設定)",
            "",
            "## ステータス",
            f"- 更新: {_now()}",
            f"- 状態: {s['status']}",
            f"- フェーズ: {s['current_phase']}",
            f"- コスト: ${c['usd']:.4f} / ${c['limit_usd']:.2f}"
            f" (in {c['input_tokens']:,} / out {c['output_tokens']:,} tokens)",
            "",
            "## 完了フェーズ",
        ]
        for cp in s["checkpoints"]:
            lines.append(f"- [x] {cp['phase']} ({cp['at']})")
        if s["errors"]:
            lines += ["", "## エラー記録"]
            for e in s["errors"]:
                lines.append(f"- {e['at']} {e['message']}")
        return "\n".join(lines) + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
