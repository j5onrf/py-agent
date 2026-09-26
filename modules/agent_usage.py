#!/usr/bin/env python3
"""Unified Token Usage, Spend Ledger & Speed Tracker [Production Ready]"""

import json
import os
import sys
import threading
import time
from typing import Any

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

CFG_DIR = os.path.expanduser("~/.config/py-agent")
LEDGER_FILE = os.path.join(CFG_DIR, ".spend_ledger.json")
LEDGER_PATH = LEDGER_FILE
PRICING_FILE = os.path.join(CFG_DIR, "model_pricing.json")

# Fallback baseline pricing per 1M tokens (Input / Output USD)
# Overridden dynamically by ~/.config/py-agent/model_pricing.json on demand
DEFAULT_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "o3-mini": (1.10, 4.40),
    "o1-mini": (1.10, 4.40),
    "o1": (15.00, 60.00),
    # DeepSeek
    "deepseek-reasoner": (0.55, 2.19),
    "deepseek-chat": (0.14, 0.28),
    # Google (Paid tiers)
    "gemini-2.5-flash": (0.10, 0.40),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 5.00),
    # Open source / Meta
    "llama-3.3-70b": (0.35, 0.40),
    "qwen-2.5-72b": (0.35, 0.40),
}

MODEL_PRICING = DEFAULT_MODEL_PRICING

_speed_lock = threading.Lock()
_speed_state = {
    "start": None,
    "t_start": None,
    "t_end": None,
    "t_chars": 0,
    "a_chars": 0,
    "in_think": False,
}

_cached_pricing: dict[str, tuple[float, float]] | None = None
_pricing_mtime: float = 0.0


def ensure_pricing_file_exists() -> None:
    """Lazy initialization: creates model_pricing.json with instructions only when requested."""
    if not os.path.exists(PRICING_FILE):
        os.makedirs(os.path.dirname(PRICING_FILE) or CFG_DIR, exist_ok=True)
        template = (
            "# ==============================================================================\n"
            "# Py-Agent Model Pricing Configuration (USD per 1,000,000 tokens)\n"
            "#\n"
            "# FORMAT: \"model-key\": [input_price_usd, output_price_usd]\n"
            "# Matches by longest prefix/substring (e.g., 'gpt-4o-mini' beats 'gpt-4o').\n"
            "# Lines starting with '#' or '//' are ignored.\n"
            "# Free models ($0.00) or local models do not need to be listed.\n"
            "# ==============================================================================\n"
            "{\n"
            '  "claude-3-7-sonnet": [3.00, 15.00],\n'
            '  "claude-3-5-sonnet": [3.00, 15.00],\n'
            '  "claude-3-5-haiku": [0.80, 4.00],\n'
            '  "gpt-4o-mini": [0.15, 0.60],\n'
            '  "gpt-4o": [2.50, 10.00],\n'
            '  "o3-mini": [1.10, 4.40],\n'
            '  "o1-mini": [1.10, 4.40],\n'
            '  "o1": [15.00, 60.00],\n'
            '  "deepseek-reasoner": [0.55, 2.19],\n'
            '  "deepseek-chat": [0.14, 0.28],\n'
            '  "gemini-2.5-flash": [0.10, 0.40],\n'
            '  "gemini-2.0-flash": [0.10, 0.40],\n'
            '  "gemini-2.5-pro": [1.25, 5.00],\n'
            '  "llama-3.3-70b": [0.35, 0.40],\n'
            '  "qwen-2.5-72b": [0.35, 0.40]\n'
            "}\n"
        )
        tmp = f"{PRICING_FILE}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(template)
            os.chmod(tmp, 0o600)
            os.replace(tmp, PRICING_FILE)
        except OSError:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


def get_pricing_map() -> dict[str, tuple[float, float]]:
    """Strictly lazy-loads model_pricing.json on demand with in-memory caching."""
    global _cached_pricing, _pricing_mtime
    if not os.path.isfile(PRICING_FILE):
        ensure_pricing_file_exists()

    if os.path.isfile(PRICING_FILE):
        try:
            mtime = os.path.getmtime(PRICING_FILE)
            if _cached_pricing is None or mtime != _pricing_mtime:
                with open(PRICING_FILE, "r", encoding="utf-8") as f:
                    lines = [l for l in f if not l.strip().startswith(("#", "//"))]
                raw = json.loads("".join(lines))
                parsed = {}
                for k, v in raw.items():
                    if k.startswith("_"):
                        continue
                    if isinstance(v, (list, tuple)) and len(v) >= 2:
                        parsed[k.lower()] = (float(v[0]), float(v[1]))
                _cached_pricing = {**DEFAULT_MODEL_PRICING, **parsed}
                _pricing_mtime = mtime
                return _cached_pricing
            return _cached_pricing
        except Exception:
            pass
    return DEFAULT_MODEL_PRICING


# --- Generation Speed Tracker State ---

def start() -> None:
    """Begins the high-resolution monotonic timer and resets speed state."""
    global _speed_state
    with _speed_lock:
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
    if not content:
        return
    with _speed_lock:
        if _speed_state["start"] is None:
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
                _speed_state["t_end"] = now
            _speed_state["a_chars"] += len(content)


def end(
    actual_out_tokens: int | None = None,
    is_local: bool = False,
    resolved_model: str | None = None,
    active_model: str | None = None,
) -> None:
    """Calculates and prints generation speed in uniform muted gray style."""
    with _speed_lock:
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
        _speed_state["start"] = None

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


# --- Spend Ledger & Token Tracking ---

def calculate_cost(model_name: str, in_tok: int, out_tok: int) -> float:
    """Calculates dollar cost. Immediately returns 0.0 for free/local models with zero I/O."""
    if not model_name or any(loc in model_name.lower() for loc in ("local", "gguf", "qwen3.", "ling", "lfm", "minicpm", "free")):
        return 0.0

    clean_name = model_name.lower()
    pricing_map = get_pricing_map()

    # Longest matching key takes precedence (e.g. 'gpt-4o-mini' matches before 'gpt-4o')
    best_key = max((k for k in pricing_map if k in clean_name), key=len, default=None)
    if best_key:
        in_price, out_price = pricing_map[best_key]
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
    target_ledger = getattr(sys.modules[__name__], "LEDGER_FILE", LEDGER_FILE)
    tmp_path = f"{target_ledger}.tmp"
    lock_path = f"{target_ledger}.lock"

    # Acquire flock to prevent race conditions during concurrent worker writes
    lock_fd = None
    if _HAS_FCNTL:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        except OSError:
            lock_fd = None

    try:
        if os.path.exists(target_ledger):
            try:
                with open(target_ledger, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = {"total_spend": 0.0, "daily": {}, "models": {}}

        data["total_spend"] = round(data.get("total_spend", 0.0) + cost, 6)
        daily = data.setdefault("daily", {})
        daily[today] = round(daily.get(today, 0.0) + cost, 6)

        models = data.setdefault("models", {})
        m_entry = models.setdefault(model, {"in_tokens": 0, "out_tokens": 0, "cost": 0.0})
        m_entry["in_tokens"] += in_tok
        m_entry["out_tokens"] += out_tok
        m_entry["cost"] = round(m_entry.get("cost", 0.0) + cost, 6)

        os.makedirs(os.path.dirname(target_ledger) or CFG_DIR, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, target_ledger)
    except OSError:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
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
    """Renders context and spend in uniform muted gray style."""
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
