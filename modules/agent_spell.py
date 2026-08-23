#!/usr/bin/env python3
"""Offline/Online Spellchecker Module - LanguageTool API & phonetic edit-distance."""

import difflib
import json
import os
import re
import shutil
import sys
import urllib.parse as urlparse
import urllib.request as urlreq
from collections.abc import Callable

TYPO_OVERRIDES: dict[str, str] = {
    "hellow": "hello", "helow": "hello", "helo": "hello",
    "howre": "how are", "wru": "where are you", "hru": "how are you",
    "youa": "you", "trainted": "trained"
}
PROTECTED_WORDS: set[str] = frozenset({"hello", "hi", "hey", "how", "here", "you", "who", "there"})
DEV_TERMS: set[str] = frozenset({
    "auth", "git", "bash", "zsh", "cli", "tui", "yaml", "json", "ast", "llm",
    "api", "url", "cmd", "args", "uuid", "md", "txt", "db", "sqlite", "epoxy", "wttr"
})

RE_WORD_BOUNDARIES: re.Pattern = re.compile(r'(\b[a-zA-Z]+\b)')
RE_WHITESPACE: re.Pattern = re.compile(r'(\s+)')


def load_system_dictionary() -> set[str]:
    """Loads system word dictionary with development and TUI command word exceptions."""
    embedded: set[str] = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with", "he", "as", "you",
        "do", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her", "she", "or", "an", "will", "my", "one",
        "all", "would", "there", "their", "what", "so", "up", "out", "if", "about", "who", "get", "which", "go", "me", "when",
        "make", "can", "like", "time", "no", "just", "him", "know", "take", "people", "into", "year", "your", "good", "some",
        "could", "them", "see", "other", "than", "then", "now", "look", "only", "come", "its", "over", "think", "also", "back",
        "after", "use", "two", "how", "our", "work", "first", "well", "way", "even", "new", "want", "because", "any", "these",
        "give", "day", "most", "us", "lazy", "quick", "brown", "fox", "jumps", "dog", "cat", "mat", "sit", "sits", "book",
        "read", "reads", "spelling", "grammar", "here", "where", "why", "whose",
        "am", "is", "are", "was", "were", "been", "being", "has", "had", "having", "does", "did", "doing",
        "write", "writes", "written", "writing", "code", "coder", "coding", "program", "programming", "python", "script",
        "sentence", "errors", "error", "correct", "correction", "spelled", "hello", "hi", "hey", *DEV_TERMS
    }
    for path in ("/usr/share/dict/words", "/etc/dictionaries-common/words", "/usr/dict/words"):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return {w.strip().lower() for w in f if w.strip().isalpha()} | embedded
            except (OSError, UnicodeDecodeError): pass
    return embedded


DICT_WORDS: set[str] = load_system_dictionary()


def edits1(word: str) -> set[str]:
    """Generates all edit-distance-1 permutations for a given word."""
    L = 'abcdefghijklmnopqrstuvwxyz'
    s = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    return set(
        [l + r[1:] for l, r in s if r] +
        [l + r[1] + r[0] + r[2:] for l, r in s if len(r) > 1] +
        [l + c + r[1:] for l, r in s if r for c in L] +
        [l + c + r for l, r in s for c in L]
    )


def correct_word(word: str) -> str:
    """Phonetically verifies and corrects individual word selections."""
    if not DICT_WORDS or not word.isalpha() or len(word) < 3 or (w_lower := word.lower()) in DICT_WORDS:
        return word
    if candidates := edits1(w_lower) & DICT_WORDS:
        best = min(candidates, key=lambda c: (1 if sorted(c) == sorted(w_lower) else 2 if len(c) - len(w_lower) == 1 else 3 if len(c) == len(w_lower) else 4, c))
        return best.upper() if word.isupper() else (best.capitalize() if word[0].isupper() else best)
    return word


def _match_case(original: str, replacement: str) -> str:
    return replacement.upper() if original.isupper() else (replacement.capitalize() if original[0].isupper() else replacement)


def _transform_words(query: str, mapper: Callable[[str], str | None]) -> tuple[str, bool]:
    chunks, changed = RE_WORD_BOUNDARIES.split(query), False
    res = []
    for chunk in chunks:
        if chunk.isalpha() and (rep := mapper(chunk)):
            res.append(rep)
            changed = changed or (rep != chunk)
        else:
            res.append(chunk)
    return "".join(res), changed


def apply_static_overrides(query: str) -> tuple[str, bool]:
    """Applies hardcoded static typo corrections on query patterns."""
    return _transform_words(query, lambda w: _match_case(w, TYPO_OVERRIDES[w.lower()]) if w.lower() in TYPO_OVERRIDES else None)


