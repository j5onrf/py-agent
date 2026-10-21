#!/usr/bin/env python3
"""UI Module - Spinners, session boxes, and interactive menus [OCR .01]"""

import json
import math
import os
import re
import select
import shutil
import sys
import threading
import time
import urllib.request as urlreq
from collections.abc import Callable
from typing import Any

from rich.box import DOUBLE, ROUNDED, SQUARE
from rich.cells import cell_len
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    import termios
    import tty
    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
_console = Console()
RE_UNSAFE_SHELL_CHARS: re.Pattern = re.compile(r'[\[\]{}()=\'"",;|<>#`$&*!\\\r\n]')

RICH_TO_ANSI = {
    "green": "\033[1;32m",
    "bright_green": "\033[1;92m",
    "blue": "\033[1;34m",
    "bright_blue": "\033[1;94m",
    "yellow": "\033[1;33m",
    "bright_yellow": "\033[1;93m",
    "cyan": "\033[1;36m",
    "bright_cyan": "\033[1;96m",
    "magenta": "\033[1;35m",
    "bright_magenta": "\033[1;95m",
    "dim white": "\033[37m",
    "white": "\033[1;37m",
}

_core_module = None
_cached_local_model: tuple[str, float] = ("", 0.0)

ANSI_SHADES = [
    "\033[2m",          # Level 0: Dim (theme background/unlit)
    "\033[90m",         # Level 1: Muted / Gray (theme comment tone)
    "\033[36m",         # Level 2: Cyan (theme primary accent)
    "\033[1;36m",       # Level 3: Bold Bright Cyan (theme vivid accent)
    "\033[1;37m",       # Level 4: Bold White (theme foreground highlight)
]
ANSI_RESET = "\033[0m"

DOT_GLYPHS = ["·", "•", "•", "○", "●"]


class InlineSpinner:
    def __init__(
        self,
        chars: tuple[str, ...] | list[str] | str = (
            "● ○ • ·",
            "○ ● ○ •",
            "• ○ ● ○",
            "· • ○ ●",
        ),
    ) -> None:
        self.chars = chars
        self.active = False
        self.thread = None
        self.message = "Thinking..."
        self.start_time = 0.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def _get_theme_color(self) -> str:
        return "\033[1;36m"

    def _glimmer(self, text: str, t: float, color: str) -> str:
        pos = (t * 2.2) % (len(text) + 8) - 4
        parts, cur_style = [], None
        for i, ch in enumerate(text):
            dist = abs(i - pos)
            style = "\033[1;37m" if dist < 1.0 else (f"{color}\033[1m" if dist < 2.5 else "\033[2m")
            if style != cur_style:
                parts.append(style)
                cur_style = style
            parts.append(ch)
        parts.append("\033[0m")
        return "".join(parts)

    def _spin(self) -> None:
        idx, char_len, tick = 0, len(self.chars), 0.0
        color = self._get_theme_color()
        while not self._stop_event.is_set() and self.active:
            try:
                char = self.chars[int(idx) % char_len]
                elapsed = time.time() - self.start_time
                with self._lock:
                    msg = self.message
                glim_msg = self._glimmer(msg, tick, color)
                if self._stop_event.is_set() or not self.active:
                    break
                frame = f"\r\x1b[K{color}{char}\033[0m {glim_msg} \033[2m{elapsed:.1f}s\033[0m"
                sys.stderr.write(frame)
                sys.stderr.flush()
            except OSError:
                pass
            idx += 0.4
            tick += 0.25
            time.sleep(0.05)
        try:
            sys.stderr.write("\r\x1b[2K\r")
            sys.stderr.flush()
        except OSError:
            pass

    def update(self, message: str) -> None:
        with self._lock:
            self.message = message

    def start(self, message: str = "Thinking...") -> None:
        with self._lock:
            self.message = message
            if not self.active:
                self.active = True
                self._stop_event.clear()
                self.start_time = time.time()
                try:
                    sys.stderr.write("\033[?25l")
                    sys.stderr.flush()
                except OSError:
                    pass
                self.thread = threading.Thread(target=self._spin, daemon=True)
                self.thread.start()

    def stop(self, done_msg: str | None = None, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            if not self.active:
                return
            self.active = False
            self._stop_event.set()
            elapsed = time.time() - self.start_time if getattr(self, "start_time", None) else 0.0

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.3)
            self.thread = None

        try:
            if done_msg:
                sys.stderr.write(f"\r\x1b[2K\033[1;32mOK\033[0m \033[1;36m{done_msg}\033[0m \033[2m({elapsed:.1f}s)\033[0m\n")
            else:
                sys.stderr.write("\r\x1b[2K\r")
            sys.stderr.write("\033[?25h")
            sys.stderr.flush()
        except OSError:
            pass


