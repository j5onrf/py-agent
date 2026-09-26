#!/usr/bin/env python3
"""Context Search & Indexing Engine - Jaccard intent matching [Production Ready]"""

import os
import re
import sys
import threading
from typing import Any

_cache_lock = threading.Lock()
_CACHE_KEY: tuple[str, float, frozenset[str]] | None = None
_CACHED_ENTRIES: list[dict[str, Any]] | None = None

RE_WORD: re.Pattern = re.compile(r"\b\w+\b")
RE_SILENT_FLAG: re.Pattern = re.compile(r"(?<!\S)--s(?!\S)")

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

        # Apply substring matching only on tokens >= 3 chars or on exact word boundaries
        has_sub = False
        if not is_exact:
            if len(ent_clean) >= 3 and ent_clean in q_clean:
                has_sub = True
            elif len(q_clean) >= 3 and q_clean in ent_clean:
                has_sub = True
            elif len(ent_clean) < 3:
                # Short 2-char aliases (e.g. 'cs', 'ta', 'gc') must match exact word boundaries
                if re.search(rf"\b{re.escape(ent_clean)}\b", q_clean):
                    has_sub = True

        if not inter_len and not has_sub and not is_exact:
            continue

        # Zero-allocation union computation: |A ∪ B| = |A| + |B| - |A ∩ B|
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

    # Strip standalone --s flag without mangling words like --sort or --strip
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
