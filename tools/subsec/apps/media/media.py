#!/usr/bin/env python3
"""
Universal Full-Screen Responsive Media Player TUI v2.2 [TUIAMP]
Optimized asynchronous MPRIS controller with unbuffered POSIX fd key reading
(Kitty, Foot, Alacritty, xterm, tmux), cascading audio backends (wpctl, pactl,
amixer, playerctl), and zero-flicker double-buffered rendering.
"""

import sys
import os
import tty
import termios
import select
import subprocess
import shutil
import time
import math
import random
import re
import unicodedata
import signal

# -----------------------------------------------------------------------------
# Terminal & Text Utilities
# -----------------------------------------------------------------------------
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """Strips ANSI escape codes to compute visual plain-text width."""
    return ANSI_ESCAPE.sub('', text)

def char_display_width(ch: str) -> int:
    """Calculates terminal visual column width for Unicode/CJK characters."""
    ea = unicodedata.east_asian_width(ch)
    return 2 if ea in ('F', 'W') else 1

def str_display_width(s: str) -> int:
    """Returns visual terminal display width taking wide glyphs into account."""
    clean = strip_ansi(s)
    return sum(char_display_width(c) for c in clean)

def truncate_str_display(s: str, max_width: int) -> str:
    """Truncates text safely to a visual column width."""
    cur_width = 0
    res = []
    for ch in s:
        w = char_display_width(ch)
        if cur_width + w > max_width:
            break
        res.append(ch)
        cur_width += w
    return "".join(res)

def fmt_time(seconds: float) -> str:
    """Converts seconds into clean MM:SS or H:MM:SS format."""
    if seconds <= 0:
        return "00:00"
    secs = int(seconds)
    hrs = secs // 3600
    mins = (secs % 3600) // 60
    rem_secs = secs % 60
    if hrs > 0:
        return f"{hrs:d}:{mins:02d}:{rem_secs:02d}"
    return f"{mins:02d}:{rem_secs:02d}"

# -----------------------------------------------------------------------------
# Color Themes Palette Engine
# -----------------------------------------------------------------------------
THEMES = [
    {
        "name": "Cyberpunk Neon",
        "border": "\033[38;5;238m",
        "accent": "\033[1;38;5;226m",
        "track": "\033[1;38;5;51m",
        "artist": "\033[38;5;201m",
        "badge_play": "\033[1;38;5;226m",
        "prog_fill": "\033[38;5;51m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;201m●\033[0m",
        "viz_peak": "\033[1;38;5;201m",
        "viz_high": "\033[38;5;198m",
        "viz_mid": "\033[38;5;226m",
        "viz_low": "\033[38;5;51m",
        "vol_fill": "\033[38;5;51m",
        "dim": "\033[38;5;242m",
    },
    {
        "name": "Winamp Classic",
        "border": "\033[38;5;238m",
        "accent": "\033[1;38;5;46m",
        "track": "\033[1;38;5;228m",
        "artist": "\033[38;5;118m",
        "badge_play": "\033[1;38;5;46m",
        "prog_fill": "\033[38;5;46m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;226m●\033[0m",
        "viz_peak": "\033[1;38;5;196m",
        "viz_high": "\033[38;5;208m",
        "viz_mid": "\033[38;5;226m",
        "viz_low": "\033[38;5;46m",
        "vol_fill": "\033[38;5;46m",
        "dim": "\033[38;5;242m",
    },
    {
        "name": "Synthwave '84",
        "border": "\033[38;5;60m",
        "accent": "\033[1;38;5;207m",
        "track": "\033[1;38;5;87m",
        "artist": "\033[38;5;213m",
        "badge_play": "\033[1;38;5;87m",
        "prog_fill": "\033[38;5;205m",
        "prog_empty": "\033[38;5;237m",
        "prog_knob": "\033[1;38;5;87m●\033[0m",
        "viz_peak": "\033[1;38;5;225m",
        "viz_high": "\033[38;5;201m",
        "viz_mid": "\033[38;5;171m",
        "viz_low": "\033[38;5;45m",
        "vol_fill": "\033[38;5;207m",
        "dim": "\033[38;5;103m",
    },
    {
        "name": "Amber CRT",
        "border": "\033[38;5;94m",
        "accent": "\033[1;38;5;220m",
        "track": "\033[1;38;5;214m",
        "artist": "\033[38;5;178m",
        "badge_play": "\033[1;38;5;220m",
        "prog_fill": "\033[38;5;214m",
        "prog_empty": "\033[38;5;235m",
        "prog_knob": "\033[1;38;5;229m●\033[0m",
        "viz_peak": "\033[1;38;5;229m",
        "viz_high": "\033[38;5;220m",
        "viz_mid": "\033[38;5;214m",
        "viz_low": "\033[38;5;172m",
        "vol_fill": "\033[38;5;214m",
        "dim": "\033[38;5;136m",
    },
    {
        "name": "Dracula",
        "border": "\033[38;5;60m",
        "accent": "\033[1;38;5;141m",
        "track": "\033[1;38;5;117m",
        "artist": "\033[38;5;212m",
        "badge_play": "\033[1;38;5;84m",
        "prog_fill": "\033[38;5;141m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;212m●\033[0m",
        "viz_peak": "\033[1;38;5;212m",
        "viz_high": "\033[38;5;141m",
        "viz_mid": "\033[38;5;117m",
        "viz_low": "\033[38;5;84m",
        "vol_fill": "\033[38;5;141m",
        "dim": "\033[38;5;103m",
    },
    {
        "name": "Matrix Phosphor",
        "border": "\033[38;5;22m",
        "accent": "\033[1;38;5;120m",
        "track": "\033[1;38;5;46m",
        "artist": "\033[38;5;82m",
        "badge_play": "\033[1;38;5;154m",
        "prog_fill": "\033[38;5;46m",
        "prog_empty": "\033[38;5;234m",
        "prog_knob": "\033[1;38;5;231m●\033[0m",
        "viz_peak": "\033[1;38;5;231m",
        "viz_high": "\033[38;5;120m",
        "viz_mid": "\033[38;5;46m",
        "viz_low": "\033[38;5;28m",
        "vol_fill": "\033[38;5;46m",
        "dim": "\033[38;5;29m",
    },
    {
        "name": "Nord Frost",
        "border": "\033[38;5;238m",
        "accent": "\033[1;38;5;111m",
        "track": "\033[1;38;5;123m",
        "artist": "\033[38;5;150m",
        "badge_play": "\033[1;38;5;150m",
        "prog_fill": "\033[38;5;111m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;231m●\033[0m",
        "viz_peak": "\033[1;38;5;231m",
        "viz_high": "\033[38;5;111m",
        "viz_mid": "\033[38;5;109m",
        "viz_low": "\033[38;5;67m",
        "vol_fill": "\033[38;5;111m",
        "dim": "\033[38;5;244m",
    },
    {
        "name": "Tokyo Night",
        "border": "\033[38;5;60m",
        "accent": "\033[1;38;5;211m",
        "track": "\033[1;38;5;111m",
        "artist": "\033[38;5;180m",
        "badge_play": "\033[1;38;5;120m",
        "prog_fill": "\033[38;5;111m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;211m●\033[0m",
        "viz_peak": "\033[1;38;5;211m",
        "viz_high": "\033[38;5;176m",
        "viz_mid": "\033[38;5;111m",
        "viz_low": "\033[38;5;73m",
        "vol_fill": "\033[38;5;111m",
        "dim": "\033[38;5;103m",
    }
]