class CalmBoatSpinner:
    _boat_lock = threading.Lock()
    _last_x: int = 0
    _last_dir: int = 1
    _WAVE_PATTERN: str = "-~~~" * 32

    def __init__(self, tokens_used: int = 0, max_tokens: int = 8192) -> None:
        self.active = False
        self.thread = None
        self.tokens_used = max(1, tokens_used)
        self.max_tokens = max(1, max_tokens)
        self._lock = threading.Lock()

    def update_context(self, tokens_used: int, max_tokens: int | None = None) -> None:
        with self._lock:
            self.tokens_used = max(1, tokens_used)
            if max_tokens:
                self.max_tokens = max(1, max_tokens)

    def update(self, *args: Any, **kwargs: Any) -> None:
        """CalmBoatSpinner renders physical wave progress; textual message updates are no-op."""

    def _sail(self) -> None:
        with CalmBoatSpinner._boat_lock:
            x = CalmBoatSpinner._last_x
            direction = CalmBoatSpinner._last_dir

        w_offset = 0
        step_timer = time.time()
        step_interval = 0.88

        try:
            sys.stderr.write("\n\n\033[2A")
            sys.stderr.flush()
        except OSError:
            pass

        width = 57
        max_x = width - 6

        while self.active:
            now = time.time()

            with self._lock:
                tokens = self.tokens_used
                max_tok = self.max_tokens

            pct = min(100.0, (tokens / max_tok) * 100.0)

            if x > max_x:
                x = max_x
                direction = -1

            if now - step_timer >= step_interval:
                x += direction
                if x >= max_x:
                    x = max_x
                    direction = -1
                elif x <= 0:
                    x = 0
                    direction = 1
                with CalmBoatSpinner._boat_lock:
                    CalmBoatSpinner._last_x = x
                    CalmBoatSpinner._last_dir = direction
                step_timer = now

            sail = "<|" if direction == 1 else "|>"
            sail_line = (" " * (x + 2)) + f"\033[1;33m{sail}\033[0m"

            water_pattern = self._WAVE_PATTERN[w_offset : w_offset + width]
            left_water = water_pattern[:x]
            right_water = water_pattern[x + 5 : width]
            hull = r"\___/"

            w_col = "\033[34m" if pct < 70 else ("\033[33m" if pct < 88 else "\033[31m")

            water_line = (
                f"{w_col}{left_water}\033[0m"
                f"\033[1;33m{hull}\033[0m"
                f"{w_col}{right_water}\033[0m"
            )

            try:
                sys.stderr.write(f"\r\x1b[2K{sail_line}\n\r\x1b[2K{water_line}\033[1A")
                sys.stderr.flush()
            except OSError:
                pass

            w_offset = (w_offset + 1) % 4
            time.sleep(0.12)

    def start(self, message: str = "") -> None:
        if not sys.stderr.isatty():
            return
        with self._lock:
            if not self.active:
                self.active = True
                try:
                    sys.stderr.write("\033[?25l")
                    sys.stderr.flush()
                except OSError:
                    pass
                self.thread = threading.Thread(target=self._sail, daemon=True)
                self.thread.start()

    def stop(self, leave_on_screen: bool = False, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            if not self.active:
                return
            self.active = False
            tokens = self.tokens_used
            max_tok = self.max_tokens

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.25)
            self.thread = None

        width = 57
        pct = min(100.0, (tokens / max_tok) * 100.0)

        if leave_on_screen:
            dock_x = min(width - 5, max(0, int((pct / 100.0) * (width - 5))))

            sail_line = (" " * (dock_x + 2)) + "\033[1;33m|>\033[0m"
            water_pattern = self._WAVE_PATTERN[:width]
            left_water = water_pattern[:dock_x]
            right_water = water_pattern[dock_x + 5 : width]
            hull = r"\___/"

            w_col = "\033[34m" if pct < 70 else ("\033[33m" if pct < 88 else "\033[31m")

            docked_line = (
                f"{w_col}{left_water}\033[0m"
                f"\033[1;33m{hull}\033[0m"
                f"{w_col}{right_water}\033[0m"
            )

            try:
                sys.stderr.write(f"\r\x1b[2K{sail_line}\n\r\x1b[2K{docked_line}\n\n")
                sys.stderr.write("\033[?25h")
                sys.stderr.flush()
            except OSError:
                pass
        else:
            try:
                sys.stderr.write("\r\x1b[2K\n\r\x1b[2K\033[1A\r")
                sys.stderr.write("\033[?25h")
                sys.stderr.flush()
            except OSError:
                pass


