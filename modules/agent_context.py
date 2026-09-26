#!/usr/bin/env python3
"""Context Search, Indexing & Compaction Engine [Production Ready]

Handles Jaccard semantic intent matching, accurate token counting heuristics,
context window monitoring, and the 3-Zone Context Compactor.
"""

import json
import os
import re
import sys
import threading
import urllib.request as urlreq
from typing import Any

from rich.box import ROUNDED
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

try:
    import agent_tools as tools
except ImportError:
    tools = None

_cache_lock = threading.Lock()
_CACHE_KEY: tuple[str, float, frozenset[str]] | None = None
_CACHED_ENTRIES: list[dict[str, Any]] | None = None

RE_WORD: re.Pattern = re.compile(r"\b\w+\b")
RE_SILENT_FLAG: re.Pattern = re.compile(r"(?<!\S)--s(?!\S)")

STOP_WORDS: frozenset[str] = frozenset({
    "is", "what", "it", "do", "any", "i", "have", "the", "a", "an", "on", "to", "for",
    "me", "you", "my", "your", "we", "us", "are", "about", "in", "how"
})


def _get_int_env(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None or not str(val).strip():
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ── 1. Jaccard Semantic Search & Blueprint Loader ─────────────────────────────

def tokenize(text: str, stop_words: frozenset[str] | set[str] = STOP_WORDS) -> list[str]:
    """Extracts lowercase tokens directly via C-speed regex without allocating intermediate strings."""
    if not text:
        return []
    return [w for w in RE_WORD.findall(text.lower()) if len(w) > 1 and w not in stop_words]


def load_context_entries(
    context_file: str, stop_words: frozenset[str] | set[str] = STOP_WORDS
) -> list[dict[str, Any]]:
    """Reads context blueprint and parses intent mappings with strict mtime and stopword caching."""
    global _CACHE_KEY, _CACHED_ENTRIES
    if not os.path.exists(context_file):
        return []

    try:
        current_mtime = os.path.getmtime(context_file)
        frozen_stop = frozenset(stop_words)
        cache_key = (context_file, current_mtime, frozen_stop)

        with _cache_lock:
            if _CACHED_ENTRIES is not None and _CACHE_KEY == cache_key:
                return list(_CACHED_ENTRIES)

        parsed: list[dict[str, Any]] = []
        with open(context_file, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "--->" not in s:
                    continue

                cmd, intents_str = s.split("--->", 1)
                cmd_clean = cmd.strip()
                intents = [i.strip() for i in intents_str.split(",") if i.strip()]
                if not intents:
                    continue

                primary_intent = intents[0]
                for intent in intents:
                    if tokens := tokenize(intent, frozen_stop):
                        parsed.append({
                            "cmd": cmd_clean,
                            "intent": intent,
                            "primary": primary_intent,
                            "tokens": tokens,
                            "tokens_set": frozenset(tokens),
                        })

        with _cache_lock:
            _CACHE_KEY = cache_key
            _CACHED_ENTRIES = parsed
            return list(_CACHED_ENTRIES)
    except OSError as e:
        sys.stderr.write(f"\033[1;31m[sys] Error reading context file: {e}\033[0m\n")
        return []


def jaccard_search(
    query: str,
    context_file: str,
    stop_words: frozenset[str] | set[str] = STOP_WORDS,
    threshold: float = 0.45,
) -> str | None:
    """Computes Jaccard index intersections with boundary-guarded substring bonuses."""
    q_clean = query.strip().lower()
    q_tokens = frozenset(tokenize(query, stop_words))
    if not q_tokens or not (entries := load_context_entries(context_file, stop_words)):
        return None

    len_q = len(q_tokens)
    candidates: list[tuple[float, str, str]] = []

    for entry in entries:
        ent_tokens = entry["tokens_set"]
        ent_clean = entry["intent"].strip().lower()

        inter_len = len(q_tokens & ent_tokens)
        is_exact = (q_clean == ent_clean)

        has_sub = False
        if not is_exact:
            if len(ent_clean) >= 3 and ent_clean in q_clean:
                has_sub = True
            elif len(q_clean) >= 3 and q_clean in ent_clean:
                has_sub = True
            elif len(ent_clean) < 3:
                if re.search(rf"\b{re.escape(ent_clean)}\b", q_clean):
                    has_sub = True

        if not inter_len and not has_sub and not is_exact:
            continue

        union_len = len_q + len(ent_tokens) - inter_len
        score = (inter_len / union_len) if union_len else 0.0

        if is_exact:
            score = 3.0
        elif has_sub:
            if ent_clean in q_clean:
                score = max(score, 0.85)
            elif q_clean in ent_clean:
                score = max(score, 0.80)

        if score >= threshold:
            candidates.append((score, entry["cmd"], entry.get("primary", entry["intent"])))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], len(x[2])))

    seen: set[str] = set()
    top_entries: list[str] = []
    for _, cmd, primary in candidates:
        if cmd not in seen and len(top_entries) < 5:
            seen.add(cmd)
            top_entries.append(f"{primary}|||{clean_tool_prefix(cmd)}")

    return "\n".join(top_entries)


