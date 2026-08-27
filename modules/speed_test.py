#!/usr/bin/env python3
"""Precise token generation & TPS speed test statistics tracker"""

import sys
import time

_state = {
    "start": None,
    "t_start": None,
    "t_end": None,
    "t_chars": 0,
    "a_chars": 0,
    "in_think": False,
}


def start() -> None:
    """Begins the timer and resets state."""
    global _state
    _state = {
        "start": time.time(),
        "t_start": None,
        "t_end": None,
        "t_chars": 0,
        "a_chars": 0,
        "in_think": False,
    }


def count_token(content: str, is_thinking: bool = False) -> None:
    """Accumulates content character counts for precise token estimation across generation phases."""
    if not content or _state["start"] is None:
        return
    now = time.time()
    if is_thinking:
        if not _state["in_think"]:
            _state["in_think"], _state["t_start"] = True, _state["t_start"] or now
        _state["t_chars"] += len(content)
    else:
        if _state["in_think"]:
            _state["in_think"], _state["t_end"] = False, now
        _state["a_chars"] += len(content)


def end(
    actual_out_tokens: int | None = None,
    is_local: bool = False,
    resolved_model: str | None = None,
    active_model: str | None = None,
) -> None:
    """Calculates and prints token statistics, then cleanly resets state."""
    if _state["start"] is None:
        return
    elapsed = max(0.001, time.time() - _state["start"])
    if _state["in_think"] and not _state["t_end"]:
        _state["t_end"] = time.time()

    tot_chars = _state["t_chars"] + _state["a_chars"]
    tot_toks = (
        actual_out_tokens
        if (actual_out_tokens and actual_out_tokens > 0)
        else max(1, round(tot_chars / 4.0))
        if tot_chars > 0
        else 0
    )
    think_toks = (
        round((_state["t_chars"] / tot_chars) * tot_toks)
        if tot_chars > 0 and _state["t_chars"] > 0
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

    _state["start"] = None