def _read_fd(fd: int) -> str:
    if not _HAS_TERMIOS:
        return os.read(fd, 1).decode("utf-8", errors="ignore")

    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char_bytes = os.read(fd, 1)
        if not char_bytes:
            return ""
        if char_bytes == b"\x03":
            raise KeyboardInterrupt
        if char_bytes == b"\x1b" and select.select([fd], [], [], 0.05)[0]:
            more = os.read(fd, 2)
            char_bytes += more
            if len(more) == 1 and more in (b"[", b"O") and select.select([fd], [], [], 0.03)[0]:
                char_bytes += os.read(fd, 1)
        return char_bytes.decode("utf-8", errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        try:
            sys.stderr.write("\033[0m")
            sys.stderr.flush()
        except Exception:
            pass


def get_key() -> str:
    if sys.stdin.isatty():
        try:
            return _read_fd(sys.stdin.fileno())
        except Exception:
            pass
    try:
        with open("/dev/tty", "r") as f:
            return _read_fd(f.fileno())
    except Exception:
        pass
    try:
        return os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def get_local_model_name(max_age: float = 30.0) -> str:
    """Retrieves local model name with 30s TTL cache to avoid stalling render on slow/offline servers."""
    global _cached_local_model
    now = time.monotonic()
    val, last_time = _cached_local_model
    if val and (now - last_time < max_age):
        return val

    try:
        req = urlreq.Request("http://localhost:8080/v1/models", method="GET")
        with urlreq.urlopen(req, timeout=0.25) as r:
            m_name = os.path.basename(json.loads(r.read().decode("utf-8"))["data"][0]["id"])
            _cached_local_model = (m_name, now)
            return m_name
    except Exception:
        fallback = "model not loaded (offline :8080)"
        _cached_local_model = (fallback, now)
        return fallback


def _build_dots(row_idx: int, t: float, is_resting: bool = False, total_rows: int = 2) -> str:
    if is_resting:
        if total_rows == 3:
            patterns = [
                [4, 3, 1, 0, 1, 3, 4],  # Row 0: ● ○ • · • ○ ●
                [3, 1, 0, 0, 0, 1, 3],  # Row 1: ○ • · · · • ○
                [4, 3, 1, 0, 1, 3, 4],  # Row 2: ● ○ • · • ○ ●
            ]
        else:
            patterns = [
                [4, 3, 1, 0, 1, 3, 4],  # Row 0: ● ○ • · • ○ ●
                [3, 1, 0, 0, 0, 1, 3],  # Row 1: ○ • · · · • ○
            ]
        row_pat = patterns[row_idx % len(patterns)]
        cells = []
        for idx in row_pat:
            lvl = min(4, max(0, idx))
            glyph = DOT_GLYPHS[lvl]
            cells.append(f"{ANSI_SHADES[lvl]}{glyph}{ANSI_RESET}")
        return " ".join(cells)

    cells = []
    for c in range(7):
        val = math.sin((c * 0.75) - (row_idx * 0.70) - (t * 5.0))
        idx = min(4, max(0, int(((val + 1.0) / 2.0) * 4.99)))
        glyph = DOT_GLYPHS[idx]
        cells.append(f"{ANSI_SHADES[idx]}{glyph}{ANSI_RESET}")
    return " ".join(cells)


def _render_theme_shader(
    rows: list[tuple[str, str, int]],
    box_w: int,
    t: float,
    is_resting: bool = False,
    sub_tag: str = "",
) -> str:
    inner_w = box_w - 2
    dots_w = 13  # 7 glyphs with 6 spaces
    header = "╭─ ○ " + sub_tag
    dashes_top = max(0, inner_w - len(header) + 1)

    if is_resting:
        lines = [f"\033[1;36m{header}{'─' * dashes_top}╮{ANSI_RESET}"]
        for r_idx, (colored_text, _, text_len) in enumerate(rows):
            gap_len = max(2, inner_w - 4 - text_len - dots_w)
            dots_field = _build_dots(r_idx, 0.0, is_resting=True, total_rows=len(rows))
            lines.append(
                f"\033[1;36m│{ANSI_RESET}  {colored_text}{' ' * gap_len}{dots_field}  \033[1;36m│{ANSI_RESET}"
            )
        lines.append(f"\033[1;36m╰{'─' * inner_w}╯{ANSI_RESET}")
        return "\n".join(lines)

    top_chars = []
    top_plain = f"{header}{'─' * dashes_top}╮"
    for x, ch in enumerate(top_plain):
        wave = math.sin((x * 0.14) - (t * 4.2))
        lvl = min(4, max(0, int(((wave + 0.85) / 1.85) * 4.99)))
        top_chars.append(f"{ANSI_SHADES[lvl]}{ch}{ANSI_RESET}")
    lines = ["".join(top_chars)]

    for r_idx, (_, plain_text, text_len) in enumerate(rows):
        y = r_idx + 1
        wave_l = math.sin(- (y * 0.45) - (t * 4.2))
        lvl_l = min(4, max(0, int(((wave_l + 0.85) / 1.85) * 4.99)))
        left_border = f"{ANSI_SHADES[lvl_l]}│{ANSI_RESET}"

        text_chars = []
        for i, ch in enumerate(plain_text):
            x = 3 + i
            wave = math.sin((x * 0.14) - (y * 0.45) - (t * 4.2))
            lvl = min(4, max(0, int(((wave + 0.85) / 1.85) * 4.99)))
            text_chars.append(f"{ANSI_SHADES[lvl]}{ch}{ANSI_RESET}")

        gap_len = max(2, inner_w - 4 - text_len - dots_w)
        dots_field = _build_dots(r_idx, t, is_resting=False, total_rows=len(rows))

        wave_r = math.sin((inner_w * 0.14) - (y * 0.45) - (t * 4.2))
        lvl_r = min(4, max(0, int(((wave_r + 0.85) / 1.85) * 4.99)))
        right_border = f"{ANSI_SHADES[lvl_r]}│{ANSI_RESET}"

        lines.append(f"{left_border}  {''.join(text_chars)}{' ' * gap_len}{dots_field}  {right_border}")

    bot_chars = []
    bot_plain = f"╰{'─' * inner_w}╯"
    y_bot = len(rows) + 1
    for x, ch in enumerate(bot_plain):
        wave = math.sin((x * 0.14) - (y_bot * 0.45) - (t * 4.2))
        lvl = min(4, max(0, int(((wave + 0.85) / 1.85) * 4.99)))
        bot_chars.append(f"{ANSI_SHADES[lvl]}{ch}{ANSI_RESET}")
    lines.append("".join(bot_chars))

    return "\n".join(lines)


def draw_session_box(
    workspace_path: str,
    home_dir: str,
    is_agent: bool,
    db_turns: int,
    mem_count: int,
    memory_active: bool,
    active_system_prompt: str,
    clean_name: str,
    sub_id: int | None = None,
    box_style: int = 1,
    wake_on_key: bool = True,
) -> str:
    raw_path = str(workspace_path).strip().splitlines()[0].strip() if workspace_path else ""
    clean_path = re.sub(r"^[󱞩\s]+", "", raw_path)
    display_dir = (
        clean_path.replace(home_dir, "~", 1)
        if (home_dir and clean_path.startswith(home_dir))
        else clean_path
    )

    try:
        import agent_cloud
        configs = agent_cloud.get_active_configs([])
        model_name = configs[0][2].get("model", "local-model") if configs else get_local_model_name()
    except Exception:
        model_name = get_local_model_name()

    display_profile = (clean_name or "chat").replace("custom/", "", 1)

    if is_agent:
        try:
            import agent_core as core
            use_map = bool(core.get_state("use_map", False)) or os.environ.get("AI_USE_MAP") == "1"
        except Exception:
            use_map = os.environ.get("AI_USE_MAP") == "1"

        if memory_active and use_map:
            db_status = f"active (map + mem: {mem_count}m/{db_turns}t)"
        elif memory_active:
            db_status = f"active ({mem_count} memories, {db_turns} turns)"
        elif use_map:
            db_status = "active (codebase map)"
        elif db_turns > 0:
            db_status = f"active ({db_turns} turns)"
        else:
            db_status = "session"
    else:
        db_status = "session"

    term_cols = shutil.get_terminal_size((80, 24)).columns
    sub_tag = f"[sub-agent #{sub_id}] " if sub_id else ""

    m_style = "\033[1;31m" if ("not loaded" in model_name or "offline" in model_name) else "\033[1;37m"
    rows = [
        (f"{m_style}{model_name}{ANSI_RESET}", model_name, cell_len(model_name)),
        (f"\033[90m{display_profile}{ANSI_RESET}", display_profile, cell_len(display_profile)),
    ]

    # 3rd line only in workspace agent mode when memory is active
    if is_agent and memory_active:
        rows.append((f"\033[32m{db_status}{ANSI_RESET}", db_status, cell_len(db_status)))

    num_lines = len(rows) + 2
    max_text_w = max(r[2] for r in rows)
    dots_w = 13
    inner_w = max(44, min(term_cols - 4, max_text_w + dots_w + 6))
    box_w = inner_w + 2

    is_tty = sys.stdout.isatty() and sys.stdin.isatty() and os.environ.get("AI_ANIM", "1") != "0"
    captured_char = ""

    if is_tty and wake_on_key and _HAS_TERMIOS:
        old_term = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        try:
            start_time = time.time()
            first_frame = True

            while True:
                r, _, _ = select.select([sys.stdin], [], [], 0.0)
                if r:
                    char_bytes = os.read(sys.stdin.fileno(), 1)
                    if char_bytes == b"\x1b" and select.select([sys.stdin], [], [], 0.05)[0]:
                        os.read(sys.stdin.fileno(), 4)
                        captured_char = ""
                    elif char_bytes:
                        try:
                            decoded = char_bytes.decode("utf-8", errors="ignore")
                            if decoded not in ("\r", "\n", "\x1b", "\x03"):
                                captured_char = decoded
                        except Exception:
                            captured_char = ""
                    break

                t = time.time() - start_time
                frame_str = _render_theme_shader(rows, box_w, t, is_resting=False, sub_tag=sub_tag)
                if first_frame:
                    sys.stdout.write(frame_str + "\n")
                    first_frame = False
                else:
                    sys.stdout.write(f"\033[{num_lines}A\r{frame_str}\n")
                sys.stdout.flush()
                time.sleep(0.033)

            resting_str = _render_theme_shader(rows, box_w, 0.0, is_resting=True, sub_tag=sub_tag)
            sys.stdout.write(f"\033[{num_lines}A\r{resting_str}\n\n")
            sys.stdout.flush()
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term)
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()

        return captured_char

    # Non-interactive fallback or direct resting render
    resting_str = _render_theme_shader(rows, box_w, 0.0, is_resting=True, sub_tag=sub_tag)
    print(resting_str + "\n")
    return ""