# -----------------------------------------------------------------------------
# Visualizer Physics Engine
# -----------------------------------------------------------------------------
class VisualizerPhysics:
    def __init__(self, max_bands=256):
        self.max_bands = max_bands
        self.heights = [0.0] * max_bands
        self.peaks = [0.0] * max_bands
        self.velocities = [0.0] * max_bands
        self.osc_phase = 0.0

    def update(self, is_playing: bool, cols: int, ticks: int):
        if cols > len(self.heights):
            diff = cols - len(self.heights) + 32
            self.heights.extend([0.0] * diff)
            self.peaks.extend([0.0] * diff)
            self.velocities.extend([0.0] * diff)

        t = ticks * 0.14
        self.osc_phase += 0.2

        if is_playing:
            kick = (max(0.0, math.sin(t * 1.8)) ** 8) * 3.8
            sub_pulse = (max(0.0, math.cos(t * 0.9)) ** 6) * 2.2
            snare = (max(0.0, math.sin(t * 3.6 + 0.8)) ** 10) * 2.0

            for i in range(cols):
                ratio = i / max(1, cols)
                bass_comp = (kick * 1.0 + sub_pulse * 0.8) * max(0.0, 1.0 - ratio * 3.2)
                mid_wave = math.sin(t * 1.4 + i * 0.22) * math.cos(t * 0.7 - i * 0.15)
                mid_comp = (mid_wave + 1.2) * 1.6 * max(0.0, 1.0 - abs(ratio - 0.42) * 2.0)
                jitter = random.uniform(0.1, 0.9) if (i % 2 == 0 or snare > 1.0) else random.uniform(0.0, 0.4)
                high_comp = (snare * 0.9 + jitter * 2.2) * ratio

                target = min(3.99, max(0.1, bass_comp + mid_comp + high_comp))

                if target > self.heights[i]:
                    self.heights[i] = self.heights[i] * 0.35 + target * 0.65
                else:
                    self.heights[i] = self.heights[i] * 0.75 + target * 0.25

                if self.heights[i] >= self.peaks[i]:
                    self.peaks[i] = self.heights[i]
                    self.velocities[i] = 0.0
                else:
                    self.velocities[i] += 0.05
                    self.peaks[i] = max(0.0, self.peaks[i] - self.velocities[i])
        else:
            for i in range(cols):
                self.heights[i] = max(0.0, self.heights[i] * 0.82)
                self.peaks[i] = max(0.0, self.peaks[i] - 0.12)
                self.velocities[i] = 0.0

