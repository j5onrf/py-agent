#!/usr/bin/env python3
"""Local-AI Kokoro Text-to-Speech (Text Out Loud) Module [Zero-Lag Edition]"""

import os
import re
import subprocess
import threading

CFG_DIR = os.path.expanduser("~/.config/py-agent")

try:
    import agent_core as core
except ImportError:
    core = None

RE_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
RE_UNCLOSED_THINK = re.compile(r"<think>.*$", re.DOTALL)
RE_CODE_BLOCKS = re.compile(r"```[\s\S]*?```", re.DOTALL)
RE_INLINE_CODE = re.compile(r"`[^`]*`")
RE_MARKDOWN_CHARS = re.compile(r"[*_~#>-]")
RE_LINKS = re.compile(r"\[([^\]]+)\]\([^)]+\)")

_current_tts_proc = None
_tts_lock = threading.Lock()


def stop_tts() -> None:
    global _current_tts_proc
    with _tts_lock:
        if _current_tts_proc:
            try:
                _current_tts_proc.terminate()
            except OSError:
                pass
            _current_tts_proc = None
    subprocess.run(["pkill", "-9", "-f", "pw-play|koko"], stderr=subprocess.DEVNULL)


def is_tts_enabled() -> bool:
    return core.get_state().get("tts_enabled", False) if core else False


def toggle_tts(enable: bool | None = None) -> bool:
    new_st = (not is_tts_enabled()) if enable is None else enable
    if core:
        core.save_state("tts_enabled", new_st)
    if not new_st:
        stop_tts()
    return new_st


def clean_text_for_speech(text: str) -> str:
    if not text:
        return ""
    # 1. Strip closed and unclosed thinking blocks
    cleaned = RE_THINK_BLOCK.sub("", text)
    cleaned = RE_UNCLOSED_THINK.sub("", cleaned)
    # 2. Strip code blocks and inline code
    cleaned = RE_CODE_BLOCKS.sub("", cleaned)
    cleaned = RE_INLINE_CODE.sub("", cleaned)
    # 3. Strip links and markdown styling
    cleaned = RE_LINKS.sub(r"\1", cleaned)
    cleaned = RE_MARKDOWN_CHARS.sub("", cleaned)
    return " ".join(cleaned.split()).strip()


def speak_text(text: str) -> None:
    global _current_tts_proc
    if not text or not is_tts_enabled():
        return

    clean = clean_text_for_speech(text)
    if not clean or len(clean) < 2:
        return

    def _run():
        global _current_tts_proc
        stop_tts()
        koko_bin = os.path.expanduser("~/.local/bin/koko")
        cmd = [koko_bin, clean] if os.path.exists(koko_bin) else ["koko", clean]
        try:
            with _tts_lock:
                _current_tts_proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            _current_tts_proc.wait()
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            with _tts_lock:
                _current_tts_proc = None

    threading.Thread(target=_run, daemon=True).start()


def speak_response(response_text: str) -> None:
    """Entry point called by agent_core after turn completion."""
    speak_text(response_text)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        speak_text(" ".join(sys.argv[1:]))
    else:
        toggle_tts()
