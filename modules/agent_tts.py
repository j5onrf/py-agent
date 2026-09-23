#!/usr/bin/env python3
"""Local-AI Kokoro Text-to-Speech Module [Production Ready]"""

import os
import re
import subprocess
import threading

CFG_DIR = os.path.expanduser("~/.config/py-agent")
VOICE_FILE = os.path.expanduser("~/.config/koko_current_voice")
SPEED_FILE = os.path.expanduser("~/.config/koko_speed")
DEFAULT_SPEED = 1.15

# Matches closed AND unclosed/truncated thinking blocks (<think>... to EOF)
RE_THINK_BLOCK = re.compile(r'<think(?:ing)?>[\s\S]*?(?:</think(?:ing)?>|$)|<thought>[\s\S]*?(?:</thought>|$)', re.DOTALL | re.IGNORECASE)
RE_CODE_BLOCK = re.compile(r'```[\s\S]*?(?:```|$)', re.DOTALL)
RE_INLINE_CODE = re.compile(r'`[^`\n]+`')
RE_URL = re.compile(r'https?://\S+')
RE_MARKDOWN_CHARS = re.compile(r'[*_#~>\[\]()|]')
RE_TIME_COLON = re.compile(r'(\b\d{1,2}):(\d{2}\b)')

_tts_lock = threading.Lock()

try:
    import agent_core as core
except ImportError:
    core = None


def stop_tts() -> None:
    subprocess.run(["pkill", "-9", "-f", "koko|pw-play"], stderr=subprocess.DEVNULL)


def is_tts_enabled() -> bool:
    try:
        if core:
            return bool(core.get_state("tts_enabled", False))
    except Exception:
        pass
    return False


def get_tts_speed() -> float:
    """Gets current TTS speed from state, config file, or default (1.15)."""
    try:
        if core and (val := core.get_state("tts_speed", None)):
            return float(val)
    except Exception:
        pass

    if os.path.exists(SPEED_FILE):
        try:
            with open(SPEED_FILE, "r", encoding="utf-8") as f:
                if v := f.read().strip():
                    return float(v)
        except (ValueError, OSError):
            pass
    return DEFAULT_SPEED


def set_tts_speed(speed: float) -> float:
    """Sets, clamps (0.5 - 2.5), and persists the TTS speed."""
    clamped = max(0.5, min(2.5, round(float(speed), 2)))
    if core:
        core.save_state("tts_speed", clamped)
    try:
        with open(SPEED_FILE, "w", encoding="utf-8") as f:
            f.write(str(clamped))
    except OSError:
        pass
    return clamped


def toggle_tts(enable: bool | None = None) -> bool:
    new_state = (not is_tts_enabled()) if enable is None else enable
    if not new_state:
        stop_tts()
    if core:
        core.save_state("tts_enabled", new_state)
    return new_state


def clean_text_for_speech(text: str) -> str:
    if not text:
        return ""
    if "[denied]" in text or "Operation halted:" in text or "Action cancelled" in text:
        return "Action cancelled."

    clean = RE_THINK_BLOCK.sub('', text)
    clean = RE_CODE_BLOCK.sub('', clean)
    clean = RE_INLINE_CODE.sub('', clean)
    clean = RE_URL.sub(' link ', clean)
    clean = RE_TIME_COLON.sub(r'\1 \2', clean)
    clean = clean.replace(':', ', ')
    clean = RE_MARKDOWN_CHARS.sub('', clean).strip()
    return " ".join(clean.split())


def speak_text(text: str) -> None:
    if not text or not is_tts_enabled():
        return
    clean = clean_text_for_speech(text)
    if not clean or len(clean) < 2:
        return

    def _run():
        with _tts_lock:
            stop_tts()
            voice = "am_echo"
            if os.path.exists(VOICE_FILE):
                try:
                    with open(VOICE_FILE, "r", encoding="utf-8") as f:
                        if v := f.read().strip():
                            voice = v
                except OSError:
                    pass

            speed = get_tts_speed()
            wav_path = f"/dev/shm/tts_{os.getpid()}.wav"

            # Execute without shell=True to eliminate quote-escaping failures
            koko_env = os.environ.copy()
            koko_env["OMP_NUM_THREADS"] = "6"
            koko_env["OMP_WAIT_POLICY"] = "PASSIVE"

            koko_cmd = [
                "nice", "-n", "-10",
                "koko", "--style", voice, "--speed", str(speed),
                "text", clean, "-o", wav_path
            ]
            try:
                res = subprocess.run(koko_cmd, env=koko_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0 and os.path.exists(wav_path):
                    subprocess.run(["pw-play", wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            finally:
                if os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except OSError:
                        pass

    threading.Thread(target=_run, daemon=True).start()


def speak_response(response_text: str) -> None:
    speak_text(response_text)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        speak_text(" ".join(sys.argv[1:]))
    else:
        toggle_tts()