def confirm_tool(tool: str) -> bool:
    target = getattr(sys, "__stderr__", None) or sys.stderr
    target.write(f"\r\x1b[2K\r\033[1;33m[sys] Authorize tool:\033[0m \033[36m{tool}\033[0m \033[1;33m? [y/N]: \033[0m")
    target.flush()
    try:
        char = get_key()
    except Exception:
        char = ""
    is_yes = char.strip().lower() in ("y", "yes")
    target.write("y\n" if is_yes else "n\n")
    target.flush()
    return is_yes


def run_interactive_selection(
    intent: str,
    jaccard_search_fn: Callable[[str], str | None],
    clean_tool_prefix_fn: Callable[[str], str],
    print_stock_error_fn: Callable[[str], Any],
    ensure_mysys_exists_fn: Callable[[], None],
) -> None:
    if RE_UNSAFE_SHELL_CHARS.search(intent) or not (matched_base := jaccard_search_fn(intent)):
        print_stock_error_fn(intent)
        sys.exit(127)

    options = matched_base.split("\n")
    num_opts, current_idx = len(options), 0
    sys.stderr.write("\033[?25l")
    sys.stderr.flush()

    try:
        while True:
            intent_part, sep, cmd_part = options[current_idx].partition("|||")
            current_intent = intent_part.strip() if sep else "run"
            current_cmd = clean_tool_prefix_fn((cmd_part if sep else intent_part).strip())
            is_danger = current_cmd.startswith("DANGER_FLAGGED:")
            cmd_to_show = current_cmd.replace("DANGER_FLAGGED:", "")
            display_cmd = (
                cmd_to_show.replace(" >/dev/null 2>&1", "")
                .replace(os.path.expanduser("~"), "~")
                .replace("/.config/py-agent/projects/", "/")
            )

            idx_str = f"{current_idx + 1:02d}/{num_opts:02d}"
            prompt = (
                f"\r\x1b[2K\033[1;31mWARNING: Destructive payload detected\033[0m\n\r\x1b[2K\033[1;31m[{idx_str}]\033[0m > \x1b[1;36m[{current_intent}]\x1b[0m {display_cmd}\n\r\x1b[2K\033[2m::\033[0m execute payload? [y/N]: "
                if is_danger
                else f"\r\x1b[2K\033[1;32m[{idx_str}]\033[0m > \x1b[1;36m[{current_intent}]\x1b[0m {display_cmd}\n\r\x1b[2K\033[2m::\033[0m enter to run, Esc to cancel: "
            )
            sys.stderr.write(prompt)
            sys.stderr.flush()

            key = get_key()

            if not key or key == "\x1b":
                sys.stderr.write("\r\x1b[2K\x1b[1A\r\x1b[2K")
                sys.stderr.flush()
                sys.exit(127)

            if key in ("\x1b[A", "\x1b[B"):
                current_idx = (current_idx + (1 if key == "\x1b[B" else -1) + num_opts) % num_opts
                sys.stderr.write("\r\x1b[2K\x1b[1A\r\x1b[2K")
                sys.stderr.flush()
                continue

            if is_danger:
                sys.stderr.write("\r\x1b[2K\x1b[1A\r\x1b[2K\x1b[1A\r\x1b[2K")
                sys.stderr.flush()
                if key.lower() == "y":
                    if "system" in cmd_to_show:
                        ensure_mysys_exists_fn()
                    sys.stdout.write(cmd_to_show)
                    sys.stdout.flush()
                    sys.exit(0)
                sys.exit(127)

            if key in ("\r", "\n", "y", "Y"):
                sys.stderr.write("\r\x1b[2K")
                sys.stderr.flush()
                if "system" in cmd_to_show:
                    ensure_mysys_exists_fn()
                sys.stdout.write(cmd_to_show)
                sys.stdout.flush()
                sys.exit(0)

            sys.stderr.write("\r\x1b[2K\x1b[1A\r\x1b[2K")
            sys.stderr.flush()
            sys.exit(127)
    finally:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()


