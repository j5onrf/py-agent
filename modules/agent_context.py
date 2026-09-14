#!/usr/bin/env python3
"""Context Search & Indexing Engine - Jaccard intent matching [Production Ready]"""

import os
import re
import sys
from typing import Any

_CACHED_FILE: str | None = None
_CACHED_ENTRIES: list[dict[str, Any]] | None = None
_LAST_M_TIME: float = 0.0

RE_WORD: re.Pattern = re.compile(r"\b\w+\b")

STOP_WORDS: frozenset[str] = frozenset({
    "is", "what", "it", "do", "any", "i", "have", "the", "a", "an", "on", "to", "for",
    "me", "you", "my", "your", "we", "us", "are", "about", "in", "how"
})


def tokenize(text: str, stop_words: frozenset[str] | set[str] = STOP_WORDS) -> list[str]:
    """Extracts lowercase tokens directly via C-speed regex without allocating intermediate strings."""
    if not text:
        return []
    return [w for w in RE_WORD.findall(text.lower()) if len(w) > 1 and w not in stop_words]


def load_context_entries(
    context_file: str, stop_words: frozenset[str] | set[str] = STOP_WORDS
) -> list[dict[str, Any]]:
    """Reads context blueprint and parses intent mappings with strict mtime and path caching."""
    global _CACHED_FILE, _CACHED_ENTRIES, _LAST_M_TIME
    if not os.path.exists(context_file):
        return []

    try:
        current_mtime = os.path.getmtime(context_file)
        if _CACHED_ENTRIES is not None and _CACHED_FILE == context_file and current_mtime <= _LAST_M_TIME:
            return _CACHED_ENTRIES

        parsed: list[dict[str, Any]] = []
        with open(context_file, "r", encoding="utf-8", errors="ignore") as f:
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
                    if tokens := tokenize(intent, stop_words):
                        parsed.append({
                            "cmd": cmd_clean,
                            "intent": intent,
                            "primary": primary_intent,
                            "tokens": tokens,
                            "tokens_set": frozenset(tokens),
                        })

        _CACHED_FILE, _CACHED_ENTRIES, _LAST_M_TIME = context_file, parsed, current_mtime
        return _CACHED_ENTRIES
    except (OSError, UnicodeDecodeError, ValueError) as e:
        sys.stderr.write(f"\033[1;31m[sys] Error parsing context metadata: {e}\033[0m\n")
        return []


def jaccard_search(
    query: str,
    context_file: str,
    stop_words: frozenset[str] | set[str] = STOP_WORDS,
    threshold: float = 0.45,
) -> str | None:
    """Computes Jaccard index intersections with zero set-union allocations and bidirectional substring bonuses."""
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
        has_sub = q_clean in ent_clean or ent_clean in q_clean
        if not inter_len and not has_sub:
            continue

        # Zero-allocation union computation: |A ∪ B| = |A| + |B| - |A ∩ B|
        union_len = len_q + len(ent_tokens) - inter_len
        score = (inter_len / union_len) if union_len else 0.0

        # Exact and bidirectional substring confidence bonuses
        if q_clean == ent_clean:
            score = 3.0
        elif ent_clean in q_clean:
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

    cleaned = cleaned.replace(" --s", "").strip()
    pager = ""
    for flag, pg in (
        (" --leaf", "leaf"),
        (" --glow", "glow"),
        (" --cat", "cat"),
        (" --view", "view"),
    ):
        if cleaned.endswith(flag):
            cleaned, pager = cleaned[:-len(flag)].strip(), pg
            break

    if not pager and is_tool:
        pager = "view"
    return f"{cleaned} | {pager}" if pager else cleaned