def clean_tool_prefix(cmd: str) -> str:
    """Strips internal tool directives and normalizes terminal pagers."""
    is_tool = cmd.startswith("[TOOL]")
    cleaned = cmd.replace("[TOOL]", "", 1).strip() if is_tool else cmd
    if cleaned.startswith("DANGER_FLAGGED:"):
        cleaned = f"DANGER_FLAGGED:{cleaned.replace('DANGER_FLAGGED:', '').replace('[TOOL]', '').strip()}"

    cleaned = RE_SILENT_FLAG.sub("", cleaned).strip()

    pager = ""
    for flag, pg in (
        (" --cat", "cat"),
        (" --view", "view"),
    ):
        if cleaned.endswith(flag):
            cleaned, pager = cleaned[:-len(flag)].strip(), pg
            break

    if not pager and is_tool:
        pager = "view"
    return f"{cleaned} | {pager}" if pager else cleaned


# ── 2. Accurate Token Heuristics & Memory Context Status ─────────────────────

def get_accurate_token_count(text: Any, *args: Any, **kwargs: Any) -> int:
    """Fast, accurate token heuristic for llama.cpp/OAI models (len * 10 // 36)."""
    return max(1, (len(text if isinstance(text, str) else str(text)) * 10) // 36) if text else 0


estimate_token_count = get_accurate_token_count


def show_memory_status(
    messages: list[dict[str, Any]],
    max_context: int = 8192,
    server_url: str = "http://localhost:8080",
) -> None:
    """Queries upstream server context props and renders Rich context usage meter."""
    try:
        req = urlreq.Request(f"{server_url.rstrip('/')}/props")
        with urlreq.urlopen(req, timeout=0.25) as r:
            srv_settings = json.loads(r.read().decode("utf-8")).get("default_generation_settings", {})
            srv_ctx = srv_settings.get("n_ctx")
            if isinstance(srv_ctx, int) and srv_ctx > 0:
                max_context = srv_ctx
    except Exception:
        max_context = _get_int_env("AI_MAX_TOKENS", max_context)

    if not isinstance(max_context, int) or max_context <= 0:
        max_context = _get_int_env("AI_MAX_TOKENS", 8192)
    if max_context <= 0:
        max_context = 8192

    total_toks = sum(get_accurate_token_count(m.get("content") or "") for m in messages) + 760
    pct = (total_toks / max_context) * 100
    bar = "█" * int(min(20, pct / 5)) + "░" * (20 - int(min(20, pct / 5)))
    color = "green" if pct < 70 else "yellow" if pct < 90 else "red"

    console = Console()
    console.print(Panel(
        Group(
            Text.assemble(
                ("Context Window: ", "dim"),
                (f"{total_toks}", f"bold {color}"),
                (f"/{max_context} tokens ", "dim"),
                (f"({pct:.1f}%)", f"bold {color}"),
            ),
            Text(f"[{bar}]", style=color),
        ),
        title="Memory & Context Status",
        title_align="left",
        border_style="bright_black",
        box=ROUNDED,
        expand=False,
    ))


# ── 3. 3-Zone Context Compactor with SmolCoder Active Session Anchors ─────────

def prune_history(history: list[dict[str, Any]], max_tokens: int | None = None) -> list[dict[str, Any]]:
    """3-Zone Context Compactor: Preserves system prompt, active session anchors, and recent tail.

    Safely walks backward to ensure tool responses are never orphaned from their
    initiating assistant tool_calls message.
    """
    if len(history) <= 4:
        return history

    limit = max_tokens or _get_int_env("AI_MAX_TOKENS", 8192)
    sys_msg = history[0]

    # Select recent tail (at least 4 messages), walking backward to ensure we never start
    # on an orphaned tool message whose assistant tool_calls message was moved to middle
    tail_idx = max(1, len(history) - 4)
    while tail_idx > 1 and history[tail_idx].get("role") == "tool":
        tail_idx -= 1

    recent_tail = history[tail_idx:]
    middle_msgs = history[1:tail_idx]

    completed_actions = []
    compacted_middle = []

    for msg in middle_msgs:
        role = msg.get("role")
        content = str(msg.get("content") or "")

        if role == "tool":
            fname = msg.get("name", "tool")
            line_count = len(content.splitlines())

            if "Successfully edited" in content:
                if m := re.search(r"Successfully edited\s+(\S+)", content):
                    completed_actions.append(f"Edited {m.group(1)}")
                summary = f"[{fname}: applied targeted edit]"
            elif "wrote" in content and "chars to" in content:
                if m := re.search(r"wrote \d+ chars to\s+(\S+)", content):
                    completed_actions.append(f"Created {m.group(1)}")
                summary = f"[{fname}: created file]"
            elif "(exit 0" in content:
                completed_actions.append("Passed shell verification")
                summary = f"[{fname}: command passed (exit 0)]"
            elif "### File:" in content or line_count > 10:
                summary = f"[{fname}: {line_count} lines processed successfully]"
            elif "(exit" in content:
                first_err = content.splitlines()[0] if content else "error"
                summary = f"[{fname}: {first_err[:120]}]"
            else:
                summary = content if len(content) <= 150 else content[:120] + "... [snipped]"

            compacted_middle.append({"role": "assistant", "content": summary})
        elif role == "assistant":
            clean_msg = {k: v for k, v in msg.items() if k != "tool_calls"}
            clean_c = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", str(clean_msg.get("content") or "")).strip()
            if clean_c:
                compacted_middle.append({**clean_msg, "content": clean_c})
        else:
            compacted_middle.append(msg)

    anchors = []
    if tools and hasattr(tools, "get_modified_files"):
        try:
            if mod_files := tools.get_modified_files():
                anchors.append(f"[Active Session Modified Files: {', '.join(mod_files)}]")
        except Exception:
            pass
    if completed_actions:
        deduped = list(dict.fromkeys(completed_actions))[-6:]
        anchors.append("[Completed Milestones]:\n" + "\n".join(f"✓ {act}" for act in deduped))

    anchor_msg = {"role": "system", "content": "\n\n".join(anchors)} if anchors else None

    assembled = [sys_msg] + ([anchor_msg] if anchor_msg else [])
    sys_anchor_tokens = sum(get_accurate_token_count(m.get("content", "")) for m in assembled)
    tail_tokens = sum(get_accurate_token_count(m.get("content") or "") for m in recent_tail)

    budget_for_middle = max(500, limit - tail_tokens - sys_anchor_tokens)
    selected_middle = []
    middle_used = 0

    for m in reversed(compacted_middle):
        toks = get_accurate_token_count(m.get("content") or "")
        if middle_used + toks > budget_for_middle and selected_middle:
            break
        selected_middle.append(m)
        middle_used += toks

    return assembled + list(reversed(selected_middle)) + recent_tail
