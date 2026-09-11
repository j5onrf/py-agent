#!/usr/bin/env python3
"""Open Knowledge Format (OKF) Project Memory Manager"""

import os
import re
import shutil
import time
from typing import Any

RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
RE_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_\-]")


def _get_memory_dir(workspace_path: str) -> str:
    ws = os.path.realpath(os.path.expanduser(workspace_path or os.getcwd()))
    return os.path.join(ws, ".agent", "memory")


def parse_memory_file(filepath: str) -> dict[str, Any]:
    """Parses an OKF Markdown memory file with YAML frontmatter."""
    if not os.path.isfile(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read().strip()
        if not raw:
            return {}

        meta: dict[str, str] = {}
        body = raw
        if match := RE_FRONTMATTER.match(raw):
            fm_text = match.group(1)
            body = raw[match.end():].strip()
            for line in fm_text.splitlines():
                line_str = line.strip()
                if line_str and not line_str.startswith("#") and ":" in line_str:
                    k, v = line_str.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip("'\"")

        title = meta.get("title") or os.path.splitext(os.path.basename(filepath))[0]
        mem_type = meta.get("type", "note").lower()
        tags = [t.strip().lower() for t in meta.get("tags", "").split(",") if t.strip()]

        return {
            "path": filepath,
            "filename": os.path.basename(filepath),
            "title": title,
            "type": mem_type,
            "tags": tags,
            "content": body,
            "mtime": os.path.getmtime(filepath),
        }
    except OSError:
        return {}


def get_memory_count(workspace_path: str) -> int:
    """Returns total number of memory files in <workspace>/.agent/memory/."""
    mem_dir = _get_memory_dir(workspace_path)
    if not os.path.isdir(mem_dir):
        return 0
    try:
        return sum(1 for f in os.listdir(mem_dir) if f.endswith(".md"))
    except OSError:
        return 0


def list_memories(workspace_path: str) -> list[dict[str, Any]]:
    """Returns sorted list of all parsed memory items in the workspace."""
    mem_dir = _get_memory_dir(workspace_path)
    if not os.path.isdir(mem_dir):
        return []
    items: list[dict[str, Any]] = []
    try:
        for fname in sorted(os.listdir(mem_dir)):
            if fname.endswith(".md"):
                parsed = parse_memory_file(os.path.join(mem_dir, fname))
                if parsed:
                    items.append(parsed)
    except OSError:
        pass
    return items


def get_memory_context(workspace_path: str, max_tokens: int = 600) -> str:
    """Formats OKF memory files into a concise system prompt context block."""
    memories = list_memories(workspace_path)
    if not memories:
        return ""

    lines = [
        "### PROJECT MEMORY & ARCHITECTURAL DIRECTIVES:",
        "The following persistent project decisions, rules, and notes are active:",
    ]

    total_est_tokens = 0
    for m in memories:
        title = m["title"]
        mtype = m["type"]
        content = m["content"].strip().replace("\r\n", "\n")
        tags_str = f" [{', '.join(m['tags'])}]" if m["tags"] else ""

        # Compact one-liner vs structured block
        if "\n" not in content and len(content) <= 120:
            entry = f"* **[{mtype}] {title}**{tags_str}: {content}"
        else:
            entry = f"* **[{mtype}] {title}**{tags_str}:\n  {content.replace(chr(10), chr(10) + '  ')}"

        est_tokens = max(1, len(entry) // 4)
        if total_est_tokens + est_tokens > max_tokens:
            lines.append(f"... [{len(memories) - len(lines) + 2} additional memory files omitted]")
            break

        lines.append(entry)
        total_est_tokens += est_tokens

    return "\n".join(lines) + "\n"


def save_memory_file(
    workspace_path: str,
    title: str,
    content: str,
    mem_type: str = "decision",
    tags: list[str] | None = None,
) -> tuple[bool, str]:
    """Saves or updates an OKF Markdown memory file inside <workspace>/.agent/memory/."""
    if not title or not title.strip():
        return False, "Memory title cannot be empty."
    if not content or not content.strip():
        return False, "Memory content cannot be empty."

    clean_title = title.strip()
    safe_slug = RE_SAFE_NAME.sub("-", clean_title.lower()).strip("-") or "memory"
    mem_dir = _get_memory_dir(workspace_path)

    try:
        os.makedirs(mem_dir, exist_ok=True)
        filepath = os.path.join(mem_dir, f"{safe_slug}.md")

        tags_line = f"tags: {', '.join(tags)}\n" if tags else ""
        date_str = time.strftime("%Y-%m-%d")

        raw_text = (
            f"---\n"
            f"title: {clean_title}\n"
            f"type: {mem_type.lower().strip()}\n"
            f"date: {date_str}\n"
            f"{tags_line}"
            f"---\n\n"
            f"{content.strip()}\n"
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(raw_text)
        return True, filepath
    except OSError as e:
        return False, f"Failed to write memory file: {e}"


def clear_memories(workspace_path: str) -> None:
    """Removes all files in <workspace>/.agent/memory/."""
    mem_dir = _get_memory_dir(workspace_path)
    if os.path.isdir(mem_dir):
        shutil.rmtree(mem_dir, ignore_errors=True)


# Compatibility SDK aliases for in-kernel Python harness (/py)
def add_fact(workspace_path: str, key: str, value: str) -> bool:
    success, _ = save_memory_file(workspace_path, key, value, mem_type="rule")
    return success


def get_facts(workspace_path: str) -> str:
    return get_memory_context(workspace_path)
