#!/usr/bin/env python3
# Universal Full-Screen Responsive Media Player TUI v1.1.1 [TUIAMP]

import math
import random
import re
import select
import shutil
import subprocess
import sys
import termios
import time
import tty

# Strips ANSI escape sequences to compute visual plain-text width
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text):
    """Returns the text with all colored ANSI codes stripped out."""
    return ANSI_ESCAPE.sub("", text)


# Global state to mimic falling peak decay
NUM_BANDS = 30
current_heights = [0.0] * 128
peak_heights = [0.0] * 128

locked_player = None


def get_key_non_blocking():
    """Checks stdin for a keypress while terminal is in raw mode."""
    rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
    if rlist:
        ch = sys.stdin.read(1)
        if ch == "\033":
            rlist, _, _ = select.select([sys.stdin], [], [], 0.01)
            if rlist:
                ch += sys.stdin.read(2)
        return ch
    return None


def get_prioritized_player():
    """Finds all system players and prioritizes: Brave/Chromium -> Firefox -> Others."""
    global locked_player
    try:
        result = subprocess.run(
            ["playerctl", "-l"], capture_output=True, text=True, check=True
        )
        players = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
    except subprocess.CalledProcessError:
        return None

    if not players:
        locked_player = None
        return None

    if locked_player and locked_player in players:
        return locked_player

    chromium_tier, firefox_tier, other_tier = [], [], []
    for p in players:
        p_low = p.lower()
        if "brave" in p_low or "chromium" in p_low:
            chromium_tier.append(p)
        elif "firefox" in p_low:
            firefox_tier.append(p)
        else:
            other_tier.append(p)

    sorted_players = chromium_tier + firefox_tier + other_tier

    for player in sorted_players:
        try:
            status = subprocess.run(
                ["playerctl", f"--player={player}", "status"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            if status == "Playing":
                locked_player = player
                return player
        except Exception:
            pass

    if sorted_players:
        locked_player = sorted_players[0]
        return sorted_players[0]

    return None


def run_pctl_for_player(player, args):
    """Safely runs playerctl metadata queries."""
    try:
        result = subprocess.run(
            ["playerctl", f"--player={player}"] + args,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def trigger_robust_toggle(player):
    """Failsafe play/pause logic using hardware keys to keep Spotify active."""
    if not player:
        return
    title = run_pctl_for_player(player, ["metadata", "title"]).lower()
    if "spotify" in player.lower() or "spotify" in title:
        if shutil.which("xdotool"):
            subprocess.run(
                ["xdotool", "key", "XF86AudioPlay"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    subprocess.run(
        ["playerctl", f"--player={player}", "play-pause"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_system_volume():
    """Queries true system master volume using wpctl (preferred for PipeWire) or pactl fallback."""
    # Method A: Try wpctl (Native PipeWire/WirePlumber)
    if shutil.which("wpctl"):
        try:
            res = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                val_str = res.stdout.replace("Volume:", "").split()[0]
                return int(float(val_str) * 100)
        except Exception:
            pass

    # Method B: Fallback to pactl if wpctl errors out
    if shutil.which("pactl"):
        try:
            res = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0 and "Volume:" in res.stdout:
                parts = res.stdout.split()
                for p in parts:
                    if "%" in p:
                        return int(p.replace("%", ""))
        except Exception:
            pass

    # Method C: Ultimate player fallback
    global locked_player
    if locked_player:
        try:
            vol_str = run_pctl_for_player(locked_player, ["volume"])
            return int(float(vol_str) * 100) if vol_str else 100
        except Exception:
            pass

    return 100


def adjust_system_volume(direction="up"):
    """Adjusts hardware master slider using native wpctl steps or pactl alternate parsing."""
    wp_delta = "0.05+" if direction == "up" else "0.05-"
    pa_delta = "+5%" if direction == "up" else "-5%"

    if shutil.which("wpctl"):
        subprocess.run(
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", wp_delta],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    if shutil.which("pactl"):
        subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", pa_delta],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    global locked_player
    if locked_player:
        pctl_delta = "0.05+" if direction == "up" else "0.05-"
        subprocess.run(
            ["playerctl", f"--player={locked_player}", "volume", pctl_delta],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def fmt_time(microseconds_or_seconds, is_micro=False):
    """Converts raw timestamps into clean MM:SS format strings."""
    try:
        total_seconds = float(microseconds_or_seconds)
        if is_micro:
            total_seconds /= 1_000_000
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError):
        return "00:00"


def generate_cliamp_spectrogram(is_playing, ticks, cols):
    """Generates a multi-line high-density Braille spectrogram mirroring Winamp."""
    lines = [[] for _ in range(4)]
    if not is_playing:
        # Stationary baseline in standby mode (eliminates idle visualizer length drift)
        for L in range(4):
            line_chars = []
            for i in range(cols):
                line_chars.append("⠂" if i % 4 == 0 else " ")
            lines[L] = f"\033[90m{''.join(line_chars)}\033[0m"
        return lines

    # Active running state simulated spectrum frequencies
    for L in range(4):
        line_chars = []
        for i in range(cols):
            pos = i / max(1, cols)
            # Simulated spectrum: high energy bass (left), high frequency noise (right)
            bass_wave = math.sin(ticks * 0.15 + i * 0.12) * 3.2 * (1.0 - pos)
            treble_wave = (
                math.sin(ticks * 0.45 - i * 0.28) * 1.6 * pos * random.uniform(0.4, 1.6)
            )
            noise = random.uniform(-0.6, 0.6)

            amp = 4.0 + bass_wave + treble_wave + noise
            threshold = (3 - L) * 2.0

            if amp > threshold:
                diff = amp - threshold
                if diff > 1.6:
                    char = random.choice(["⠶", "⠦", "⠧", "⠷", "⠾", "⠽", "⠿"])
                else:
                    char = random.choice(["⠂", "⠁", "⠃", "⠆", "⠇", "⠦"])
            else:
                char = " "

            # Gradient mapping
            if L == 0:
                color = "\033[38;5;198m"  # Top: Neon Pink
            elif L == 1:
                color = "\033[38;5;209m"  # Mid-Top: Coral
            elif L == 2:
                color = "\033[38;5;118m"  # Mid-Bottom: Yellow-Green
            else:
                color = "\033[38;5;34m"  # Bottom: Green

            if char != " ":
                line_chars.append(f"{color}{char}\033[0m")
            else:
                line_chars.append(" ")
        lines[L] = "".join(line_chars)
    return lines


def generate_dynamic_cava(is_playing, ticks, style_mode, cols):
    """Generates the single-line backup visualizers with dynamic column bounds."""
    if cols < 10:
        return ""

    if not is_playing:
        idle_chars = "⠂⠁⠂⠁⠤"
        repeated = (idle_chars * (cols // len(idle_chars) + 1))[:cols]
        return f"\033[90m{repeated}\033[0m"

    standard_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    dense_blocks = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
    peak_markers = [" ", " ", "⠂", "⠃", "⠆", "⠇", "⠦", "⠧", "⠷"]

    # --- Mode 0: Official GitHub vis_wave.go (Discrete Outline Wave) ---
    if style_mode == 0:
        t = ticks * 0.4
        visualizer_line = []
        for i in range(cols):
            wave = math.sin(t + i * 0.3) * math.cos(t * 0.4) * 3.5
            h_idx = int(max(0, min(len(peak_markers) - 1, 4 + wave)))
            char = peak_markers[h_idx] if h_idx > 1 else "⠂"
            if h_idx > 6:
                visualizer_line.append(f"\033[38;5;209m{char}\033[0m")
            elif h_idx > 3:
                visualizer_line.append(f"\033[38;5;110m{char}\033[0m")
            else:
                visualizer_line.append(f"\033[32m{char}\033[0m")
        return "".join(visualizer_line)

    # --- Mode 2: Official GitHub vis_block.go (Dense Solid Wall) ---
    elif style_mode == 2:
        t = ticks * 0.35
        visualizer_line = []
        for i in range(cols):
            wave1 = math.sin(t + i * 0.2) * 3.0
            wave2 = math.cos(t * 0.5 - i * 0.1) * 2.0
            h_idx = int(max(0, min(len(dense_blocks) - 1, 4 + wave1 + wave2)))
            if h_idx > 6:
                visualizer_line.append(f"\033[38;5;209m{dense_blocks[h_idx]}\033[0m")
            elif h_idx > 3:
                visualizer_line.append(f"\033[38;5;110m{dense_blocks[h_idx]}\033[0m")
            else:
                visualizer_line.append(f"\033[32m{dense_blocks[h_idx]}\033[0m")
        return "".join(visualizer_line)

    # --- Mode 3: Custom Smooth Sine Wave ---
    elif style_mode == 3:
        t = ticks * 0.35
        visualizer_line = []
        for i in range(cols):
            wave1 = math.sin(t + i * 0.25) * 3.5
            wave2 = math.cos(t * 0.6 - i * 0.15) * 2.5
            noise = random.uniform(-0.6, 0.6)
            h_idx = int(
                max(0, min(len(standard_blocks) - 1, 4 + wave1 + wave2 + noise))
            )
            if h_idx > 6:
                visualizer_line.append(f"\033[38;5;209m{standard_blocks[h_idx]}\033[0m")
            elif h_idx > 3:
                visualizer_line.append(f"\033[38;5;110m{standard_blocks[h_idx]}\033[0m")
            else:
                visualizer_line.append(f"\033[32m{standard_blocks[h_idx]}\033[0m")
        return "".join(visualizer_line)

    # --- Mode 4: Geometric Pinnacle Peaks ---
    elif style_mode == 4:
        peaks = [" ", " ", "░", "▒", "▓", "█", "▕", "▎", "▲"]
        t = ticks * 0.35
        visualizer_line = []
        for i in range(cols):
            wave = math.sin(t + i * 0.4) * math.cos(t * 0.5) * 4.0
            h_idx = int(max(0, min(len(peaks) - 1, 4 + wave)))
            if h_idx > 6:
                visualizer_line.append(f"\033[38;5;209m{peaks[h_idx]}\033[0m")
            elif h_idx > 3:
                visualizer_line.append(f"\033[38;5;110m{peaks[h_idx]}\033[0m")
            else:
                visualizer_line.append(f"\033[32m{peaks[h_idx]}\033[0m")
        return "".join(visualizer_line)

    # --- Mode 5: Stereo Mirror (Symmetric Wave) ---
    elif style_mode == 5:
        t = ticks * 0.4
        half = cols // 2
        line = [" "] * cols
        for i in range(half):
            wave = (
                math.sin(t + i * 0.2)
                * math.cos(t * 0.3)
                * 4.0
                * (1.0 - i / max(1, half))
            )
            h_idx = int(max(0, min(len(peak_markers) - 1, 4 + wave)))
            char = peak_markers[h_idx] if h_idx > 1 else "⠂"
            l_idx = half - 1 - i
            r_idx = half + i
            color = (
                "\033[38;5;209m"
                if h_idx > 6
                else ("\033[38;5;110m" if h_idx > 3 else "\033[32m")
            )
            if l_idx >= 0:
                line[l_idx] = f"{color}{char}\033[0m"
            if r_idx < cols:
                line[r_idx] = f"{color}{char}\033[0m"
        return "".join(line)

    # --- Mode 6: Neon Matrix (Cyberpunk LED Blocks) ---
    elif style_mode == 6:
        t = ticks * 0.5
        line = []
        for i in range(cols):
            wave = (math.sin(t + i * 0.1) + 1.0) * 0.5 * 8.0
            h_idx = int(max(0, min(len(dense_blocks) - 1, wave)))
            char = dense_blocks[h_idx]
            color = (
                "\033[38;5;198m"
                if h_idx > 6
                else ("\033[38;5;51m" if h_idx > 3 else "\033[38;5;93m")
            )
            line.append(f"{color}{char}\033[0m")
        return "".join(line)

    # --- Mode 7: Pulse Oscilloscope (Neon Green Sweep) ---
    else:
        t = ticks * 0.6
        line = []
        for i in range(cols):
            wave = math.sin(t + i * 0.08) * math.sin(t * 0.3 + i * 0.2) * 3.5
            h_idx = int(max(0, min(len(standard_blocks) - 1, 4 + wave)))
            char = [" ", "⠤", "⠂", "⠃", "⠆", "⠇", "⠦", "⠧", "█"][h_idx]
            color = (
                "\033[38;5;46m"
                if h_idx > 6
                else ("\033[38;5;118m" if h_idx > 3 else "\033[38;5;28m")
            )
            line.append(f"{color}{char}\033[0m")
        return "".join(line)


def generate_visualizer_panel(is_playing, ticks, style_mode, cols):
    """Generates a 4-line visualizer block to guarantee static layout heights."""
    # Theme 1: Winamp Multi-Line Braille Spectrogram
    if style_mode == 1:
        return generate_cliamp_spectrogram(is_playing, ticks, cols)

    # Other single-line visualizers: pad the upper rows cleanly
    lines = [""] * 4
    lines[3] = generate_dynamic_cava(is_playing, ticks, style_mode, cols)
    return lines


def draw_row_raw(colored_text, width, align="center"):
    """Pads and draws a single row cleanly encased within the vertical borders."""
    plain_len = len(strip_ansi(colored_text))
    pad = width - plain_len
    pad = max(pad, 0)
    if align == "center":
        left = pad // 2
        right = pad - left
        content = " " * left + colored_text + " " * right
    elif align == "left":
        content = " " * 4 + colored_text + " " * (pad - 4)
    else:  # right
        content = " " * (pad - 4) + colored_text + " " * 4
    sys.stdout.write(f"\033[90m│\033[0m{content}\033[90m│\033[0m\r\n")


def run_media_control():
    """TUI loop rendering metadata frames dynamically sized to full-screen limits."""
    if not shutil.which("playerctl"):
        print("\033[1;31mError: 'playerctl' is required.\033[0m")
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    # Initialize terminal state
    sys.stdout.write("\033[?25l\033[H\033[J")
    sys.stdout.flush()

    last_mpris_check = 0.0
    ticks = 0
    visualizer_mode = (
        1  # Standardize default visualizer to the retro 4-line Spectrometer
    )

    title, artist, status, pos_str, len_str = "", "", "", "", ""
    active_player = None
    is_playing = False

    last_W, last_H = 0, 0

    mode_names = {
        0: "Official Wave",
        1: "Official Bars",
        2: "Official Block",
        3: "Smooth Sine",
        4: "Pinnacle Peaks",
        5: "Stereo Mirror",
        6: "Neon Matrix",
        7: "Pulse Oscilloscope",
    }

    try:
        tty.setraw(fd)

        while True:
            current_timestamp = time.time()
            ticks += 1

            # Query active MPRIS player variables
            if current_timestamp - last_mpris_check > 0.2:
                active_player = get_prioritized_player()
                if active_player:
                    title = run_pctl_for_player(active_player, ["metadata", "title"])
                    artist = run_pctl_for_player(active_player, ["metadata", "artist"])
                    status = run_pctl_for_player(active_player, ["status"])
                    pos_str = run_pctl_for_player(active_player, ["position"])
                    len_str = run_pctl_for_player(
                        active_player, ["metadata", "mpris:length"]
                    )
                    is_playing = status == "Playing"
                else:
                    title = ""
                last_mpris_check = current_timestamp

            # Query live terminal dimensions
            W, H = shutil.get_terminal_size()

            if W != last_W or H != last_H:
                sys.stdout.write("\033[H\033[J")
                last_W, last_H = W, H
            else:
                sys.stdout.write("\033[H")

            # Fallback block for tight terminals
            if H < 18 or W < 50:
                sys.stdout.write("\033[H\033[J")
                sys.stdout.write(
                    " Terminal window too small for full-screen display.\r\n"
                )
                sys.stdout.write(" Please expand your terminal.\r\n")
                sys.stdout.flush()
                time.sleep(0.1)
                continue

            box_width = W - 2
            viz_width = W - 8

            # -------------------------------------------------------------
            # Assemble Core Content Rows (Locked to exact line budget)
            # -------------------------------------------------------------
            content_rows = []

            # 1. Main Header
            header_colored = f"\033[1;32m T U I A M P \033[0m\033[90m ── \033[0m\033[1mTHEME:\033[0m {mode_names[visualizer_mode]}"
            content_rows.append((header_colored, "center"))

            # 2. Blank
            content_rows.append(("", "center"))

            if active_player and title:
                # 3. Dynamic Track Metadata Centering & Safe Truncation
                full_track = f"{artist} - {title}" if artist else title
                for word in [" - YouTube Music", " - YouTube", " - Spotify"]:
                    full_track = full_track.split(word)[0]

                # Max safe bounds inside borders
                max_meta_len = max(20, W - 16)
                if len(full_track) > max_meta_len:
                    clean_track = f"{full_track[: max_meta_len - 3]}..."
                else:
                    clean_track = full_track

                content_rows.append((f"♫ \033[38;5;209m{clean_track}\033[0m", "center"))

                # 4. Playback Badges & Timer Progress Tracker
                is_micro = False
                if len_str:
                    try:
                        is_micro = float(len_str) > 10000000
                    except ValueError:
                        pass

                time_current = fmt_time(pos_str, is_micro=False)
                if pos_str and is_micro:
                    time_current = (
                        fmt_time(float(pos_str) * 1000000, is_micro=True)
                        if "." in pos_str
                        else fmt_time(pos_str, is_micro=True)
                    )

                time_total = (
                    fmt_time(len_str, is_micro=is_micro) if len_str else "00:00"
                )
                time_line = f"{time_current} / {time_total}"
                status_badge = (
                    "\033[1;38;5;118m▶ Playing\033[0m"
                    if is_playing
                    else "\033[1;31m■ Paused\033[0m"
                )

                # Spaced out HUD timer line mimicking retro UI
                avail_meta_space = box_width - 12 - len(time_line) - 9
                spacing = " " * max(2, avail_meta_space)
                hud_line = f"      {time_line}{spacing}{status_badge}      "
                content_rows.append((hud_line, "center"))

                # 5. Scaled Progress Bar Track (With clean marker ●)
                progress_bar = "─" * viz_width
                if pos_str and len_str:
                    try:
                        p_val = float(pos_str)
                        l_val = float(len_str)
                        if is_micro:
                            l_val /= 1_000_000
                        pct = p_val / l_val if l_val > 0 else 0
                        filled = max(0, min(viz_width - 1, int(pct * viz_width)))
                        progress_bar = f"\033[90m{'─' * filled}\033[0m\033[38;5;209m●\033[0m\033[90m{'─' * (viz_width - 1 - filled)}\033[0m"
                    except Exception:
                        pass
                content_rows.append((progress_bar, "center"))

                # 6. Blank
                content_rows.append(("", "center"))

                # 7-10. Static 4-Line Spectrogram Panel Block (Prevents jump artifacts)
                viz_panel_lines = generate_visualizer_panel(
                    is_playing, ticks, visualizer_mode, viz_width
                )
                for line in viz_panel_lines:
                    content_rows.append((line, "center"))

                # 11. Divider
                content_rows.append((f"\033[90m{'─' * viz_width}\033[0m", "center"))

                # 12. Dynamic Volume Block HUD & Equalizer Frame
                vol_pct = get_system_volume()
                vol_pct = max(0, min(100, vol_pct))
                vol_bar_width = 30
                filled_vol = max(
                    0, min(vol_bar_width, int((vol_pct / 100) * vol_bar_width))
                )
                vol_bar = f"\033[38;5;118m{'█' * filled_vol}\033[0m\033[90m{'█' * (vol_bar_width - filled_vol)}\033[0m"
                vol_line = f"\033[1mVOL\033[0m  [{vol_bar}]  +{vol_pct / 10:.1f}dB"
                content_rows.append((vol_line, "center"))

                # 13. Retro Equalizer Banner
                content_rows.append(
                    (
                        "\033[90mEQ  70 180 320 600 1k 3k 6k 12k 14k 16k [Flat]\033[0m",
                        "center",
                    )
                )

                # 14. Output Telemetry Line
                src_display = active_player.split(".")[0][:12]
                meta_footer = f"\033[90mOUT Rate 44.1kHz  │  Resample 4/4  │  Src: {src_display}\033[0m"
                content_rows.append((meta_footer, "center"))

            else:
                # Standby Screen Block (Fills exact core rows layout limits)
                clean_track = "(Empty)"
                content_rows.append(("\033[90m♫ Idle\033[0m", "center"))
                content_rows.append(("\033[90m00:00 / 00:00\033[0m", "center"))
                content_rows.append(
                    (
                        "\033[90m─●──────────────────────────────────────────────────────────\033[0m",
                        "center",
                    )
                )
                content_rows.append(("", "center"))
                for line in generate_visualizer_panel(False, 0, 1, viz_width):
                    content_rows.append((line, "center"))
                content_rows.append((f"\033[90m{'─' * viz_width}\033[0m", "center"))
                content_rows.append(
                    (
                        "\033[90mVOL  [██████████████████████████████]  +0.0dB\033[0m",
                        "center",
                    )
                )
                content_rows.append(
                    (
                        "\033[90mEQ  70 180 320 600 1k 3k 6k 12k 14k 16k [Flat]\033[0m",
                        "center",
                    )
                )
                content_rows.append(
                    (
                        "\033[90m[ No active system media player detected ]\033[0m",
                        "center",
                    )
                )

            # 15. Playlist Divider
            content_rows.append((f"\033[90m{'─' * viz_width}\033[0m", "center"))
            content_rows.append(("── Playlist ── [Shuffle] [Repeat: Off] ──", "center"))

            # 16. Active Queue Selector
            if active_player and title:
                content_rows.append((f"\033[32m▶ 1. {clean_track}\033[0m", "left"))
            else:
                content_rows.append(("\033[90m1. (Empty Queue)\033[0m", "left"))

            # 17. Spacer Row
            content_rows.append(("", "center"))

            # 18. Legend HUD Keys
            legend = "\033[90m[Spc]▶⏸  [<>]Trk  [↔]Seek  [+-]Vol  [/]Search  [a]Queue  [Tab]Focus\033[0m"
            content_rows.append((legend, "center"))

            # 19. Second Legend Option Block
            content_rows.append(
                ("\033[90m[v]Theme  │  [q]Quit tuiamp\033[0m", "center")
            )

            # -------------------------------------------------------------
            # Render Bounding Box and Padding (Dynamic Centering Calculation)
            # -------------------------------------------------------------
            core_row_count = len(content_rows)
            vertical_padding = (H - 2) - core_row_count
            top_padding = max(0, vertical_padding // 2)
            bottom_padding = max(0, vertical_padding - top_padding)

            # Draw Top Border Frame
            sys.stdout.write(f"\033[90m┌{'─' * box_width}┐\033[0m\r\n")

            # Draw Upper Spacing Border Lines
            for _ in range(top_padding):
                draw_row_raw("", box_width)

            # Draw Main Centered Content Block
            for colored_text, alignment in content_rows:
                draw_row_raw(colored_text, box_width, align=alignment)

            # Draw Lower Spacing Border Lines
            for _ in range(bottom_padding):
                draw_row_raw("", box_width)

            # Draw Bottom Border Frame
            sys.stdout.write(f"\033[90m└{'─' * box_width}┘\033[0m")
            sys.stdout.flush()

            # Handle keystroke inputs
            key = get_key_non_blocking()
            if key:
                if key == " " or key == "\r":
                    trigger_robust_toggle(active_player)
                elif key.lower() == "v":
                    visualizer_mode = (visualizer_mode + 1) % 8
                elif key == "+" or key == "=":
                    adjust_system_volume("up")
                elif key == "-":
                    adjust_system_volume("down")
                elif active_player:
                    if key.lower() == "n" or key == "\033[C":
                        subprocess.run(
                            ["playerctl", f"--player={active_player}", "next"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    elif key.lower() == "p" or key == "\033[D":
                        subprocess.run(
                            ["playerctl", f"--player={active_player}", "previous"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    elif key.lower() == "q":
                        break
                elif key.lower() == "q":
                    break

            time.sleep(0.04)

    except KeyboardInterrupt:
        pass
    finally:
        # Restore terminal settings and show cursor again
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\033[H\033[J")
        sys.stdout.flush()


if __name__ == "__main__":
    run_media_control()
