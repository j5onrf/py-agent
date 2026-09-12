#!/usr/bin/env python3
"""Token Usage & Spend Ledger Manager [Zero-Overhead Edition]"""

import json
import os
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
    """Records spend to ledger only if an actual non-zero cost occurred."""
    # FAST-PATH: Zero file I/O for local models or free tiers
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
) -> str:
    """Renders a clean, lightweight context and spend indicator."""
    parts = [f"\033[2m[ {in_tok:,} in | {out_tok:,} out"]

    if ctx_used is not None and ctx_max and ctx_max > 0:
        pct = (ctx_used / ctx_max) * 100.0
        parts.append(f"| ctx: {pct:.1f}%")

    if cost > 0.0001:
        parts.append(f"| \033[33m${cost:.4f}\033[2m")

    parts.append("]\033[0m")
    return " ".join(parts)
