#!/usr/bin/env python3
"""
Universal Full-Screen Responsive Stopwatch TUI v2.0 [CHRONOAMP]
Optimized asynchronous chronograph with unbuffered POSIX fd key reading,
multi-palette theme engine, multi-mode visualizers, and lap telemetry.
"""

import sys
import os
import tty
import termios
import select
import shutil
import time
import math
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

def fmt_time_high_res(seconds: float) -> str:
    """Formats raw seconds into a precision HH:MM:SS.hh chronograph string."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    hundredths = int((seconds % 1) * 100)
    return f"{h:02d}:{m:02d}:{s:02d}.{hundredths:02d}"

def fmt_delta(delta: float) -> str:
    """Formats a signed lap difference (+00:01.23 or -00:00.45)."""
    sign = "+" if delta >= 0 else "-"
    delta = abs(delta)
    m = int((delta % 3600) // 60)
    s = int(delta % 60)
    hundredths = int((delta % 1) * 100)
    return f"{sign}{m:02d}:{s:02d}.{hundredths:02d}"

# -----------------------------------------------------------------------------
# Color Themes Palette Engine (Synced with TUIAMP)
# -----------------------------------------------------------------------------
THEMES = [
    {
        "name": "Cyberpunk Neon",
        "border": "\033[38;5;238m",
        "accent": "\033[1;38;5;226m",
        "clock": "\033[1;38;5;51m",
        "badge_run": "\033[1;38;5;226m",
        "prog_fill": "\033[38;5;51m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;201m●\033[0m",
        "viz_high": "\033[38;5;198m",
        "viz_mid": "\033[38;5;226m",
        "viz_low": "\033[38;5;51m",
        "dim": "\033[38;5;242m",
    },
    {
        "name": "Winamp Classic",
        "border": "\033[38;5;238m",
        "accent": "\033[1;38;5;46m",
        "clock": "\033[1;38;5;228m",
        "badge_run": "\033[1;38;5;46m",
        "prog_fill": "\033[38;5;46m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;226m●\033[0m",
        "viz_high": "\033[38;5;208m",
        "viz_mid": "\033[38;5;226m",
        "viz_low": "\033[38;5;46m",
        "dim": "\033[38;5;242m",
    },
    {
        "name": "Synthwave '84",
        "border": "\033[38;5;60m",
        "accent": "\033[1;38;5;207m",
        "clock": "\033[1;38;5;87m",
        "badge_run": "\033[1;38;5;87m",
        "prog_fill": "\033[38;5;205m",
        "prog_empty": "\033[38;5;237m",
        "prog_knob": "\033[1;38;5;87m●\033[0m",
        "viz_high": "\033[38;5;201m",
        "viz_mid": "\033[38;5;171m",
        "viz_low": "\033[38;5;45m",
        "dim": "\033[38;5;103m",
    },
    {
        "name": "Amber CRT",
        "border": "\033[38;5;94m",
        "accent": "\033[1;38;5;220m",
        "clock": "\033[1;38;5;214m",
        "badge_run": "\033[1;38;5;220m",
        "prog_fill": "\033[38;5;214m",
        "prog_empty": "\033[38;5;235m",
        "prog_knob": "\033[1;38;5;229m●\033[0m",
        "viz_high": "\033[38;5;220m",
        "viz_mid": "\033[38;5;214m",
        "viz_low": "\033[38;5;172m",
        "dim": "\033[38;5;136m",
    },
    {
        "name": "Dracula",
        "border": "\033[38;5;60m",
        "accent": "\033[1;38;5;141m",
        "clock": "\033[1;38;5;117m",
        "badge_run": "\033[1;38;5;84m",
        "prog_fill": "\033[38;5;141m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;212m●\033[0m",
        "viz_high": "\033[38;5;141m",
        "viz_mid": "\033[38;5;117m",
        "viz_low": "\033[38;5;84m",
        "dim": "\033[38;5;103m",
    },
    {
        "name": "Matrix Phosphor",
        "border": "\033[38;5;22m",
        "accent": "\033[1;38;5;120m",
        "clock": "\033[1;38;5;46m",
        "badge_run": "\033[1;38;5;154m",
        "prog_fill": "\033[38;5;46m",
        "prog_empty": "\033[38;5;234m",
        "prog_knob": "\033[1;38;5;231m●\033[0m",
        "viz_high": "\033[38;5;120m",
        "viz_mid": "\033[38;5;46m",
        "viz_low": "\033[38;5;28m",
        "dim": "\033[38;5;29m",
    },
    {
        "name": "Nord Frost",
        "border": "\033[38;5;238m",
        "accent": "\033[1;38;5;111m",
        "clock": "\033[1;38;5;123m",
        "badge_run": "\033[1;38;5;150m",
        "prog_fill": "\033[38;5;111m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;231m●\033[0m",
        "viz_high": "\033[38;5;111m",
        "viz_mid": "\033[38;5;109m",
        "viz_low": "\033[38;5;67m",
        "dim": "\033[38;5;244m",
    },
    {
        "name": "Tokyo Night",
        "border": "\033[38;5;60m",
        "accent": "\033[1;38;5;211m",
        "clock": "\033[1;38;5;111m",
        "badge_run": "\033[1;38;5;120m",
        "prog_fill": "\033[38;5;111m",
        "prog_empty": "\033[38;5;236m",
        "prog_knob": "\033[1;38;5;211m●\033[0m",
        "viz_high": "\033[38;5;176m",
        "viz_mid": "\033[38;5;111m",
        "viz_low": "\033[38;5;73m",
        "dim": "\033[38;5;103m",
    }
]

# -----------------------------------------------------------------------------
# Chrono Visualizer Engines
# -----------------------------------------------------------------------------
VIZ_NAMES = [
    "Analog Radar Sweep",
    "Chrono Metronome",
    "High-Res Braille Wave",
    "Linear Expansion Pulse",
    "Digital Matrix Stream"
]

def render_radar_sweep(is_running: bool, elapsed: float, cols: int, theme: dict) -> list:
    """Multi-line analog radar dial sweep with trailing phosphor decay."""
    lines = [[] for _ in range(3)]
    if not is_running:
        for r in range(3):
            lines[r] = f"{theme['dim']}{'·' * cols}\033[0m"
        return lines

    frac = (elapsed % 1.0)
    sweep_pos = int(frac * cols)
    
    trail_len = max(6, cols // 8)
    for r in range(3):
        row_chars = []
        for i in range(cols):
            dist = (sweep_pos - i) % cols
            if dist == 0:
                row_chars.append(f"{theme['accent']}█\033[0m")
            elif dist < trail_len:
                ratio = 1.0 - (dist / trail_len)
                if ratio > 0.66:
                    color = theme["viz_high"]
                    char = "▰" if r == 1 else "━"
                elif ratio > 0.33:
                    color = theme["viz_mid"]
                    char = "▱" if r == 1 else "─"
                else:
                    color = theme["viz_low"]
                    char = "·"
                row_chars.append(f"{color}{char}\033[0m")
            else:
                row_chars.append(f"{theme['dim']}·\033[0m")
        lines[r] = "".join(row_chars)
    return lines

def render_chrono_pendulum(is_running: bool, elapsed: float, cols: int, theme: dict) -> list:
    """Harmonic sine pendulum with bounce ticks and velocity vectors."""
    lines = [[] for _ in range(3)]
    track_width = max(10, cols - 8)
    side_pad = (cols - track_width) // 2
    rem_pad = cols - track_width - side_pad

    t = elapsed * math.pi * 1.5 if is_running else 0.0
    pos = int((math.sin(t) + 1.0) * 0.5 * (track_width - 1))

    for r in range(3):
        row = [" "] * track_width
        if r == 0:
            row[0], row[-1] = "┌", "┐"
            for i in range(1, track_width - 1):
                row[i] = "─" if i % 4 != 0 else "┬"
            if is_running:
                row[pos] = "▼"
        elif r == 1:
            row[0], row[-1] = "│", "│"
            for i in range(1, track_width - 1):
                row[i] = "·"
            if is_running:
                color = theme["viz_high"] if (pos <= 2 or pos >= track_width - 3) else theme["accent"]
                row[pos] = f"{color}●\033[0m"
            else:
                row[track_width // 2] = f"{theme['dim']}○\033[0m"
        else:
            row[0], row[-1] = "└", "┘"
            for i in range(1, track_width - 1):
                row[i] = "─" if i % 4 != 0 else "┴"
            if is_running:
                row[pos] = "▲"

        lines[r] = f"{' ' * side_pad}{''.join(row)}{' ' * rem_pad}"
    return lines

def render_braille_wave(is_running: bool, elapsed: float, cols: int, theme: dict) -> list:
    """High-density 8-dot Braille time-wave reacting to hundredths-of-a-second."""
    lines = [[] for _ in range(3)]
    t = elapsed * 8.0 if is_running else 0.0

    braille_levels = [" ", "⠤", "⠒", "⠉", "⠶", "⣶", "⣿"]

    for r in range(3):
        row_chars = []
        for i in range(cols):
            if is_running:
                norm_x = i / max(1, cols)
                wave1 = math.sin(t + i * 0.18) * 1.4
                wave2 = math.cos(t * 0.7 - i * 0.09) * 0.8
                total = 1.5 + wave1 + wave2

                thresh = 2.0 - r
                frac = total - thresh
                if frac >= 1.0:
                    char = "⣿"
                    color = theme["viz_high"] if r == 0 else theme["viz_mid"]
                elif frac > 0.6:
                    char = "⣶"
                    color = theme["viz_mid"]
                elif frac > 0.3:
                    char = "⠤"
                    color = theme["viz_low"]
                elif frac > 0.0:
                    char = "⠂"
                    color = theme["viz_low"]
                else:
                    char = " "
                    color = theme["dim"]
                row_chars.append(f"{color}{char}\033[0m")
            else:
                row_chars.append(f"{theme['dim']}·\033[0m" if r == 1 else " ")
        lines[r] = "".join(row_chars)
    return lines

def render_linear_pulse(is_running: bool, elapsed: float, cols: int, theme: dict) -> list:
    """Expanding harmonic center bar reacting to active run cadence."""
    lines = [[] for _ in range(3)]
    t = elapsed * 6.0 if is_running else 0.0
    max_w = max(4, cols - 12)
    w = int((math.sin(t) + 1.0) * 0.5 * (max_w - 4)) + 4 if is_running else cols // 3

    left = (cols - w) // 2
    right = cols - w - left

    for r in range(3):
        if r == 0:
            char = "─"
            color = theme["viz_low"]
        elif r == 1:
            char = "█" if is_running else "━"
            color = theme["accent"] if is_running else theme["dim"]
        else:
            char = "─"
            color = theme["viz_low"]

        lines[r] = f"{' ' * left}{color}{char * w}\033[0m{' ' * right}"
    return lines

def render_matrix_stream(is_running: bool, elapsed: float, cols: int, theme: dict) -> list:
    """Hex and digital chronograph stream with tick sweeps."""
    matrix_glyphs = "0123456789ABCDEFSEC"
    lines = [[] for _ in range(3)]
    tick_int = int(elapsed * 25) if is_running else 0

    for r in range(3):
        row_chars = []
        for i in range(cols):
            if is_running:
                idx = (tick_int + i * 3 + r * 7) % len(matrix_glyphs)
                ch = matrix_glyphs[idx]
                if (i + tick_int) % 11 == 0:
                    row_chars.append(f"{theme['accent']}{ch}\033[0m")
                elif (i + r) % 2 == 0:
                    row_chars.append(f"{theme['viz_low']}{ch}\033[0m")
                else:
                    row_chars.append(f"{theme['dim']}{ch}\033[0m")
            else:
                row_chars.append(f"{theme['dim']}:" if (i % 4 == 0) else " ")
        lines[r] = "".join(row_chars)
    return lines

def generate_visualizer_panel(mode: int, is_running: bool, elapsed: float, cols: int, theme: dict) -> list:
    if mode == 0:
        return render_radar_sweep(is_running, elapsed, cols, theme)
    elif mode == 1:
        return render_chrono_pendulum(is_running, elapsed, cols, theme)
    elif mode == 2:
        return render_braille_wave(is_running, elapsed, cols, theme)
    elif mode == 3:
        return render_linear_pulse(is_running, elapsed, cols, theme)
    else:
        return render_matrix_stream(is_running, elapsed, cols, theme)

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

    if raw_bytes[0] == 0x1B:
        if len(raw_bytes) == 1:
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
def run_stopwatch_tui():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    # Alternate screen buffer and hide cursor
    sys.stdout.write("\033[?1049h\033[?25l\033[H\033[J")
    sys.stdout.flush()

    def cleanup(*_):
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?1049l\033[?25h")
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    is_running = False
    start_time = 0.0
    elapsed_paused = 0.0
    laps = []

    theme_idx = 0
    viz_mode = 0
    last_w, last_h = 0, 0

    try:
        tty.setraw(fd)

        while True:
            theme = THEMES[theme_idx]

            # True continuous high-resolution timer
            now = time.time()
            if is_running:
                current_elapsed = (now - start_time) + elapsed_paused
            else:
                current_elapsed = elapsed_paused

            W, H = shutil.get_terminal_size()
            if W != last_w or H != last_h:
                sys.stdout.write("\033[H\033[J")
                last_w, last_h = W, H

            if H < 21 or W < 54:
                sys.stdout.write("\033[H\033[J")
                sys.stdout.write(" Terminal window too small for CHRONOAMP display (min 54x21).\r\n")
                sys.stdout.write(" Please expand your terminal window.\r\n")
                sys.stdout.flush()
                time.sleep(0.1)
                continue

            box_width = W - 2
            viz_width = W - 8

            content_rows = []

            # 1. Header Row
            header = (
                f"{theme['accent']}▶ C H R O N O G R A P H\033[0m {theme['dim']}──\033[0m "
                f"\033[1mTHEME:\033[0m {theme['name']} {theme['dim']}──\033[0m "
                f"\033[1mVIZ:\033[0m {VIZ_NAMES[viz_mode]}"
            )
            content_rows.append((header, "center"))
            content_rows.append(("", "center"))

            # 2. Status Badge
            if is_running:
                status_badge = f"{theme['badge_run']}▶ RUNNING\033[0m"
            elif current_elapsed > 0:
                status_badge = "\033[1;33m■ PAUSED\033[0m"
            else:
                status_badge = f"{theme['dim']}○ READY\033[0m"
            content_rows.append((f"[ {status_badge} ]", "center"))

            # 3. Large High-Res Clock Face Display
            time_display = fmt_time_high_res(current_elapsed)
            clock_banner = f"{theme['clock']}┏━ {time_display} ━┓\033[0m"
            content_rows.append((clock_banner, "center"))
            content_rows.append(("", "center"))

            # 4. Spaced HUD Soft-buttons
            if is_running:
                btn_left = f"{theme['accent']}[L] LAP\033[0m"
                btn_right = "\033[1;31m[SPACE] STOP\033[0m"
            elif current_elapsed > 0:
                btn_left = "\033[1;33m[R] RESET\033[0m"
                btn_right = f"{theme['badge_run']}[SPACE] START\033[0m"
            else:
                btn_left = f"{theme['dim']}[L] LAP\033[0m"
                btn_right = f"{theme['badge_run']}[SPACE] START\033[0m"

            spacing = " " * max(6, box_width - 16 - str_display_width(btn_left) - str_display_width(btn_right))
            btn_colored = f"      {btn_left}{spacing}{btn_right}      "
            content_rows.append((btn_colored, "center"))
            content_rows.append(("", "center"))

            # 5. Multi-line Visualizer Block (3 rows)
            viz_lines = generate_visualizer_panel(viz_mode, is_running, current_elapsed, viz_width, theme)
            for vl in viz_lines:
                content_rows.append((vl, "center"))

            # 6. Seconds Loop Progress Track (Circular minute-bar)
            current_sec_pct = (current_elapsed % 60) / 60.0
            knob_idx = max(0, min(viz_width - 1, int(current_sec_pct * (viz_width - 1))))
            prog_bar = (
                f"{theme['prog_fill']}{'─' * knob_idx}\033[0m"
                f"{theme['prog_knob']}"
                f"{theme['prog_empty']}{'─' * (viz_width - 1 - knob_idx)}\033[0m"
            )
            content_rows.append((prog_bar, "center"))
            content_rows.append((f"{theme['border']}{'─' * viz_width}\033[0m", "center"))

            # 7. Lap Telemetry & Current Lap Tracker
            if not laps:
                cur_lap_dur = current_elapsed
            else:
                cur_lap_dur = current_elapsed - laps[-1]["split_time"]
            cur_lap_str = fmt_time_high_res(cur_lap_dur)

            # Lap statistics
            best_lap_dur = None
            avg_lap_dur = None
            delta_str = ""
            if laps:
                durations = [l["lap_time"] for l in laps]
                best_lap_dur = min(durations)
                avg_lap_dur = sum(durations) / len(durations)
                diff = cur_lap_dur - best_lap_dur
                delta_str = f" ({fmt_delta(diff)})"

            lap_stat_line = (
                f"\033[1mCURRENT LAP:\033[0m {theme['accent']}{cur_lap_str}{delta_str}\033[0m"
            )
            content_rows.append((lap_stat_line, "center"))

            best_str = fmt_time_high_res(best_lap_dur) if best_lap_dur is not None else "--:--:--.--"
            avg_str = fmt_time_high_res(avg_lap_dur) if avg_lap_dur is not None else "--:--:--.--"
            telemetry_line = (
                f"{theme['dim']}TOTAL LAPS: {len(laps):02d}  │  "
                f"BEST: {best_str}  │  AVG: {avg_str}\033[0m"
            )
            content_rows.append((telemetry_line, "center"))
            content_rows.append((f"{theme['border']}{'─' * viz_width}\033[0m", "center"))

            # 8. Lap History Header & Table (Last 3 Laps)
            best_idx = -1
            worst_idx = -1
            if len(laps) >= 2:
                durations = [l["lap_time"] for l in laps]
                min_d = min(durations)
                max_d = max(durations)
                if min_d != max_d:
                    best_idx = durations.index(min_d)
                    worst_idx = durations.index(max_d)

            lap_rows = []
            if not laps:
                lap_rows.append((f"{theme['dim']}(No Laps Recorded)\033[0m", "center"))
            else:
                for idx, lap in list(enumerate(laps))[-3:][::-1]:
                    l_num = lap["lap_num"]
                    l_fmt = fmt_time_high_res(lap["lap_time"])
                    s_fmt = fmt_time_high_res(lap["split_time"])

                    if idx == best_idx:
                        tag_color = "\033[1;32m"
                        tag = " [FASTEST]"
                    elif idx == worst_idx:
                        tag_color = "\033[1;31m"
                        tag = " [SLOWEST]"
                    else:
                        tag_color = theme["accent"]
                        tag = "          "

                    marker = f"{theme['accent']}▶\033[0m" if idx == len(laps) - 1 else " "
                    row_str = (
                        f"{marker} Lap {l_num:02d}: {tag_color}{l_fmt}\033[0m{tag} "
                        f"{theme['dim']}(Split: {s_fmt})\033[0m"
                    )
                    lap_rows.append((row_str, "left"))

            # Fill missing rows for static layout budget
            while len(lap_rows) < 3:
                lap_rows.append(("", "center"))

            for row_content, align in lap_rows:
                content_rows.append((row_content, align))

            content_rows.append((f"{theme['border']}{'─' * viz_width}\033[0m", "center"))

            # 9. Interactive HUD Legends
            legend1 = (
                f"{theme['dim']}[Spc/Enter]Start/Stop  [l]Lap  [r]Reset  "
                f"[v]Visualizer  [t]Theme  [q/Esc]Quit\033[0m"
            )
            content_rows.append((legend1, "center"))

            # 10. Frame Layout Centering & Double Buffering
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

            # 11. Keystroke Dispatcher
            key = get_key_non_blocking()
            if key:
                if key in (' ', '\r', '\n'):
                    if is_running:
                        elapsed_paused += time.time() - start_time
                        is_running = False
                    else:
                        start_time = time.time()
                        is_running = True
                elif key in ('l', 'L'):
                    if is_running:
                        tot = (time.time() - start_time) + elapsed_paused
                        last_s = laps[-1]["split_time"] if laps else 0.0
                        lap_dur = tot - last_s
                        laps.append({
                            "lap_num": len(laps) + 1,
                            "lap_time": lap_dur,
                            "split_time": tot
                        })
                elif key in ('r', 'R'):
                    if not is_running:
                        start_time = 0.0
                        elapsed_paused = 0.0
                        laps = []
                elif key in ('v', 'V'):
                    viz_mode = (viz_mode + 1) % len(VIZ_NAMES)
                elif key in ('t', 'T'):
                    theme_idx = (theme_idx + 1) % len(THEMES)
                elif key in ('q', 'Q', 'ESC'):
                    break

            time.sleep(0.025)  # ~40 FPS high-precision chronograph refresh

    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    run_stopwatch_tui()
