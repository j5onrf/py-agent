#!/usr/bin/env python3
# Universal Full-Screen Responsive Stopwatch TUI v1.4.1

import math
import re
import select
import shutil
import sys
import termios
import time
import tty

# Regex pattern matching standard ANSI SGR escape sequences
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text):
    """Returns the text with all colored ANSI codes stripped out."""
    return ANSI_ESCAPE.sub('', text)

def get_key_non_blocking():
    """Checks stdin for a keypress while terminal is in raw mode."""
    rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
    if rlist:
        ch = sys.stdin.read(1)
        if ch == '\033': 
            rlist, _, _ = select.select([sys.stdin], [], [], 0.01)
            if rlist:
                ch += sys.stdin.read(2)
        return ch
    return None

def fmt_time_high_res(seconds):
    """Formats raw seconds into a highly precise HH:MM:SS.hh string."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    hundredths = int((seconds % 1) * 100)
    return f"{h:02d}:{m:02d}:{s:02d}.{hundredths:02d}"

def get_elapsed(is_running, start_time, elapsed_paused):
    """Calculates true elapsed time accounting for active running state."""
    if is_running:
        return (time.time() - start_time) + elapsed_paused
    return elapsed_paused

def generate_visualizer(is_running, ticks, style_mode, current_elapsed, cols):
    """Generates reactive chronograph visualizers scaled dynamically to terminal width."""
    if cols < 10:
        return ""

    # --- Mode 0: Linear Pulse (Default - Expanding Center Bar) ---
    if style_mode == 0:
        t = current_elapsed * 6.0 if is_running else 0.0
        max_expand = cols - 12
        width = int((math.sin(t) + 1.0) * 0.5 * (max_expand - 4)) + 5
        side = (cols - width) // 2
        bar_content = "━" * width
        color = "\033[38;5;110m" if is_running else "\033[90m"
        return f"{' ' * side}{color}{bar_content}\033[0m{' ' * (cols - width - side)}"

    # --- Mode 1: Sweep Oscilloscope (Analog Sweep Hand) ---
    elif style_mode == 1:
        frac = (current_elapsed % 1.0)
        sweep_pos = int(frac * cols)
        line = []
        for i in range(cols):
            if i == sweep_pos:
                line.append("\033[1;32m█\033[0m" if is_running else "\033[90m█\033[0m")
            elif (sweep_pos - i) % cols < 6:
                dist = (sweep_pos - i) % cols
                greens = ["\033[38;5;46m", "\033[38;5;40m", "\033[38;5;34m", "\033[38;5;28m", "\033[38;5;22m"]
                color = greens[dist - 1] if is_running and (dist - 1) < len(greens) else "\033[90m"
                char = "▰" if is_running else "⠂"
                line.append(f"{color}{char}\033[0m")
            else:
                line.append("\033[90m⠂\033[0m")
        return "".join(line)

    # --- Mode 2: Chrono Pendulum (Clock Metronome) ---
    elif style_mode == 2:
        t = current_elapsed * math.pi
        track_width = cols - 6
        if track_width < 4:
            return ""
        pos = int((math.sin(t) + 1.0) * 0.5 * (track_width - 1))
        pendulum = [" "] * cols
        pendulum[1] = "["
        pendulum[cols-2] = "]"
        for idx in range(3, cols-3):
            if idx == pos + 3:
                pendulum[idx] = "\033[1;38;5;209m●\033[0m" if is_running else "\033[90m●\033[0m"
            else:
                pendulum[idx] = "\033[90m·\033[0m"
        return "".join(pendulum)

    # --- Mode 3: Sweep Radar (Bouncing Dot) ---
    else:
        t = current_elapsed * 4.0
        pos = int((math.sin(t) + 1.0) * 0.5 * (cols - 3))
        bar = [" "] * cols
        color = "\033[38;5;209m" if is_running else "\033[90m"
        bar[pos] = "◀"
        bar[pos+1] = "█"
        bar[pos+2] = "▶"
        return "".join(f"{color}{c}\033[0m" if c != " " else c for c in bar)

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

def run_stopwatch_tui():
    """Main TUI loop mapping dynamic grid sizing for full-screen centering."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    # Clean screen initialization
    sys.stdout.write("\033[?25l\033[H\033[J")
    sys.stdout.flush()

    # Stopwatch variables
    is_running = False
    start_time = 0.0
    elapsed_paused = 0.0
    laps = []

    # UI size cache
    last_W, last_H = 0, 0
    ticks = 0
    visualizer_mode = 0  
    mode_names = {
        0: "Linear Pulse",
        1: "Sweep Oscilloscope",
        2: "Chrono Pendulum",
        3: "Sweep Radar"
    }

    try:
        tty.setraw(fd)

        while True:
            ticks += 1
            current_elapsed = get_elapsed(is_running, start_time, elapsed_paused)

            # Query live terminal window dimensions
            W, H = shutil.get_terminal_size()

            # Dynamic Redraw Check: wipe screen if terminal has been resized
            if W != last_W or H != last_H:
                sys.stdout.write("\033[H\033[J")
                last_W, last_H = W, H
            else:
                sys.stdout.write("\033[H")

            # Fallback block for tiny window sizes
            if H < 18 or W < 50:
                sys.stdout.write("\033[H\033[J")
                sys.stdout.write(" Terminal window too small for full-screen display.\r\n")
                sys.stdout.write(" Please expand your terminal.\r\n")
                sys.stdout.flush()
                time.sleep(0.1)
                continue

            # Core UI Box dimensions (accounting for borders)
            box_width = W - 2

            # -------------------------------------------------------------
            # Build Core UI Content Array
            # -------------------------------------------------------------
            content_rows = []

            # 1. Header Row
            header_colored = f"\033[1;32mCHRONOGRAPH\033[0m  \033[90m│\033[0m  \033[1mTHEME:\033[0m {mode_names[visualizer_mode]}"
            content_rows.append((header_colored, "center"))

            # 2. Blank
            content_rows.append(("", "center"))

            # 3. Status Badge Row
            if is_running:
                status_badge = "\033[1;42;30m RUNNING \033[0m"
            elif current_elapsed > 0:
                status_badge = "\033[1;43;30m PAUSED \033[0m"
            else:
                status_badge = "\033[1;90;37m IDLE \033[0m"
            content_rows.append((f" {status_badge} ", "center"))

            # 4. Large Clock Face
            time_display = fmt_time_high_res(current_elapsed)
            clock_colored = f"\033[1;39m[  {time_display}  ]\033[0m"
            content_rows.append((clock_colored, "center"))

            # 5. Blank
            content_rows.append(("", "center"))

            # 6. Spaced HUD Soft-buttons
            if is_running:
                btn_left = "\033[1;36m[L] LAP\033[0m"
                btn_right = "\033[1;31m[SPACE] STOP\033[0m"
            elif current_elapsed > 0:
                btn_left = "\033[1;33m[R] RESET\033[0m"
                btn_right = "\033[1;32m[SPACE] START\033[0m"
            else:
                btn_left = "\033[90m[L] LAP\033[0m"
                btn_right = "\033[1;32m[SPACE] START\033[0m"

            btn_left_len = len(strip_ansi(btn_left))
            btn_right_len = len(strip_ansi(btn_right))
            side_margin = 6
            available_space = box_width - (side_margin * 2) - btn_left_len - btn_right_len
            available_space = max(available_space, 2)
            btn_spacing = " " * available_space
            btn_colored = f"{' ' * side_margin}{btn_left}{btn_spacing}{btn_right}{' ' * side_margin}"
            content_rows.append((btn_colored, "center"))

            # 7. Blank
            content_rows.append(("", "center"))

            # 8. Scaled Chrono Dial Visualizer
            viz_width = W - 8
            viz_colored = generate_visualizer(is_running, ticks, visualizer_mode, current_elapsed, viz_width)
            content_rows.append((viz_colored, "center"))

            # 9. Dynamic Circular Loop Progress Bar
            current_minute_pct = (current_elapsed % 60) / 60.0
            filled = max(0, min(viz_width, int(current_minute_pct * viz_width)))
            progress_colored = f"\033[38;5;209m{'━' * filled}\033[0m\033[90m{'━' * (viz_width - filled)}\033[0m"
            content_rows.append((progress_colored, "center"))

            # 10. Horizontal Layout Divider
            content_rows.append((f"\033[90m{'─' * viz_width}\033[0m", "center"))

            # 11. Current Lap Stats
            if not laps:
                current_lap_time = current_elapsed
            else:
                current_lap_time = current_elapsed - laps[-1]['split_time']
            current_lap_str = fmt_time_high_res(current_lap_time)
            lap_colored = f"\033[1mCURRENT LAP:\033[0m \033[38;5;110m{current_lap_str}\033[0m"
            content_rows.append((lap_colored, "center"))

            # 12. Lap History Section Header
            content_rows.append(("── Lap History ──", "center"))

            # 13-15. Dynamic Lap History Items
            best_lap_idx = -1
            worst_lap_idx = -1
            if len(laps) >= 2:
                lap_times = [lap['lap_time'] for lap in laps]
                min_time = min(lap_times)
                max_time = max(lap_times)
                if min_time != max_time:
                    best_lap_idx = lap_times.index(min_time)
                    worst_lap_idx = lap_times.index(max_time)

            lap_rows = []
            if not laps:
                lap_rows.append(("\033[90m(No Laps Recorded)\033[0m", "left"))
            else:
                for idx, lap in list(enumerate(laps))[-3:][::-1]:
                    lap_num = idx + 1
                    lap_fmt = fmt_time_high_res(lap['lap_time'])
                    split_fmt = fmt_time_high_res(lap['split_time'])
                    
                    if idx == best_lap_idx:
                        lap_color = "\033[1;32m"  # Fastest: Green
                        tag = " (Fastest)"
                    elif idx == worst_lap_idx:
                        lap_color = "\033[1;31m"  # Slowest: Red
                        tag = " (Slowest)"
                    else:
                        lap_color = "\033[0m"
                        tag = ""

                    marker = "▶ " if idx == len(laps) - 1 else "  "
                    colored_lap = f"{marker}{lap_color}Lap {lap_num:02d}: {lap_fmt:<12}{tag:<12}\033[90m(Split: {split_fmt})\033[0m"
                    lap_rows.append((colored_lap, "left"))

            # Maintain structural layout budget by filling missing laps with empty rows
            while len(lap_rows) < 3:
                lap_rows.append(("", "left"))

            for row, alignment in lap_rows:
                content_rows.append((row, alignment))

            # 16. Lower Horizontal Divider
            content_rows.append((f"\033[90m{'─' * viz_width}\033[0m", "center"))

            # 17. Footer Key Options
            footer_colored = "\033[90m[v] Change Theme  │  [q] Quit stopwatch\033[0m"
            content_rows.append((footer_colored, "center"))

            # -------------------------------------------------------------
            # Render Bounding Box and Padding (Dynamic Centering Calculation)
            # -------------------------------------------------------------
            core_row_count = len(content_rows)
            # Available vertical padding inside the screen bounds
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
                if key == ' ' or key == '\r':
                    if is_running:
                        elapsed_paused += time.time() - start_time
                        is_running = False
                    else:
                        start_time = time.time()
                        is_running = True
                elif key.lower() == 'l':
                    if is_running:
                        total_elapsed = get_elapsed(is_running, start_time, elapsed_paused)
                        if not laps:
                            lap_duration = total_elapsed
                        else:
                            last_split = laps[-1]['split_time']
                            lap_duration = total_elapsed - last_split
                        laps.append({'lap_time': lap_duration, 'split_time': total_elapsed})
                elif key.lower() == 'r':
                    if not is_running and current_elapsed > 0:
                        is_running = False
                        start_time = 0.0
                        elapsed_paused = 0.0
                        laps = []
                elif key.lower() == 'v':
                    visualizer_mode = (visualizer_mode + 1) % 4
                elif key.lower() == 'q':
                    break

            time.sleep(0.03)

    except KeyboardInterrupt:
        pass
    finally:
        # Restore terminal settings and show cursor again
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\033[H\033[J")
        sys.stdout.flush()

if __name__ == "__main__":
    run_stopwatch_tui()
