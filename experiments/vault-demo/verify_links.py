#!/usr/bin/env python3
"""vault-demo の健全性検証。

Vault ルート(このファイルのある experiments/vault-demo/)で実行する。
検証項目:
  1. [[wikilink]] が Vault 内の <name>.md に解決するか(リンク切れ検出)
  2. raw/ を指す Markdown リンクの実パスが存在するか(出典切れ検出)
  3. 孤立ノート(どこからも [[ ]] されない compiled ページ)
  4. リンク密度(wikilink エッジ数 / compiled ページ数)
  5. INDEX.md が entities/ concepts/ の全実ファイルに言及しているか

終了コード: 問題ゼロなら 0、あれば 1。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
MDLINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

COMPILED_DIRS = ["entities", "concepts"]


def md_files() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.md") if "raw/" not in p.relative_to(ROOT).as_posix())


def stem_index() -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for p in md_files():
        idx[p.stem] = p
    return idx


def main() -> int:
    files = md_files()
    stems = stem_index()
    problems: list[str] = []

    incoming: dict[str, int] = {p.stem: 0 for p in files}
    total_edges = 0

    for path in files:
        raw_text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()

        # コードスパン/コードブロック内の [[...]] や (...) はリンクではない(Obsidian も
        # リンク化しない)ので、抽出前に除去して誤検出を防ぐ。
        text = re.sub(r"```.*?```", "", raw_text, flags=re.DOTALL)
        text = re.sub(r"`[^`\n]*`", "", text)

        for m in WIKILINK.finditer(text):
            target = m.group(1).strip()
            total_edges += 1
            if target not in stems:
                problems.append(f"[リンク切れ] {rel}: [[{target}]] は存在しない")
            else:
                incoming[target] = incoming.get(target, 0) + 1

        for m in MDLINK.finditer(text):
            href = m.group(1).strip()
            if href.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = (path.parent / href).resolve()
            if not target_path.exists():
                problems.append(f"[出典切れ] {rel}: {href} が実在しない")

    # 孤立ノート(compiled のみ対象。ルートの INDEX/README/NOW は除外)
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if not any(rel.startswith(d + "/") for d in COMPILED_DIRS):
            continue
        if incoming.get(path.stem, 0) == 0:
            problems.append(f"[孤立ノート] {rel}: どこからもリンクされていない")

    # INDEX 同期
    index_text = (ROOT / "INDEX.md").read_text(encoding="utf-8")
    index_stems = {m.group(1).strip() for m in WIKILINK.finditer(index_text)}
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(d + "/") for d in COMPILED_DIRS) and path.stem not in index_stems:
            problems.append(f"[INDEX 未同期] {rel} が INDEX.md に無い")

    compiled_count = sum(
        1 for p in files
        if any(p.relative_to(ROOT).as_posix().startswith(d + "/") for d in COMPILED_DIRS)
    )
    density = total_edges / compiled_count if compiled_count else 0.0

    print(f"compiled ページ数: {compiled_count}")
    print(f"wikilink エッジ総数: {total_edges}")
    print(f"リンク密度(エッジ/compiled ページ): {density:.2f}")
    print(f"検出された問題: {len(problems)}")
    for p in problems:
        print("  - " + p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
