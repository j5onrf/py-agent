#!/usr/bin/env python3
"""State Persistence & Boundary Locking Engine [Hardened Production Ready]

Provides thread-safe and process-isolated state caching with flock file locking,
atomic tempfile swapping, and environment configuration helpers.
"""

import fcntl
import json
import os
import sys
import threading
from typing import Any

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
STATE_FILE: str = os.path.join(CFG_DIR, ".state.json")
STATE_LOCK_FILE: str = os.path.join(CFG_DIR, ".state.lock")

DEFAULTS: dict[str, Any] = {
    "show_stats": False,
    "memory_active": False,
    "box_style": 7,
    "yolo_mode": True,
    "show_thinking": True,
    "reasoning_active": True,
    "reasoning_budget": 500,
    "voice_auto_submit": True,
    "tts_enabled": False,
    "render_markdown": False,
    "adapters_active": False,
    "calm_mode": False,
    "code_theme": "monokai",
}

_state_lock = threading.Lock()
_state_cache: dict[str, Any] = {}
_state_mtime: float = 0.0
_state_size: int = 0
_state_ino: int = 0


def _get_int_env(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None or not str(val).strip():
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_state(key: str = "", default: Any = None) -> Any:
    global _state_cache, _state_mtime, _state_size, _state_ino
    with _state_lock:
        if os.path.exists(STATE_FILE):
            try:
                st = os.stat(STATE_FILE)
                sig = (st.st_mtime, st.st_size, getattr(st, "st_ino", 0))
                if sig != (_state_mtime, _state_size, _state_ino) or not _state_cache:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        _state_cache = loaded
                    _state_mtime, _state_size, _state_ino = sig
            except (OSError, json.JSONDecodeError):
                pass
        elif _state_cache:
            _state_cache, _state_mtime, _state_size, _state_ino = {}, 0.0, 0, 0
        merged = {**DEFAULTS, **_state_cache}
        return merged.get(key, default) if key else merged


def save_state(key: str, value: Any) -> None:
    global _state_cache, _state_mtime, _state_size, _state_ino
    with _state_lock:
        os.makedirs(CFG_DIR, exist_ok=True)
        lock_fd = None
        tmp = f"{STATE_FILE}.tmp.{os.getpid()}.{threading.get_ident()}"
        try:
            lock_fd = os.open(STATE_LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            current = {}
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        current = json.load(f)
                except (OSError, json.JSONDecodeError):
                    current = {}
            st = {**current, key: value}
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2)
            os.replace(tmp, STATE_FILE)
            _state_cache = st
            try:
                st_stat = os.stat(STATE_FILE)
                _state_mtime, _state_size, _state_ino = st_stat.st_mtime, st_stat.st_size, getattr(st_stat, "st_ino", 0)
            except OSError:
                pass
        except (OSError, TypeError, ValueError) as e:
            sys.stderr.write(f"[sys] Failed to persist state '{key}': {e}\n")
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                except OSError:
                    pass


def workspace_safe_name(workspace_path: str, home_dir: str = "") -> str:
    home, ws = os.path.realpath(home_dir or os.path.expanduser("~")), os.path.realpath(workspace_path)
    return "home-chat" if ws == home else (ws.replace("/", "-").strip("-.") or "home-chat")


def is_calm_cli() -> bool:
    """Strict gate: Calm mode only runs in interactive CLI terminals."""
    if os.environ.get("AI_SURFACE") == "1" or os.environ.get("TEXTUAL") or _get_int_env("AI_SUBAGENT_DEPTH", 0) >= 1:
        return False
    if not (sys.stdout.isatty() and sys.stderr.isatty()):
        return False
    return bool(get_state("calm_mode", False))
