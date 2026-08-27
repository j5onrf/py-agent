#!/usr/bin/env python3
"""Local-AI Kokoro Text-to-Speech (Text Out Loud) Module"""

import os
import re
import subprocess
import threading

VOICE_FILE = os.path.expanduser("~/.config/koko_current_voice")

RE_THINK_BLOCK: re.Pattern = re.compile(r"<think>.*?</think>", re.DOTALL)
RE_CODE_BLOCK: re.Pattern = re.compile(r"```.*?```", re.DOTALL)
RE_MARKDOWN_CHARS: re.Pattern = re.compile(r"[*_#`~>\[\]()|]")
RE_TIME_COLON: re.Pattern = re.compile(r"(\b\d{1,2}):(\d{2}\b)")

try:
    import agent_core as core
except ImportError:
    core = None


def stop_tts() -> None:
    subprocess.run("pkill -9 -f 'pw-play|koko'", shell=True, stderr=subprocess.DEVNULL)


def is_tts_enabled() -> bool:
    try:
        if core:
            return bool(core.get_state("tts_enabled", False))
    except Exception:
        pass
    return False


def speak_text(text: str) -> None:
    if not is_tts_enabled():
        return
    if not text or not text.strip():
        return

    clean = RE_THINK_BLOCK.sub("", text)
    clean = RE_CODE_BLOCK.sub("code block omitted", clean)
    clean = RE_TIME_COLON.sub(r"\1 \2", clean)  # Converts 11:36 -> 11 36
    clean = clean.replace(
        ":", ", "
    )  # Replaces any lingering colons with natural pauses
    clean = RE_MARKDOWN_CHARS.sub("", clean).strip()
    if not clean:
        return

    def _run():
        stop_tts()
        voice = "am_echo"
        if os.path.exists(VOICE_FILE):
            try:
                with open(VOICE_FILE, "r", encoding="utf-8") as f:
                    if v := f.read().strip():
                        voice = v
            except OSError:
                pass

        wav_path = "/dev/shm/tts.wav"
        # Strict shell escaping protects against code execution or syntax errors
        escaped_text = (
            clean.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("$", "\\$")
            .replace("`", "\\`")
        )
        cmd = f'OMP_NUM_THREADS=4 koko --style "{voice}" --speed 1.15 text "{escaped_text}" -o {wav_path} 2>/dev/null && pw-play {wav_path}'
        subprocess.run(
            cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    threading.Thread(target=_run, daemon=True).start()


def speak_response(text: str) -> None:
    if is_tts_enabled():
        speak_text(text)


def toggle_tts() -> bool:
    new_state = not is_tts_enabled()
    if not new_state:
        stop_tts()
    if core:
        core.save_state("tts_enabled", new_state)
    return new_state