VIZ_NAMES = [
    "Peak-Cap Equalizer",
    "Braille Spectrogram",
    "Stereo VU Deck",
    "CRT Oscilloscope",
    "Symmetrical Wings",
    "Cyber Matrix Rain"
]

def render_peak_equalizer(physics: VisualizerPhysics, cols: int, theme: dict) -> list:
    lines = [[] for _ in range(4)]
    row_colors = [theme["viz_high"], theme["viz_mid"], theme["viz_mid"], theme["viz_low"]]
    peak_color = theme["viz_peak"]

    for r in range(4):
        lower = 3.0 - r
        upper = lower + 1.0
        row_chars = []
        for c in range(cols):
            h = physics.heights[c]
            p = physics.peaks[c]
            if h >= upper:
                row_chars.append(f"{row_colors[r]}█\033[0m")
            elif h > lower:
                frac = h - lower
                char = "▆" if frac > 0.65 else ("▄" if frac > 0.35 else "▂")
                row_chars.append(f"{row_colors[r]}{char}\033[0m")
            elif p >= lower and p < upper and p > 0.2:
                row_chars.append(f"{peak_color}▔\033[0m")
            else:
                row_chars.append(" ")
        lines[r] = "".join(row_chars)
    return lines

def render_braille_spectrogram(physics: VisualizerPhysics, cols: int, theme: dict) -> list:
    lines = [[] for _ in range(4)]
    row_colors = [theme["viz_high"], theme["viz_mid"], theme["viz_mid"], theme["viz_low"]]
    peak_color = theme["viz_peak"]

    for r in range(4):
        lower = 3.0 - r
        upper = lower + 1.0
        row_chars = []
        for c in range(cols):
            h = physics.heights[c]
            p = physics.peaks[c]
            if h >= upper:
                row_chars.append(f"{row_colors[r]}⣿\033[0m")
            elif h > lower:
                frac = h - lower
                b_char = "⣶" if frac > 0.7 else ("⣤" if frac > 0.45 else ("⣀" if frac > 0.2 else "⠤"))
                row_chars.append(f"{row_colors[r]}{b_char}\033[0m")
            elif p >= lower and p < upper and p > 0.2:
                row_chars.append(f"{peak_color}⠉\033[0m")
            else:
                row_chars.append(" ")
        lines[r] = "".join(row_chars)
    return lines

