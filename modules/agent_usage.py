#!/usr/bin/env python3
"""Unified Token Usage, Spend Ledger & Speed Tracker [Production Ready]"""

import json
import os
import sys
import time
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
LEDGER_FILE = os.path.join(CFG_DIR, ".spend_ledger.json")
LEDGER_PATH = LEDGER_FILE

# Approximate pricing per 1M tokens (Input / Output USD)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenRouter / Anthropic
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o3-mini": (1.10, 4.40),
    # DeepSeek
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    # Google (Paid tiers)
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 5.00),
}

# --- Generation Speed Tracker State ---
_speed_state = {
    "start": None,
    "t_start": None,
    "t_end": None,
    "t_chars": 0,
    "a_chars": 0,
    "in_think": False,
}


def start() -> None:
    """Begins the high-resolution monotonic timer and resets speed state."""
    global _speed_state
    _speed_state = {
        "start": time.perf_counter(),
        "t_start": None,
        "t_end": None,
        "t_chars": 0,
        "a_chars": 0,
        "in_think": False,
    }


def count_token(content: str, is_thinking: bool = False) -> None:
    """Accumulates content characters across thinking and answer phases."""
    if not content or _speed_state["start"] is None:
        return
    now = time.perf_counter()
    if is_thinking:
        if not _speed_state["in_think"]:
            _speed_state["in_think"] = True
            if _speed_state["t_start"] is None:
                _speed_state["t_start"] = now
        _speed_state["t_chars"] += len(content)
    else:
        if _speed_state["in_think"]:
            _speed_state["in_think"] = False
            _state_end = now
        _speed_state["a_chars"] += len(content)


def end(
    actual_out_tokens: int | None = None,
    is_local: bool = False,
    resolved_model: str | None = None,
    active_model: str | None = None,
) -> None:
    """Calculates and prints generation speed in uniform muted gray style."""
    if _speed_state["start"] is None:
        return

    now = time.perf_counter()
    elapsed = max(0.0001, now - _speed_state["start"])

    if _speed_state["in_think"] and not _speed_state["t_end"]:
        _speed_state["t_end"] = now

    tot_chars = _speed_state["t_chars"] + _speed_state["a_chars"]
    tot_toks = (
        actual_out_tokens
        if (actual_out_tokens and actual_out_tokens > 0)
        else max(1, round(tot_chars / 4.0))
        if tot_chars > 0
        else 0
    )

    think_toks = (
        round((_speed_state["t_chars"] / tot_chars) * tot_toks)
        if tot_chars > 0 and _speed_state["t_chars"] > 0
        else 0
    )
    ans_toks = max(0, tot_toks - think_toks)
    tps = tot_toks / elapsed

    model_line = ""
    if (
        active_model == "openrouter/free"
        and resolved_model
        and resolved_model != "openrouter/free"
    ):
        model_line = f"\033[90m [ model: {resolved_model} ]\033[0m\n"

    if is_local and think_toks > 0:
        msg = f"{model_line}\033[90m [ think: {think_toks} | ans: {ans_toks} | {tot_toks} tokens | {elapsed:.1f}s @ {tps:.1f} t/s ]\033[0m\n"
    else:
        msg = f"{model_line}\033[90m [ {tot_toks} tokens | {elapsed:.2f}s | {tps:.2f} t/s ]\033[0m\n"

    sys.stdout.write(msg)
    sys.stdout.flush()
    _speed_state["start"] = None


# --- Spend Ledger & Token Tracking ---

def calculate_cost(model_name: str, in_tok: int, out_tok: int) -> float:
    """Calculates approximate dollar cost based on model prefix."""
    if not model_name or any(loc in model_name.lower() for loc in ("local", "gguf", "qwen3.", "ling", "lfm", "minicpm", "free")):
        return 0.0

    clean_name = model_name.lower()
    for key, (in_price, out_price) in MODEL_PRICING.items():
        if key in clean_name:
            return (in_tok * (in_price / 1_000_000.0)) + (out_tok * (out_price / 1_000_000.0))
    return 0.0


def record(model: str, in_tok: int, out_tok: int, cost: float = 0.0) -> None:
    """Records spend to ledger only if a non-zero cost occurred."""
    if cost <= 0.0:
        cost = calculate_cost(model, in_tok, out_tok)
    if cost <= 0.00001:
        return

    today = time.strftime("%Y-%m-%d")
    data: dict[str, Any] = {"total_spend": 0.0, "daily": {}, "models": {}}

    try:
        if os.path.exists(LEDGER_FILE):
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

        data["total_spend"] = round(data.get("total_spend", 0.0) + cost, 6)
        daily = data.setdefault("daily", {})
        daily[today] = round(daily.get(today, 0.0) + cost, 6)

        models = data.setdefault("models", {})
        m_entry = models.setdefault(model, {"in_tokens": 0, "out_tokens": 0, "cost": 0.0})
        m_entry["in_tokens"] += in_tok
        m_entry["out_tokens"] += out_tok
        m_entry["cost"] = round(m_entry.get("cost", 0.0) + cost, 6)

        tmp = f"{LEDGER_FILE}.tmp"
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, LEDGER_FILE)
    except OSError:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def turn_line(
    in_tok: int,
    out_tok: int,
    cost: float = 0.0,
    ctx_used: int | None = None,
    ctx_max: int | None = None,
    cached_tok: int = 0,
) -> str:
    """Renders context and spend in the exact same style and bracket alignment as speed stats."""
    parts = [f"{in_tok:,} in", f"{out_tok:,} out"]

    if cached_tok > 0 and in_tok > 0:
        cache_pct = int((cached_tok / in_tok) * 100)
        parts.append(f"cch: {cache_pct}%")

    if ctx_used is not None and ctx_max and ctx_max > 0:
        pct = (ctx_used / ctx_max) * 100.0
        parts.append(f"ctx: {pct:.1f}%")

    if cost > 0.0001:
        parts.append(f"${cost:.4f}")

    body = " | ".join(parts)
    return f"\033[90m [ {body} ]\033[0m"
