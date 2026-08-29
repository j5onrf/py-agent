#!/usr/bin/env python3
"""Local-AI Kokoro Text-to-Speech (Text Out Loud) Module [Zero-Lag Edition]"""

import os, re, subprocess, threading

CFG_DIR = os.path.expanduser("~/.config/py-agent")
VOICE_FILE = os.path.expanduser("~/.config/koko_current_voice")

RE_THINK_BLOCK = re.compile(r'<think>.*?</think>', re.DOTALL)
RE_CODE_BLOCK = re.compile(r'```.*?```', re.DOTALL)
RE_MARKDOWN_CHARS = re.compile(r'[*_#`~>\[\]()|]')
RE_TIME_COLON = re.compile(r'(\b\d{1,2}):(\d{2}\b)')

try: import agent_core as core
except ImportError: core = None


def stop_tts() -> None:
    subprocess.run("pkill -9 -f 'pw-play|koko'", shell=True, stderr=subprocess.DEVNULL)


def is_tts_enabled() -> bool:
    try:
        if core: return bool(core.get_state("tts_enabled", False))
    except Exception: pass
    return False


def toggle_tts(enable: bool | None = None) -> bool:
    new_state = (not is_tts_enabled()) if enable is None else enable
    if not new_state: stop_tts()
    if core: core.save_state("tts_enabled", new_state)
    return new_state


def clean_text_for_speech(text: str) -> str:
    if not text: return ""
    clean = RE_THINK_BLOCK.sub('', text)
    clean = RE_CODE_BLOCK.sub('code block omitted', clean)
    clean = RE_TIME_COLON.sub(r'\1 \2', clean)
    clean = clean.replace(':', ', ')
    clean = RE_MARKDOWN_CHARS.sub('', clean).strip()
    return " ".join(clean.split())


def speak_text(text: str) -> None:
    if not text or not is_tts_enabled(): return
    clean = clean_text_for_speech(text)
    if not clean or len(clean) < 2: return

    def _run():
        stop_tts()
        voice = "am_echo"
        if os.path.exists(VOICE_FILE):
            try:
                with open(VOICE_FILE, "r", encoding="utf-8") as f:
                    if v := f.read().strip(): voice = v
            except OSError: pass

        wav_path = "/dev/shm/tts.wav"
        escaped = clean.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
        cmd = f'OMP_NUM_THREADS=4 koko --style "{voice}" --speed 1.15 text "{escaped}" -o {wav_path} 2>/dev/null && pw-play {wav_path}'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    threading.Thread(target=_run, daemon=True).start()


def speak_response(response_text: str) -> None:
    speak_text(response_text)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        speak_text(" ".join(sys.argv[1:]))
    else:
        toggle_tts()