def render_stereo_vu_deck(physics: VisualizerPhysics, cols: int, theme: dict, is_playing: bool, ticks: int) -> list:
    lines = [""] * 4
    if is_playing:
        half = max(1, cols // 2)
        l_energy = sum(physics.heights[:half]) / half
        r_energy = sum(physics.heights[half:cols]) / half
        l_level = max(0.05, min(1.0, (l_energy / 2.8) + math.sin(ticks * 0.4) * 0.12))
        r_level = max(0.05, min(1.0, (r_energy / 2.8) + math.cos(ticks * 0.35) * 0.12))
    else:
        l_level, r_level = 0.02, 0.02

    bar_w = max(12, cols - 26)
    l_filled = int(l_level * bar_w)
    r_filled = int(r_level * bar_w)

    l_db = -20.0 + (l_level * 23.0)
    r_db = -20.0 + (r_level * 23.0)

    l_peak = " \033[1;38;5;196m[CLIP]\033[0m" if l_db >= 0.0 else "       "
    r_peak = " \033[1;38;5;196m[CLIP]\033[0m" if r_db >= 0.0 else "       "

    def make_vu_bar(filled, total):
        chars = []
        g_end = int(total * 0.65)
        y_end = int(total * 0.85)
        for i in range(total):
            if i < filled:
                if i < g_end:
                    chars.append(f"{theme['viz_low']}█\033[0m")
                elif i < y_end:
                    chars.append(f"{theme['viz_mid']}█\033[0m")
                else:
                    chars.append(f"{theme['viz_peak']}█\033[0m")
            else:
                chars.append(f"{theme['dim']}·\033[0m")
        return "".join(chars)

    hdr = "-20   -15   -10    -7    -5    -3    -1     0   +1   +2   +3 dB"
    hdr_trimmed = hdr[:bar_w].ljust(bar_w)

    lines[0] = f"      {theme['dim']}{hdr_trimmed}\033[0m"
    lines[1] = f"L  [{make_vu_bar(l_filled, bar_w)}] {l_db:+4.1f}dB{l_peak}"
    lines[2] = f"R  [{make_vu_bar(r_filled, bar_w)}] {r_db:+4.1f}dB{r_peak}"
    lines[3] = f"      {theme['dim']}{hdr_trimmed}\033[0m"

    for r in range(4):
        p_len = str_display_width(lines[r])
        pad = cols - p_len
        if pad > 0:
            lines[r] = " " * (pad // 2) + lines[r] + " " * (pad - pad // 2)
    return lines

def render_oscilloscope(physics: VisualizerPhysics, cols: int, theme: dict, is_playing: bool) -> list:
    lines = [[" "] * cols for _ in range(4)]
    if not is_playing:
        for c in range(cols):
            lines[2][c] = f"{theme['dim']}─\033[0m"
        return ["".join(row) for row in lines]

    phase = physics.osc_phase
    for c in range(cols):
        idx = min(c, len(physics.heights) - 1)
        amp = max(0.2, physics.heights[idx] / 1.8)
        y = 1.5 + (math.sin(phase + c * 0.18) * 1.1 + math.cos(phase * 1.4 + c * 0.09) * 0.6) * (amp / 2.0)
        row_idx = max(0, min(3, int(round(y))))
        char = f"{theme['viz_high']}~" if row_idx in (0, 3) else f"{theme['viz_low']}─"
        if c % 4 == 0:
            char = f"{theme['viz_mid']}●"
        lines[row_idx][c] = f"{char}\033[0m"
    return ["".join(row) for row in lines]

def render_symmetrical_wings(physics: VisualizerPhysics, cols: int, theme: dict) -> list:
    lines = [[] for _ in range(4)]
    row_colors = [theme["viz_high"], theme["viz_mid"], theme["viz_mid"], theme["viz_low"]]
    half = cols // 2

    for r in range(4):
        lower = 3.0 - r
        upper = lower + 1.0
        left_chars, right_chars = [], []
        for i in range(half):
            idx = min(i, len(physics.heights) - 1)
            h = physics.heights[idx]
            p = physics.peaks[idx]
            if h >= upper:
                char = f"{row_colors[r]}█\033[0m"
            elif h > lower:
                frac = h - lower
                char = f"{row_colors[r]}{'▆' if frac > 0.5 else '▄'}\033[0m"
            elif p >= lower and p < upper and p > 0.2:
                char = f"{theme['viz_peak']}▔\033[0m"
            else:
                char = " "
            left_chars.insert(0, char)
            right_chars.append(char)

        spacer = [" "] if (cols % 2 != 0) else []
        lines[r] = "".join(left_chars + spacer + right_chars)
    return lines

def render_cyber_matrix(physics: VisualizerPhysics, cols: int, theme: dict, is_playing: bool, ticks: int) -> list:
    matrix_chars = "0123456789ABCDEFｦｱｳｴｵｶｷｹｺｻｼｽｾｿ"
    lines = [[] for _ in range(4)]
    for r in range(4):
        lower = 3.0 - r
        row_chars = []
        for c in range(cols):
            idx = min(c, len(physics.heights) - 1)
            h = physics.heights[idx]
            if is_playing and h > lower:
                ch = matrix_chars[(ticks + c * 3 + r * 7) % len(matrix_chars)]
                color = theme["viz_peak"] if r == 0 else (theme["viz_high"] if r == 1 else theme["viz_low"])
                row_chars.append(f"{color}{ch}\033[0m")
            elif is_playing and (c + ticks) % 11 == 0:
                ch = matrix_chars[(c + ticks) % len(matrix_chars)]
                row_chars.append(f"{theme['dim']}{ch}\033[0m")
            else:
                row_chars.append(" ")
        lines[r] = "".join(row_chars)
    return lines

def generate_visualizer_panel(mode: int, physics: VisualizerPhysics, cols: int, theme: dict, is_playing: bool, ticks: int) -> list:
    if mode == 0:
        return render_peak_equalizer(physics, cols, theme)
    elif mode == 1:
        return render_braille_spectrogram(physics, cols, theme)
    elif mode == 2:
        return render_stereo_vu_deck(physics, cols, theme, is_playing, ticks)
    elif mode == 3:
        return render_oscilloscope(physics, cols, theme, is_playing)
    elif mode == 4:
        return render_symmetrical_wings(physics, cols, theme)
    else:
        return render_cyber_matrix(physics, cols, theme, is_playing, ticks)

# -----------------------------------------------------------------------------
# Cascading Audio System (PipeWire -> PulseAudio -> ALSA -> Playerctl)
# -----------------------------------------------------------------------------
class SystemAudio:
    def __init__(self):
        self.volume = 100
        self.is_muted = False
        self.last_check = 0.0

    def query(self, force=False, active_player=None) -> tuple:
        now = time.time()
        if not force and (now - self.last_check < 1.0):
            return self.volume, self.is_muted
        self.last_check = now

        # 1. PipeWire / WirePlumber (wpctl)
        if shutil.which("wpctl"):
            for sink in ("@DEFAULT_AUDIO_SINK@", "@DEFAULT_SINK@"):
                try:
                    res = subprocess.run(["wpctl", "get-volume", sink], capture_output=True, text=True, timeout=0.25)
                    if res.returncode == 0 and "Volume:" in res.stdout:
                        self.is_muted = "[MUTED]" in res.stdout
                        val = res.stdout.replace("Volume:", "").replace("[MUTED]", "").strip().split()[0]
                        self.volume = max(0, min(100, int(round(float(val) * 100))))
                        return self.volume, self.is_muted
                except Exception:
                    pass

        # 2. PulseAudio / pipewire-pulse (pactl)
        if shutil.which("pactl"):
            try:
                res = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture_output=True, text=True, timeout=0.25)
                if res.returncode == 0 and "Volume:" in res.stdout:
                    for p in res.stdout.split():
                        if "%" in p:
                            self.volume = max(0, min(100, int(p.replace("%", ""))))
                            break
                    m_res = subprocess.run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], capture_output=True, text=True, timeout=0.2)
                    self.is_muted = "yes" in m_res.stdout.lower()
                    return self.volume, self.is_muted
            except Exception:
                pass

        # 3. ALSA (amixer)
        if shutil.which("amixer"):
            try:
                res = subprocess.run(["amixer", "sget", "Master"], capture_output=True, text=True, timeout=0.25)
                if res.returncode == 0:
                    matches = re.findall(r'\[(\d+)%\]', res.stdout)
                    if matches:
                        self.volume = max(0, min(100, int(matches[0])))
                    self.is_muted = "[off]" in res.stdout
                    return self.volume, self.is_muted
            except Exception:
                pass

        # 4. Fallback: direct playerctl volume
        if active_player and shutil.which("playerctl"):
            try:
                res = subprocess.run(["playerctl", f"--player={active_player}", "volume"], capture_output=True, text=True, timeout=0.25)
                if res.returncode == 0 and res.stdout.strip():
                    self.volume = max(0, min(100, int(round(float(res.stdout.strip()) * 100))))
                    return self.volume, self.is_muted
            except Exception:
                pass

        return self.volume, self.is_muted

    def adjust(self, delta: int, active_player=None):
        self.volume = max(0, min(100, self.volume + delta))
        self.last_check = time.time()

        step_flt = abs(delta) / 100.0
        wp_arg = f"{step_flt:.2f}+" if delta > 0 else f"{step_flt:.2f}-"
        pa_arg = f"+{abs(delta)}%" if delta > 0 else f"-{abs(delta)}%"
        pctl_arg = f"{step_flt:.2f}+" if delta > 0 else f"{step_flt:.2f}-"

        # 1. wpctl with -l 1.5 to allow over 100% on Arch WirePlumber
        if shutil.which("wpctl"):
            for sink in ("@DEFAULT_AUDIO_SINK@", "@DEFAULT_SINK@"):
                try:
                    res = subprocess.run(["wpctl", "set-volume", "-l", "1.5", sink, wp_arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.2)
                    if res.returncode == 0:
                        return
                except Exception:
                    pass

        # 2. pactl fallback
        if shutil.which("pactl"):
            try:
                res = subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", pa_arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.2)
                if res.returncode == 0:
                    return
            except Exception:
                pass

        # 3. amixer fallback
        if shutil.which("amixer"):
            try:
                ami_arg = f"{abs(delta)}%+" if delta > 0 else f"{abs(delta)}%-"
                res = subprocess.run(["amixer", "set", "Master", ami_arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.2)
                if res.returncode == 0:
                    return
            except Exception:
                pass

        # 4. playerctl fallback
        if active_player and shutil.which("playerctl"):
            try:
                subprocess.Popen(["playerctl", f"--player={active_player}", "volume", pctl_arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.last_check = time.time()

        if shutil.which("wpctl"):
            for sink in ("@DEFAULT_AUDIO_SINK@", "@DEFAULT_SINK@"):
                try:
                    res = subprocess.run(["wpctl", "set-mute", sink, "toggle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.2)
                    if res.returncode == 0:
                        return
                except Exception:
                    pass

        if shutil.which("pactl"):
            try:
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.2)
            except Exception:
                pass

# -----------------------------------------------------------------------------
# MPRIS Controller
# -----------------------------------------------------------------------------
class PlayerManager:
    DELIM = "<!@!>"
    FORMAT = f"{{{{playerName}}}}{DELIM}{{{{status}}}}{DELIM}{{{{artist}}}}{DELIM}{{{{title}}}}{DELIM}{{{{position}}}}{DELIM}{{{{mpris:length}}}}"

    def __init__(self):
        self.active_player = None
        self.player_name = ""
        self.title = ""
        self.artist = ""
        self.status = "Stopped"
        self.is_playing = False
        self.position = 0.0
        self.length = 0.0
        self.shuffle = False
        self.loop_status = "None"
        self.last_sync = 0.0
        self.last_frame = time.time()
        self.last_player_scan = 0.0

    def parse_time(self, raw_str: str) -> float:
        if not raw_str:
            return 0.0
        try:
            val = float(raw_str)
            return val / 1_000_000.0 if val > 1_000_000 else val
        except (ValueError, TypeError):
            return 0.0

    def find_best_player(self) -> str:
        try:
            res = subprocess.run(["playerctl", "-l"], capture_output=True, text=True, check=True, timeout=0.2)
            players = [p.strip() for p in res.stdout.strip().split('\n') if p.strip()]
        except Exception:
            return None

        if not players:
            return None

        if self.active_player in players:
            return self.active_player

        chromium_tier, firefox_tier, other_tier = [], [], []
        for p in players:
            p_low = p.lower()
            if any(k in p_low for k in ("brave", "chromium", "chrome")):
                chromium_tier.append(p)
            elif "firefox" in p_low:
                firefox_tier.append(p)
            else:
                other_tier.append(p)

        sorted_players = chromium_tier + firefox_tier + other_tier
        for p in sorted_players:
            try:
                st = subprocess.run(["playerctl", f"--player={p}", "status"], capture_output=True, text=True, timeout=0.1).stdout.strip()
                if st == "Playing":
                    return p
            except Exception:
                pass

        return sorted_players[0] if sorted_players else None

    def update(self):
        now = time.time()
        dt = now - self.last_frame
        self.last_frame = now

        if self.is_playing and self.length > 0:
            self.position = min(self.length, self.position + dt)

        if now - self.last_sync > 0.6:
            self.last_sync = now
            if not self.active_player or (now - self.last_player_scan > 2.5):
                self.active_player = self.find_best_player()
                self.last_player_scan = now

            if not self.active_player:
                self.title = ""
                self.is_playing = False
                return

            cmd = ["playerctl", f"--player={self.active_player}", "metadata", "--format", self.FORMAT]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=0.25)
                if res.returncode == 0 and self.DELIM in res.stdout:
                    parts = res.stdout.strip().split(self.DELIM)
                    if len(parts) >= 6:
                        self.player_name = parts[0] or self.active_player
                        self.status = parts[1]
                        self.is_playing = (self.status == "Playing")
                        self.artist = parts[2]
                        self.title = parts[3]
                        self.position = self.parse_time(parts[4])
                        self.length = self.parse_time(parts[5])
                else:
                    self.active_player = None
            except Exception:
                self.active_player = None

    def toggle(self):
        if not self.active_player:
            return
        if "spotify" in self.active_player.lower() and shutil.which("xdotool"):
            subprocess.Popen(["xdotool", "key", "XF86AudioPlay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        subprocess.Popen(["playerctl", f"--player={self.active_player}", "play-pause"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def next(self):
        if self.active_player:
            subprocess.Popen(["playerctl", f"--player={self.active_player}", "next"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def previous(self):
        if self.active_player:
            subprocess.Popen(["playerctl", f"--player={self.active_player}", "previous"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def seek(self, seconds: int):
        if self.active_player:
            if self.length > 0:
                self.position = max(0.0, min(self.length, self.position + seconds))
            arg = f"{abs(seconds)}s+" if seconds > 0 else f"{abs(seconds)}s-"
            subprocess.Popen(["playerctl", f"--player={self.active_player}", "position", arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def toggle_shuffle(self):
        if self.active_player:
            self.shuffle = not self.shuffle
            subprocess.Popen(["playerctl", f"--player={self.active_player}", "shuffle", "Toggle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def cycle_loop(self):
        if self.active_player:
            nxt = {"None": "Track", "Track": "Playlist", "Playlist": "None"}.get(self.loop_status, "Track")
            self.loop_status = nxt
            subprocess.Popen(["playerctl", f"--player={self.active_player}", "loop", nxt], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -----------------------------------------------------------------------------
# Input Handling (Unbuffered POSIX File Descriptor Read)
# -----------------------------------------------------------------------------
def get_key_non_blocking() -> str:
    """Reads unbuffered bytes directly from the OS file descriptor,
    capturing entire Kitty/xterm escape packets atomically."""
    fd = sys.stdin.fileno()
    rlist, _, _ = select.select([fd], [], [], 0.0)
    if not rlist:
        return None

    try:
        raw_bytes = os.read(fd, 64)
    except OSError:
        return None

    if not raw_bytes:
        return None

    # Handle Escape Sequences
    if raw_bytes[0] == 0x1B:
        if len(raw_bytes) == 1:
            # Check if trailing bytes are still in transit
            rlist, _, _ = select.select([fd], [], [], 0.025)
            if rlist:
                try:
                    raw_bytes += os.read(fd, 63)
                except OSError:
                    pass
            else:
                return "ESC"

        try:
            seq = raw_bytes.decode('latin1')
        except Exception:
            return None

        # Normalize Arrow Keys across Kitty (SS3 \x1bOA), ANSI (\x1b[A), and Kitty Protocol (\x1b[1;1A)
        if seq in ("\x1b[A", "\x1bOA") or (seq.startswith("\x1b[") and seq.endswith("A")):
            return "UP"
        if seq in ("\x1b[B", "\x1bOB") or (seq.startswith("\x1b[") and seq.endswith("B")):
            return "DOWN"
        if seq in ("\x1b[C", "\x1bOC") or (seq.startswith("\x1b[") and seq.endswith("C")):
            return "RIGHT"
        if seq in ("\x1b[D", "\x1bOD") or (seq.startswith("\x1b[") and seq.endswith("D")):
            return "LEFT"

        return seq

    try:
        return raw_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return None

def format_row(colored_text: str, width: int, align="center", border_color="\033[90m") -> str:
    plain_len = str_display_width(colored_text)
    pad = max(0, width - plain_len)
    if align == "center":
        left = pad // 2
        content = " " * left + colored_text + " " * (pad - left)
    elif align == "left":
        left = min(3, pad)
        content = " " * left + colored_text + " " * (pad - left)
    else:
        right = min(3, pad)
        content = " " * (pad - right) + colored_text + " " * right
    return f"{border_color}│\033[0m{content}{border_color}│\033[0m\r\n"

# -----------------------------------------------------------------------------
# Main Application Loop
# -----------------------------------------------------------------------------
def run_tuiamp():
    if not shutil.which("playerctl"):
        print("\033[1;31mError: 'playerctl' is required to run TUIAMP.\033[0m")
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    player = PlayerManager()
    audio = SystemAudio()
    physics = VisualizerPhysics()

    theme_idx = 0
    viz_mode = 0
    ticks = 0
    last_w, last_h = 0, 0

    sys.stdout.write("\033[?1049h\033[?25l\033[H\033[J")
    sys.stdout.flush()

    def cleanup(*_):
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?1049l\033[?25h")
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        tty.setraw(fd)

        while True:
            ticks += 1
            theme = THEMES[theme_idx]

            player.update()
            volume, is_muted = audio.query(active_player=player.active_player)
            W, H = shutil.get_terminal_size()

            if W != last_w or H != last_h:
                sys.stdout.write("\033[H\033[J")
                last_w, last_h = W, H

            if H < 21 or W < 54:
                sys.stdout.write("\033[H\033[J")
                sys.stdout.write(" Terminal window too small for TUIAMP display (min 54x21).\r\n")
                sys.stdout.write(" Please expand your terminal.\r\n")
                sys.stdout.flush()
                time.sleep(0.1)
                continue

            box_width = W - 2
            viz_width = W - 8

            physics.update(player.is_playing, viz_width, ticks)

            content_rows = []

            # 1. Header
            header = (
                f"{theme['accent']}▶ T U I A M P\033[0m {theme['dim']}──\033[0m "
                f"\033[1mTHEME:\033[0m {theme['name']} {theme['dim']}──\033[0m "
                f"\033[1mVIZ:\033[0m {VIZ_NAMES[viz_mode]}"
            )
            content_rows.append((header, "center"))
            content_rows.append(("", "center"))

            # 2. Track Title
            if player.title:
                full_track = f"{player.artist} - {player.title}" if player.artist else player.title
                for tag in [" - YouTube Music", " - YouTube", " - Spotify"]:
                    full_track = full_track.split(tag)[0]
                max_track_w = max(18, W - 16)
                if str_display_width(full_track) > max_track_w:
                    clean_track = truncate_str_display(full_track, max_track_w - 3) + "..."
                else:
                    clean_track = full_track
                content_rows.append((f"♫  {theme['track']}{clean_track}\033[0m", "center"))
            else:
                clean_track = "(No Active Media Player)"
                content_rows.append((f"{theme['dim']}♫  {clean_track}\033[0m", "center"))

            # 3. Badges & Timers
            time_pos = fmt_time(player.position)
            time_len = fmt_time(player.length) if player.length > 0 else "--:--"
            time_line = f"{time_pos} / {time_len}"

            if player.is_playing:
                status_badge = f"{theme['badge_play']}▶ Playing\033[0m"
            elif player.title:
                status_badge = "\033[1;31m■ Paused\033[0m"
            else:
                status_badge = f"{theme['dim']}○ Standby\033[0m"

            spacing = " " * max(4, box_width - 16 - len(time_line) - 9)
            content_rows.append((f"      {time_line}{spacing}{status_badge}      ", "center"))

            # 4. Progress Bar
            if player.length > 0 and player.position >= 0:
                pct = max(0.0, min(1.0, player.position / player.length))
                knob_pos = max(0, min(viz_width - 1, int(pct * (viz_width - 1))))
                bar = (
                    f"{theme['prog_fill']}{'─' * knob_pos}\033[0m"
                    f"{theme['prog_knob']}"
                    f"{theme['prog_empty']}{'─' * (viz_width - 1 - knob_pos)}\033[0m"
                )
            else:
                mid = viz_width // 2
                bar = f"{theme['prog_empty']}{'─' * mid}●{'─' * (viz_width - 1 - mid)}\033[0m"
            content_rows.append((bar, "center"))
            content_rows.append(("", "center"))

            # 5. Visualizer
            viz_lines = generate_visualizer_panel(viz_mode, physics, viz_width, theme, player.is_playing, ticks)
            for vline in viz_lines:
                content_rows.append((vline, "center"))

            content_rows.append((f"{theme['border']}{'─' * viz_width}\033[0m", "center"))

            # 6. Volume Meter
            vol_pct = max(0, min(100, volume))
            vol_width = min(28, max(8, viz_width - 32))
            vol_filled = max(0, min(vol_width, int((vol_pct / 100) * vol_width)))
            vol_empty = vol_width - vol_filled

            if is_muted:
                vol_bar = f"\033[90m{'█' * vol_filled}{'░' * vol_empty}\033[0m"
                mute_str = " \033[1;31m[MUTED]\033[0m"
            else:
                vol_bar = f"{theme['vol_fill']}{'█' * vol_filled}\033[90m{'░' * vol_empty}\033[0m"
                mute_str = ""

            db_val = (vol_pct / 10.0) - 10.0 if vol_pct > 0 else -60.0
            content_rows.append((f"\033[1mVOL\033[0m  [{vol_bar}]  {vol_pct:3d}% ({db_val:+4.1f}dB){mute_str}", "center"))
            content_rows.append((f"{theme['dim']}EQ  60 170 310 600 1k 3k 6k 12k 14k 16k [Bypass: Flat]\033[0m", "center"))

            # 7. Telemetry & Queue
            src_disp = (player.player_name or "None").split('.')[0][:12]
            shuf_disp = f"{theme['accent']}On\033[0m" if player.shuffle else f"{theme['dim']}Off\033[0m"
            loop_disp = f"{theme['accent']}{player.loop_status}\033[0m" if player.loop_status != "None" else f"{theme['dim']}Off\033[0m"
            telemetry = (
                f"{theme['dim']}OUT Rate: 44.1kHz  │  Src: {src_disp}  │  "
                f"Shuffle: {shuf_disp}{theme['dim']}  │  Loop: {loop_disp}\033[0m"
            )
            content_rows.append((telemetry, "center"))
            content_rows.append((f"{theme['border']}{'─' * viz_width}\033[0m", "center"))

            if player.title:
                play_icon = "▶" if player.is_playing else "⏸"
                content_rows.append((f"{theme['accent']}{play_icon} 1. {clean_track}\033[0m", "left"))
            else:
                content_rows.append((f"{theme['dim']}1. (Queue Empty)\033[0m", "left"))

            content_rows.append(("", "center"))

            # 8. Interactive HUD Legends
            content_rows.append((f"{theme['dim']}[Spc]▶⏸  [<>]Trk  [↔/hl]Seek  [↑↓/jk/+-]Vol  [m]Mute  [s]Shuf  [r]Loop\033[0m", "center"))
            content_rows.append((f"{theme['dim']}[v]Visualizer  │  [t]Theme  │  [q]Quit\033[0m", "center"))

            # 9. Center & Double-Buffer Frame Render
            core_count = len(content_rows)
            v_pad = max(0, (H - 2) - core_count)
            top_pad = v_pad // 2
            bot_pad = v_pad - top_pad

            buffer = ["\033[H"]
            border_c = theme["border"]

            buffer.append(f"{border_c}┌{'─' * box_width}┐\033[0m\r\n")
            for _ in range(top_pad):
                buffer.append(format_row("", box_width, border_color=border_c))

            for text, align in content_rows:
                buffer.append(format_row(text, box_width, align=align, border_color=border_c))

            for _ in range(bot_pad):
                buffer.append(format_row("", box_width, border_color=border_c))

            buffer.append(f"{border_c}└{'─' * box_width}┘\033[0m")

            sys.stdout.write("".join(buffer))
            sys.stdout.flush()

            # 10. Universal Cross-Terminal Input Dispatcher
            key = get_key_non_blocking()
            if key:
                if key in (' ', '\r', '\n'):
                    player.toggle()
                elif key in ('RIGHT', 'l'):
                    player.seek(+5)
                elif key in ('LEFT', 'h'):
                    player.seek(-5)
                elif key in ('UP', '+', '=', 'k'):
                    audio.adjust(+5, active_player=player.active_player)
                elif key in ('DOWN', '-', '_', 'j'):
                    audio.adjust(-5, active_player=player.active_player)
                elif key in ('>', '.', ']', 'n', 'N'):
                    player.next()
                elif key in ('<', ',', '[', 'p', 'P'):
                    player.previous()
                elif key in ('m', 'M'):
                    audio.toggle_mute()
                elif key in ('s', 'S'):
                    player.toggle_shuffle()
                elif key in ('r', 'R'):
                    player.cycle_loop()
                elif key in ('v', 'V'):
                    viz_mode = (viz_mode + 1) % len(VIZ_NAMES)
                elif key in ('t', 'T'):
                    theme_idx = (theme_idx + 1) % len(THEMES)
                elif key in ('q', 'Q', 'ESC'):
                    break

            time.sleep(0.033)

    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    run_tuiamp()