def show_help() -> None:
    header = Text.assemble(
        ("  Shortcuts: ", "dim"),
        ("Esc", "bold yellow"),
        (": bypass  |  ", "dim"),
        ("Ctrl+C", "bold yellow"),
        (": cancel  |  ", "dim"),
        ("q / exit", "bold yellow"),
        (": quit", "dim"),
    )

    cmd_table = Table(show_header=False, box=None, padding=(0, 1))
    cmd_table.add_column("Command", style="bold cyan", justify="left", no_wrap=True)
    cmd_table.add_column("Description", style="white")

    cmds = [
        ("/h", "Help menu"),
        ("/pyc, /pyc web", "PyCode IDE (Desktop / Web)"),
        ("/dsh", "DeepSeek Harness (dsh)"),
        ("/webui, /web", "WebUI gateway (llama.cpp)"),
        ("/tui", "Terminal UI (PyTUI)"),
        ("/calm, /zen", "Toggle silent Calm mode (boat indicator)"),
        ("/v \\[auto], /voice", "Voice to text"),
        ("/tts", "Text to speech (Kokoro)"),
        ("/adp", "Toggle self-healing adapters"),
        ("/py \\[code]", "IPython kernel execution"),
        ("/m, /map", "Toggle Codebase index-map"),
        ("/mem \\[save|list]", "Toggle & manage OKF memory files"),
        ("/hs, /hindsight", "Retrospective session memory audit"),
        ("/box", "Replay dynamic theme skeleton wave"),
        ("/task \\[goal]", "Autonomous task loop"),
        ("/t \\[N|show|hide]", "Reasoning budget & display"),
        ("/g, /yolo", "Toggle confirmation gates (YOLO)"),
        ("/md", "Toggle Markdown stream"),
        ("/stats", "Generation speed stats"),
        ("/com, /compact", "3-Zone context compaction"),
        ("/tok", "Context token usage"),
        ("/sync", "Sync codebase index-map"),
        ("/clear, /c", "Soft clear active chat history"),
        ("/reset, /r", "Hard reset (.agent & database purge)"),
        ("/s <query|off>", "Load or unload skill"),
        ("-save <tag>", "Save checkpoint"),
        ("-load", "Restore checkpoint"),
        ("/gnd \\[budget|on|off]", "Search grounding (Gemini/DDG)"),
        ("/f, /tk, /b, /a", "Follow-up, Think, Brainstorm, All"),
        ("file <path>", "Load file into context"),
        ("exit, quit, q", "Exit"),
    ]

    for cmd, desc in cmds:
        cmd_table.add_row(cmd, f"[dim]-[/dim] {desc}")

    _console.print(
        "\n",
        Panel(
            Group(header, Text(""), Text("  Commands:", style="bold yellow"), cmd_table),
            title=" Help & Commands ",
            title_align="left",
            border_style="bright_blue",
            box=ROUNDED,
            expand=False,
        ),
        "\n",
    )


