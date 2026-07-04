#!/usr/bin/env python3
"""claude.ai のデータエクスポートを Obsidian vault にインポートする。

入力:  claude.ai の「設定 → プライバシー → データをエクスポート」で届く
       ZIP(そのまま渡せる)、または展開済みの conversations.json。
出力:  vault の `inbox/ClaudeChat Memory/` 配下に 1 会話 = 1 Markdown。
       併せて全会話への索引ノート `_Index.md` を再生成する。

使い方:
    python3 scripts/claude_export_to_obsidian.py <export.zip | conversations.json> --vault <vaultのパス>

例:
    python3 scripts/claude_export_to_obsidian.py ~/Downloads/data-2026-07-04.zip --vault ~/Obsidian/MyVault

再実行は安全(冪等)。同じ会話(uuid)は上書き更新され、タイトル変更時は
旧ファイルを差し替える。標準ライブラリのみで動く。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DEST = "inbox/ClaudeChat Memory"
INDEX_NAME = "_Index.md"

# Obsidian のファイル名・wikilink で問題になる文字
FILENAME_BAD_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]]')
MAX_TITLE_LEN = 80


def load_conversations(src: Path) -> list[dict]:
    if src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as zf:
            names = [n for n in zf.namelist() if n.endswith("conversations.json")]
            if not names:
                sys.exit(f"error: {src} の中に conversations.json が見つかりません")
            with zf.open(names[0]) as f:
                return json.load(f)
    if src.is_dir():
        src = src / "conversations.json"
    if not src.exists():
        sys.exit(f"error: {src} が見つかりません")
    return json.loads(src.read_text(encoding="utf-8"))


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def sanitize_title(title: str) -> str:
    title = FILENAME_BAD_CHARS.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip().rstrip(".")
    if len(title) > MAX_TITLE_LEN:
        title = title[:MAX_TITLE_LEN].rstrip()
    return title or "Untitled"


def message_text(msg: dict) -> str:
    """text フィールド優先。無ければ content ブロック(新形式)から組み立てる。"""
    text = (msg.get("text") or "").strip()
    if text:
        return text
    parts = []
    for block in msg.get("content") or []:
        if block.get("type") == "text" and block.get("text"):
            parts.append(block["text"])
    return "\n\n".join(parts).strip()


def render_conversation(conv: dict) -> tuple[str, datetime | None]:
    created = parse_ts(conv.get("created_at"))
    updated = parse_ts(conv.get("updated_at"))
    title = (conv.get("name") or "").strip() or "Untitled"
    messages = conv.get("chat_messages") or []

    lines = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"uuid: {conv.get('uuid', '')}",
        f"created: {created.isoformat() if created else ''}",
        f"updated: {updated.isoformat() if updated else ''}",
        f"messages: {len(messages)}",
        "tags:",
        "  - claude-chat",
        "---",
        "",
    ]

    for msg in messages:
        sender = "Human" if msg.get("sender") == "human" else "Claude"
        ts = parse_ts(msg.get("created_at"))
        stamp = f" — {ts.strftime('%Y-%m-%d %H:%M')}" if ts else ""
        lines.append(f"## {sender}{stamp}")
        lines.append("")
        body = message_text(msg)
        lines.append(body if body else "*(本文なし)*")
        lines.append("")
        attachments = msg.get("attachments") or []
        files = msg.get("files") or []
        names = [a.get("file_name") for a in attachments if a.get("file_name")]
        names += [f.get("file_name") for f in files if f.get("file_name")]
        if names:
            lines.append("> [!note] 添付: " + ", ".join(names))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n", created


def existing_uuid_map(dest: Path) -> dict[str, Path]:
    """dest 直下の md をスキャンし frontmatter の uuid → パス を返す。"""
    mapping: dict[str, Path] = {}
    if not dest.exists():
        return mapping
    for path in dest.glob("*.md"):
        if path.name == INDEX_NAME:
            continue
        try:
            with path.open(encoding="utf-8") as f:
                head = "".join(next(f, "") for _ in range(10))
        except OSError:
            continue
        m = re.search(r"^uuid: ([0-9a-f-]{36})$", head, re.MULTILINE)
        if m:
            mapping[m.group(1)] = path
    return mapping


def target_filename(dest: Path, conv: dict, created: datetime | None,
                    taken: set[str]) -> str:
    date = created.strftime("%Y-%m-%d") if created else "0000-00-00"
    title = sanitize_title((conv.get("name") or "").strip() or "Untitled")
    base = f"{date} {title}"
    name = f"{base}.md"
    if name in taken:  # 同日同タイトルの別会話
        name = f"{base} {conv.get('uuid', '')[:8]}.md"
    return name


def write_index(dest: Path, entries: list[tuple[datetime | None, str, str]]) -> None:
    """entries: (created, filename(拡張子なし), title)"""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    entries.sort(key=lambda e: e[0] or epoch, reverse=True)
    lines = [
        "---",
        "tags:",
        "  - claude-chat",
        "---",
        "",
        "# ClaudeChat Memory 索引",
        "",
        f"全 {len(entries)} 会話。claude.ai エクスポートから "
        f"`scripts/claude_export_to_obsidian.py` で生成(再実行で更新)。",
        "",
    ]
    current_month = None
    for created, stem, title in entries:
        month = created.strftime("%Y-%m") if created else "日付不明"
        if month != current_month:
            lines.append(f"## {month}")
            lines.append("")
            current_month = month
        day = created.strftime("%m/%d") if created else "--/--"
        alias = re.sub(r"[\[\]|]", " ", title)
        alias = re.sub(r"\s+", " ", alias).strip()
        lines.append(f"- {day} [[{stem}|{alias}]]")
    (dest / INDEX_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", type=Path,
                    help="エクスポート ZIP / conversations.json / 展開済みディレクトリ")
    ap.add_argument("--vault", type=Path, required=True, help="Obsidian vault のルート")
    ap.add_argument("--dest", default=DEFAULT_DEST,
                    help=f"vault 内の出力先(既定: {DEFAULT_DEST})")
    ap.add_argument("--skip-existing", action="store_true",
                    help="既に取り込んだ会話(uuid 一致)を上書きしない")
    args = ap.parse_args()

    conversations = load_conversations(args.export)
    dest = args.vault / args.dest
    dest.mkdir(parents=True, exist_ok=True)

    by_uuid = existing_uuid_map(dest)
    taken = {p.name for p in dest.glob("*.md")}
    index_entries: list[tuple[datetime | None, str, str]] = []
    created_n = updated_n = skipped_n = empty_n = 0

    for conv in conversations:
        if not (conv.get("chat_messages") or []):
            empty_n += 1
            continue
        content, created = render_conversation(conv)
        uuid = conv.get("uuid", "")
        title = (conv.get("name") or "").strip() or "Untitled"
        old = by_uuid.get(uuid)

        if old and args.skip_existing:
            skipped_n += 1
            index_entries.append((created, old.stem, title))
            continue

        name = target_filename(dest, conv, created, taken - ({old.name} if old else set()))
        path = dest / name
        if old and old != path:  # タイトル/日付が変わった → 旧ファイルを差し替え
            old.unlink()
            taken.discard(old.name)
        if old:
            updated_n += 1
        else:
            created_n += 1
        path.write_text(content, encoding="utf-8")
        taken.add(name)
        index_entries.append((created, path.stem, title))

    write_index(dest, index_entries)
    print(f"完了: 新規 {created_n} / 更新 {updated_n} / スキップ {skipped_n}"
          f" / 空会話を除外 {empty_n} → {dest}")


if __name__ == "__main__":
    main()
