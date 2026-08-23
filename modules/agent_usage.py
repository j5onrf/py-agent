#!/usr/bin/env python3
"""Token Usage & Spend Ledger Manager"""

import json
import os
import time
from typing import Any

LEDGER_PATH: str = os.path.expanduser("~/.config/py-agent/.spend_ledger.json")

# Model pricing per 1M tokens (input / output)
PRICING_MAP: dict[str, dict[str, float]] = {
    "gpt-5.5": {"in": 2.00, "out": 8.00},
    "gpt-5": {"in": 1.50, "out": 6.00},
    "gpt-4.5": {"in": 75.00, "out": 150.00},
    "claude-fable-5": {"in": 3.00, "out": 12.00},
    "claude-sonnet-5": {"in": 1.00, "out": 4.00},
    "claude-3-7-sonnet": {"in": 3.00, "out": 15.00},
    "claude-opus-4-8": {"in": 4.50, "out": 18.00},
    "gemini-3.7-flash": {"in": 0.75, "out": 3.75},
    "gemini-3.6-flash": {"in": 1.50, "out": 7.50},
    "gemini-3.5-flash": {"in": 0.075, "out": 0.30},
    "gemini-3.1-flash-lite": {"in": 0.075, "out": 0.30},
    "local-model": {"in": 0.0, "out": 0.0}
}

_today_cache: dict[str, Any] = {"date": "", "cost": 0.0}


def record(model: str, in_tok: int, out_tok: int, cost: float = 0.0) -> None:
    """Records token metrics and transaction costs to a daily spend database."""
    global _today_cache
    today = time.strftime("%Y-%m-%d")

    if cost == 0.0:
        model_low = model.lower()
        if pricing := next((v for k, v in PRICING_MAP.items() if k in model_low), None):
            cost = ((in_tok * pricing["in"]) + (out_tok * pricing["out"])) / 1_000_000.0

    data = {"date": today, "total_cost": 0.0, "models": {}}
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                if (temp := json.load(f)).get("date") == today:
                    data = temp
        except (OSError, json.JSONDecodeError):
            pass

    m_data = data["models"].setdefault(model, {"in": 0, "out": 0, "cost": 0.0})
    m_data["in"] += in_tok
    m_data["out"] += out_tok
    m_data["cost"] += cost
    data["total_cost"] += cost

    _today_cache = {"date": today, "cost": data["total_cost"]}

    try:
        os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
        tmp = f"{LEDGER_PATH}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, LEDGER_PATH)
    except OSError:
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except OSError: pass


def turn_line(in_tok: int, out_tok: int, cost: float, ctx_used: int, ctx_max: int | None = None) -> str:
    """Generates a structured terminal diagnostic summary line with cached ledger reads."""
    today = time.strftime("%Y-%m-%d")
    today_cost = _today_cache["cost"] if _today_cache.get("date") == today else 0.0

    if cost > 0.0 and today_cost == 0.0 and os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today:
                    today_cost = data.get("total_cost", 0.0)
                    _today_cache["date"] = today
                    _today_cache["cost"] = today_cost
        except (OSError, json.JSONDecodeError):
            pass

    ctx_pct = (ctx_used / (ctx_max or 8192)) * 100
    cost_part = f"cost: \033[32m${cost:.5f}\033[90m | " if cost > 0.0 else ""
    today_part = f"today: \033[32m${today_cost:.4f}\033[90m | " if (cost > 0.0 and today_cost > 0.0) else ""

    return f"\033[90m [ {in_tok} in | {out_tok} out | {cost_part}{today_part}ctx: {ctx_pct:.1f}% ]\033[0m"