def check_query_spelling_offline(query: str) -> tuple[str, bool]:
    """Runs high-speed local dictionary edit-distance corrections."""
    return _transform_words(query, lambda w: (c if (c := correct_word(w)) != w else None))


def highlight_diff(original: str, corrected: str) -> str:
    """Highlights differences between the original input and the auto-corrected query."""
    orig_words, corr_words = RE_WHITESPACE.split(original), RE_WHITESPACE.split(corrected)
    res = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, orig_words, corr_words).get_opcodes():
        chunk = "".join(corr_words[j1:j2])
        if op in ('replace', 'insert') and chunk.strip():
            res.append(f"\033[23;1;32m{chunk}\033[0m\033[3m")
        else:
            res.append(chunk)
    return "".join(res)


def _get_prio(w: str, orig: str) -> int:
    w_low, orig_low = w.lower(), orig.lower()
    return 1 if sorted(w_low) == sorted(orig_low) else 2 if len(w_low) - len(orig_low) == 1 else 3 if len(w_low) == len(orig_low) else 4


def check_query_spelling(query: str, get_key_fn: Callable[[], str]) -> tuple[str, str]:
    """Runs spellcheck verification pipelines with fast local timeout handling."""
    orig_input = query
    query, changed_static = apply_static_overrides(query)
    corrected_query, changed, used_grammar = query, changed_static, False
    resp_data = None

    endpoints = [
        ("http://localhost:8010/v2/check", 0.25),
        ("http://localhost:8081/v2/check", 0.25),
        ("https://api.languagetool.org/v2/check", 1.2)
    ]

    for url, timeout_val in endpoints:
        try:
            req = urlreq.Request(url, data=urlparse.urlencode({'text': query, 'language': 'en-US'}).encode('utf-8'), method='POST')
            with urlreq.urlopen(req, timeout=timeout_val) as r:
                resp_data = json.loads(r.read().decode('utf-8'))
                used_grammar = True
                break
        except (OSError, urlreq.URLError, TimeoutError, json.JSONDecodeError):
            pass

    if resp_data and "matches" in resp_data and (matches := resp_data["matches"]):
        matches.sort(key=lambda m: m.get("offset", 0), reverse=True)
        chars = list(query)
        for match in matches:
            offset, length = match.get("offset"), match.get("length")
            if match.get("replacements") and offset is not None and length is not None:
                if best := match["replacements"][0].get("value"):
                    orig_word = query[offset:offset + length]
                    if orig_word.lower() in PROTECTED_WORDS: continue
                    if orig_word.isalpha():
                        local_cand = correct_word(orig_word)
                        if local_cand != orig_word and local_cand.lower() != best.lower():
                            if _get_prio(local_cand, orig_word) < _get_prio(best, orig_word) or (best[0].lower() != orig_word[0].lower() and local_cand[0].lower() == orig_word[0].lower()):
                                best = local_cand
                    chars[offset:offset + length] = list(best)
                    changed = True
        corrected_query = "".join(chars)

    if not used_grammar and not changed_static:
        corrected_query, changed = check_query_spelling_offline(query)

    if changed and corrected_query.strip().lower() != orig_input.strip().lower():
        sys.stderr.write(f"\n\033[2m[sys] Typos detected. Correct query to:\033[0m\n\033[3m   \"{highlight_diff(orig_input, corrected_query)}\"\033[0m\n\033[2m   [↵ accept  Tab: edit  d: disable  Esc: skip]: \033[0m")
        sys.stderr.flush()

        key = get_key_fn()
        cols = shutil.get_terminal_size().columns or 80
        total_lines = 1 + sum((l + cols - 1) // cols for l in (len("[sys] Typos detected. Correct query to:"), 4 + len(corrected_query), len("   [↵ accept  Tab: edit  d: disable  Esc: skip]: ")))
        clear_prompt = "\r\x1b[K" + "\x1b[1A\r\x1b[K" * (total_lines - 1)

        if key in ('\r', '\n', ''):
            rollback = (total_lines - 1) + ((2 + len(orig_input) + cols - 1) // cols)
            sys.stderr.write(f"\r\x1b[{rollback}A\r\x1b[J\033[1;30m❯\033[0m {corrected_query}\n")
            sys.stderr.flush()
            return "RUN", corrected_query

        if key in ('\t', 'e', 'E'):
            sys.stderr.write(clear_prompt + "\033[2;33m[sys] Returning to editor...\033[0m\n")
            sys.stderr.flush()
            return "EDIT", orig_input

        if key in ('d', 'D'):
            sys.stderr.write(clear_prompt + "\033[2;31m[sys] Spellchecker disabled. (Type /spell to re-enable)\033[0m\n")
            sys.stderr.flush()
            return "DISABLE", orig_input

        sys.stderr.write(clear_prompt)
        sys.stderr.flush()

    return "RUN", orig_input
