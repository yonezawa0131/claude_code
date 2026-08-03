"""追記専用の記録。

## なぜ要るか

自動で動くものは、**あとから「なぜそうしたのか」を再現できないと直せない**。
そして事故が起きるのはたいてい、記録が残っていない部分になる。

この journal は追記しかしない。書き換えも削除もしない。
1行1イベントの JSON Lines で、人間が読めて grep できる形にしてある。

記録するのは結果だけではなく、**その判断に使った入力**も含める。
「なぜこの注文を出したか」を、あとから同じ入力で再計算して確かめられる。
"""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Journal:
    """1回の実行を通しての記録。"""

    path: Path
    #: この実行を識別する文字列。1回の実行のイベントを束ねる
    run_id: str = field(default_factory=lambda: _now().replace(":", "").replace("-", ""))
    #: 実際に書き込むか。False なら標準出力にだけ出す
    enabled: bool = True

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.enabled:
            os.makedirs(self.path.parent, exist_ok=True)

    def write(self, event: str, **fields: Any) -> dict:
        """1件記録する。"""
        record = {"time": _now(), "run_id": self.run_id, "event": event, **fields}
        if self.enabled:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record

    def read_all(self) -> list[dict]:
        """記録を全部読む。集計や検算に使う。"""
        if not self.path.exists():
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def runs(self) -> list[str]:
        """記録されている実行IDを、古い順に返す。"""
        seen: list[str] = []
        for rec in self.read_all():
            rid = rec.get("run_id")
            if rid and rid not in seen:
                seen.append(rid)
        return seen