def select_workspace_profile(workspace_name: str) -> tuple[str, bool, bool, bool, bool, bool]:
    """Renders consolidated profile selector with automatic frontmatter pre-cache and 2-line layout."""
    import agent_skills as skills

    profiles_dir = os.path.join(CFG_DIR, "skills", "profiles")
    collected = []

    if os.path.isdir(profiles_dir):
        for fname in sorted(os.listdir(profiles_dir)):
            if fname.endswith(".md") and not fname.endswith(("-py.md", "-map.md")):
                base_name = os.path.splitext(fname)[0]
                k = base_name
                sf = os.path.join(profiles_dir, fname)
                defaults = {"yolo": False, "map": False, "py": False, "mem": False, "adp": False}
                tok_lbl = "~200t"
                cat = None

                try:
                    with open(sf, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                    meta, body = skills.parse_frontmatter(raw_content)
                    tok_count = max(1, (len(body or raw_content) * 10) // 36)
                    tok_lbl = f"~{tok_count / 1000:.1f}kt" if tok_count >= 1000 else f"~{tok_count}t"
                    defaults["yolo"] = str(meta.get("yolo", "")).lower() in ("true", "1", "yes", "on")
                    defaults["map"] = str(meta.get("map", meta.get("use_map", ""))).lower() in ("true", "1", "yes", "on")
                    defaults["py"] = str(meta.get("ipython", meta.get("py", ""))).lower() in ("true", "1", "yes", "on")
                    defaults["mem"] = str(meta.get("memory", meta.get("mem", ""))).lower() in ("true", "1", "yes", "on")
                    defaults["adp"] = str(meta.get("adapters", meta.get("adp", meta.get("adapter", "")))).lower() in ("true", "1", "yes", "on")
                    cat = meta.get("category")
                except Exception as e:
                    sys.stderr.write(f"\033[1;33m[ai init]\033[0m Failed to parse {sf}: {e}\n")

                if not cat:
                    if base_name.startswith("cloud-") or base_name in ("gemini", "deepseek"):
                        cat = "Cloud"
                    elif base_name in ("sysadmin", "tini-cybersec"):
                        cat = "Roles"
                    else:
                        cat = "Local"

                lbl = base_name.replace("-", " ").title()
                collected.append((cat, k, lbl, tok_lbl, defaults))

    all_entries = collected
    cat_order = {"Cloud": 0, "Local": 1, "Roles": 2}
    all_entries.sort(key=lambda x: (cat_order.get(x[0], 99), x[2].lower()))

    profile_cache = {}
    options = []
    seen_cats = set()
    for cat_name, k, lbl, tok_lbl, defaults in all_entries:
        profile_cache[k] = defaults
        cat_header = cat_name if cat_name not in seen_cats else None
        seen_cats.add(cat_name)
        options.append((k, lbl, tok_lbl, cat_header))

    if not options:
        sys.stderr.write(f"\033[1;33m[ai init]\033[0m No agent profiles found in {profiles_dir}. Using defaults.\n")
        return "chat", False, False, False, False, False

    sys.stderr.write(f"\n\033[1;36m[ai init]\033[0m Select default Agent Profile for workspace \033[1;33m{workspace_name}\033[0m:\n\n\033[?25l")
    sys.stderr.flush()

    current_idx, num_opts = 0, len(options)
    user_overrides = set()

    ws_path = os.environ.get("AI_WORKSPACE_PATH", os.path.join(CFG_DIR, "projects", workspace_name))
    if not os.path.isdir(ws_path):
        ws_path = os.getcwd()

    map_toks = 350
    for cand in [
        os.path.join(ws_path, ".agent", f"index-map-{workspace_name}.txt"),
        os.path.join(ws_path, f"index-map-{workspace_name}.txt"),
    ]:
        if os.path.isfile(cand):
            try:
                map_toks = max(50, (os.path.getsize(cand) * 10) // 36)
                break
            except OSError:
                pass

    mem_toks = 0
    mem_dir = os.path.join(ws_path, ".agent", "memory")
    if os.path.isdir(mem_dir):
        try:
            mem_toks = sum(
                (os.path.getsize(os.path.join(mem_dir, f)) * 10) // 36
                for f in os.listdir(mem_dir)
                if f.endswith(".md")
            )
        except OSError:
            pass
    if mem_toks == 0:
        mem_toks = 40
    init_meta = profile_cache.get(options[0][0], {})
    is_yolo = init_meta.get("yolo", False)
    use_map = init_meta.get("map", False)
    is_py = init_meta.get("py", False)
    is_mem = init_meta.get("mem", False)
    is_adp = init_meta.get("adp", False)
    last_rendered_lines = 0

    try:
        while True:
            cur_key = options[current_idx][0]
            cur_meta = profile_cache.get(cur_key, {})
            if "yolo" not in user_overrides:
                is_yolo = cur_meta.get("yolo", False)
            if "map" not in user_overrides:
                use_map = cur_meta.get("map", False)
            if "py" not in user_overrides:
                is_py = cur_meta.get("py", False)
            if "mem" not in user_overrides:
                is_mem = cur_meta.get("mem", False)
            if "adp" not in user_overrides:
                is_adp = cur_meta.get("adp", False)

            frame_lines = []
            sub_idx = 1
            for idx, (k, lbl, d, cat) in enumerate(options):
                if cat:
                    sub_idx = 1
                    if idx > 0:
                        frame_lines.append("\r\x1b[K\n")
                    dashes = "─" * max(5, 30 - len(cat))
                    frame_lines.append(f"\r\x1b[K\033[1;36m  ─── {cat} {dashes}\033[0m\n")

                if idx == current_idx:
                    frame_lines.append(f"\r\x1b[K\033[1;32m  > {sub_idx:2d}. {lbl:<20}\033[0m \033[1;36m({d})\033[0m\n")
                else:
                    frame_lines.append(f"\r\x1b[K\033[37m    {sub_idx:2d}. {lbl:<20}\033[0m \033[2m({d})\033[0m\n")
                sub_idx += 1

            b_on = "\033[1;36m[ON]\033[0m"
            b_off = "\033[37m[OFF]\033[0m"
            yolo_badge = b_on if is_yolo else b_off
            map_badge  = b_on if use_map  else b_off
            mem_badge  = b_on if is_mem   else b_off
            py_badge   = b_on if is_py    else b_off
            adp_badge  = b_on if is_adp else b_off

            if is_py:
                tool_label = "python + native (7 tools, ~760t)"
            elif use_map:
                tool_label = "index-map (11 tools, ~1.1kt)"
            else:
                tool_label = "native json (6 tools, ~680t)"

            addons = []
            if use_map:
                m_str = f"~{map_toks}t" if map_toks < 1000 else f"~{map_toks/1000:.1f}kt"
                addons.append(f"+Map: {m_str}")
            if is_mem:
                mem_str = f"~{mem_toks}t" if mem_toks < 1000 else f"~{mem_toks/1000:.1f}kt"
                addons.append(f"+Mem: {mem_str}")

            addon_info = f"  \033[90m[{' | '.join(addons)}]\033[0m" if addons else ""
            tools_desc = f"\033[1;36m{tool_label:<29}\033[0m{addon_info}"

            bottom_text = (
                f"\r\x1b[K\n\r\x1b[K    \033[2mTools:\033[0m {tools_desc}\n"
                f"\r\x1b[K\n\r\x1b[K  \033[2m::\033[0m "
                f"\033[1;37mEnter\033[0m \033[37mselect\033[0m    "
                f"\033[1;37mUp/Down\033[0m \033[37mnavigate\033[0m    "
                f"\033[1;37mEsc:\033[0m \033[37mdefault\033[0m\n"
                f"\r\x1b[K     "
                f"\033[37mTab: YOLO\033[0m {yolo_badge}    "
                f"\033[37mm: Map\033[0m {map_badge}    "
                f"\033[37md: Mem\033[0m {mem_badge}    "
                f"\033[37mp: Py\033[0m {py_badge}    "
                f"\033[37ma: Adp\033[0m {adp_badge}"
            )
            frame_lines.append(bottom_text)

            full_frame = "".join(frame_lines)
            lines_count = full_frame.count("\n")

            if last_rendered_lines > 0:
                sys.stderr.write(f"\033[{last_rendered_lines}A\r\033[J")

            sys.stderr.write(full_frame)
            sys.stderr.flush()
            last_rendered_lines = lines_count

            char = get_key()
            if not char:
                sys.stderr.write("\r\x1b[2K\n\033[1;33m[ai init] Input closed. Aborting.\033[0m\n")
                sys.stderr.flush()
                sys.exit(0)

            if char == "\x03":
                sys.stderr.write("\r\x1b[2K\n\033[1;33mCancelled.\033[0m\n")
                sys.stderr.flush()
                raise KeyboardInterrupt
            elif char in ("\t", "y", "Y"):
                is_yolo = not is_yolo
                user_overrides.add("yolo")
            elif char in ("m", "M"):
                use_map = not use_map
                user_overrides.add("map")
            elif char in ("d", "D"):
                is_mem = not is_mem
                user_overrides.add("mem")
            elif char in ("p", "P"):
                is_py = not is_py
                user_overrides.add("py")
            elif char in ("a", "A"):
                is_adp = not is_adp
                user_overrides.add("adp")
            elif char in ("\x1b", "\r", "\n"):
                is_enter = char in ("\r", "\n")
                key, label = options[current_idx if is_enter else 0][:2]

                sys.stderr.write(f"\x1b[{last_rendered_lines + 3}A\r\x1b[J")

                if is_enter and not is_yolo:
                    sys.stderr.write(f"\033[1;36mEnable Autonomous YOLO mode for {label}? [y/N] \033[2m(Esc/Left: back)\033[0m: \033[0m")
                    sys.stderr.flush()
                    raw_c = get_key()
                    c = raw_c.lower()

                    if raw_c in ("\x1b", "\x1b[D", "\x7f", "\x08", "\x1b[A", "\x1b[B") or c in ("b", "back"):
                        sys.stderr.write("\r\x1b[2K")
                        sys.stderr.write(
                            f"\n\033[1;36m[ai init]\033[0m Select default Agent Profile for workspace \033[1;33m{workspace_name}\033[0m:\n\n"
                        )
                        sys.stderr.flush()
                        last_rendered_lines = 0
                        continue

                    if c == "y":
                        is_yolo = True
                    sys.stderr.write("\r\x1b[2K")

                active_badges = "".join(
                    f" \033[1;36m[{tag}: ON]\033[0m"
                    for tag, active in [("Yolo", is_yolo), ("Map", use_map), ("Mem", is_mem), ("Py", is_py), ("Adp", is_adp)]
                    if active
                )
                sys.stderr.write(f"\033[1;32m✓ Profile set to:\033[0m \033[1m{label}\033[0m{active_badges}\n")
                sys.stderr.flush()
                return key, is_yolo, use_map, is_py, is_mem, is_adp
            elif char in ("\x1b[A", "\x1b[B"):
                current_idx = (current_idx + (1 if char == "\x1b[B" else -1) + num_opts) % num_opts
    finally:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()
