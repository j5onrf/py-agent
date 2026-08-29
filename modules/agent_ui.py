#!/usr/bin/env python3
"""UI Module - Spinners, session boxes, and interactive menus"""

import json
import os
import re
import select
import sys
import threading
import time
import urllib.request as urlreq
from collections.abc import Callable
from typing import Any

from rich.box import DOUBLE, HEAVY, HORIZONTALS, ROUNDED
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    import termios
    import tty
except ImportError:
    pass

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
_console, _console_err = Console(), Console(stderr=True)
RE_UNSAFE_SHELL_CHARS: re.Pattern = re.compile(r'[\[\]{}()=\'"",;|<>#]')


class InlineSpinner:
    """A thread-safe, lightweight console spinner tracking elapsed operation runtime."""

    def __init__(self, chars: tuple[str, ...] | list[str] | str = ("✦ [∿ · ·]", "✦ [· ∿ ·]", "✦ [· · ∿]", "✦ [· ∿ ·]")) -> None:
        self.chars, self.active, self.thread, self.message, self.start_time = (
            chars,
            False,
            None,
            "Thinking...",
            0.0,
        )
        self._lock = threading.Lock()

    def _get_theme_color(self) -> str:
        try:
            import agent_core as core
            box = core.get_state("box_style", 1)
            colors = {1: "\033[1;32m", 2: "\033[1;34m", 3: "\033[1;36m", 4: "\033[1;37m", 5: "\033[1;32m"}
            return colors.get(box, "\033[1;32m")
        except Exception:
            return "\033[1;32m"

    def _spin(self) -> None:
        idx, char_len = 0, len(self.chars)
        color = self._get_theme_color()
        while self.active:
            try:
                char, elapsed = self.chars[idx % char_len], time.time() - self.start_time
                with self._lock:
                    msg = self.message
                sys.stderr.write(
                    f"\r\x1b[K{color}{char}\033[0m \033[36m{msg}\033[0m \033[2m{elapsed:.1f}s\033[0m"
                )
                sys.stderr.flush()
            except OSError:
                pass
            idx += 1
            time.sleep(0.14)
        try:
            sys.stderr.write("\r\x1b[2K\r")
            sys.stderr.flush()
        except OSError:
            pass

    def update(self, message: str) -> None:
        with self._lock:
            self.message = message

    def start(self, message: str = "Thinking...") -> None:
        if not self.active:
            self.active = True
            with self._lock:
                self.message = message
            self.start_time = time.time()
            self.thread = threading.Thread(target=self._spin, daemon=True)
            self.thread.start()

    def stop(self, done_msg: str | None = None, *args: Any, **kwargs: Any) -> None:
        if self.active:
            self.active = False
            elapsed = time.time() - self.start_time if getattr(self, "start_time", None) else 0.0
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=0.2)
                self.thread = None
            try:
                if done_msg:
                    sys.stderr.write(
                        f"\r\x1b[K\033[1;32m✔\033[0m \033[1;36m{done_msg}\033[0m \033[2m({elapsed:.1f}s)\033[0m\n"
                    )
                else:
                    sys.stderr.write("\r\x1b[2K\r")
                sys.stderr.write("\033[?25h")
                sys.stderr.flush()
            except OSError:
                pass


def _read_fd(fd: int) -> str:
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        termios.tcflush(fd, termios.TCIFLUSH)
        char_bytes = os.read(fd, 1)
        if char_bytes == b"\x1b" and select.select([fd], [], [], 0.05)[0]:
            char_bytes += os.read(fd, 2)
        return char_bytes.decode("utf-8", errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old)
        try:
            sys.stdout.write("\033[0m")
            sys.stdout.flush()
        except Exception:
            pass


def get_key() -> str:
    """Reads a single key or raw keyboard escape sequence securely from /dev/tty or stdin."""
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


def get_local_model_name() -> str:
    """Queries the running llama-server to extract the loaded model's filename."""
    try:
        req = urlreq.Request("http://localhost:8080/v1/models", method="GET")
        with urlreq.urlopen(req, timeout=0.5) as r:
            return os.path.basename(json.loads(r.read().decode("utf-8"))["data"][0]["id"])
    except Exception:
        return "local-model"


def draw_session_box(
    workspace_path: str,
    home_dir: str,
    is_agent: bool,
    db_turns: int,
    tpm_count: int,
    memory_active: bool,
    active_system_prompt: str,
    clean_name: str,
    sub_id: int | None = None,
    box_style: int = 1,
) -> None:
    """Renders the system initialization box with customizable style presets (1-5)."""
    display_dir = (
        workspace_path.replace(home_dir, "~", 1)
        if workspace_path.startswith(home_dir)
        else workspace_path
    )

    try:
        import agent_cloud

        configs = agent_cloud.get_active_configs([])
        model_name = (
            configs[0][2].get("model", "local-model") if configs else get_local_model_name()
        )
    except Exception:
        model_name = get_local_model_name()

    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("Key", style="dim cyan", justify="right")
    table.add_column("Value", style="green")

    table.add_row("model:", model_name)
    table.add_row("directory:", display_dir)
    table.add_row("skill:", clean_name or "chat")
    mem_status = f"active ({tpm_count} facts, {db_turns} turns)" if memory_active else "stateless"
    table.add_row("database:", mem_status if is_agent else "stateless")

    STYLES = {
        1: ("\u223f Py Agent", ROUNDED, "green", "bold bright_green"),
        2: ("\u223f Py Agent", DOUBLE, "bright_blue", "bold bright_blue"),
        3: ("\u223f Py Agent", HEAVY, "bright_cyan", "bold bright_white"),
        4: ("Py Agent", HORIZONTALS, "dim white", "bold cyan"),
    }

    if box_style == 5:
        title_str = f"  \u223f Py Agent [sub-agent #{sub_id}]" if sub_id else "  \u223f Py Agent"
        panel = Panel(
            Group(Text(title_str, style="bold bright_green"), Text(""), table),
            border_style="green",
            box=ROUNDED,
            expand=False,
            subtitle="[dim]Ctrl+C to exit[/dim]",
            subtitle_align="right",
        )
    else:
        base_title, box_type, border_col, title_style = STYLES.get(box_style, STYLES[1])
        title_text = f" {base_title} [sub-agent #{sub_id}] " if sub_id else f" {base_title} "
        panel = Panel(
            table,
            title=Text(title_text, style=title_style),
            title_align="left",
            border_style=border_col,
            box=box_type,
            expand=False,
            subtitle="[dim]Ctrl+C to exit[/dim]",
            subtitle_align="right",
        )

    _console.print(panel)
    _console.print(f"[dim][sys] Startup context: {len(active_system_prompt) // 4:,} tokens[/dim]\n")
    try:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()
    except OSError:
        pass


def confirm_tool(tool: str) -> bool:
    """Intercepts potentially out-of-bounds commands for visual user verification."""
    target = getattr(sys, "__stderr__", None) or sys.stderr
    target.write(
        f"\r\x1b[K\033[1;33m▲ [sys] Authorize tool:\033[0m \033[36m{tool}\033[0m \033[1;33m? [Y/n]: \033[0m"
    )
    target.flush()
    try:
        char = get_key()
    except Exception:
        char = ""
    is_yes = char.lower() == "y" or char in ("\r", "\n", "")
    target.write("y\n" if is_yes else "n\n")
    target.flush()
    return is_yes


def run_interactive_selection(
    intent: str,
    jaccard_search_fn: Callable[[str], str | None],
    clean_tool_prefix_fn: Callable[[str], str],
    print_stock_error_fn: Callable[[str], None],
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
            current_intent, current_cmd = options[current_idx].split("|||", 1)
            current_cmd = clean_tool_prefix_fn(current_cmd)
            is_danger = current_cmd.startswith("DANGER_FLAGGED:")
            cmd_to_show = current_cmd.replace("DANGER_FLAGGED:", "")
            display_cmd = (
                cmd_to_show.replace(" >/dev/null 2>&1", "")
                .replace(os.path.expanduser("~"), "~")
                .replace("/.config/py-agent/projects/", "/")
            )

            idx_str = f"{current_idx + 1:02d}/{num_opts:02d}"
            prompt = (
                f"\r\x1b[2K\033[1;31m▲ WARNING: Destructive payload detected\033[0m\n\r\x1b[2K\033[1;31m[{idx_str}]\033[0m ❯ \x1b[1;36m[{current_intent}]\x1b[0m {display_cmd}\n\r\x1b[2K\033[2m::\033[0m execute payload? [y/N]: "
                if is_danger
                else f"\r\x1b[2K\033[1;32m[{idx_str}]\033[0m ❯ \x1b[1;36m[{current_intent}]\x1b[0m {display_cmd}\n\r\x1b[2K\033[2m::\033[0m ↵ run  Esc: "
            )
            sys.stderr.write(prompt)
            sys.stderr.flush()

            key = get_key()

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

            if key in ("\r", "", "y", "Y"):
                sys.stderr.write("\n")
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
    """Renders a Pi-styled clean CLI help menu for Local-AI Agent."""
    header = Text.assemble(
        ("  Shortcuts: ", "dim"),
        ("Esc", "bold yellow"),
        (": bypass  ", "dim"),
        ("Ctrl+C", "bold yellow"),
        (": cancel", "dim"),
    )

    cmd_table = Table(show_header=False, box=None, padding=(0, 1))
    cmd_table.add_column("Command", style="bold cyan", justify="left", no_wrap=True)
    cmd_table.add_column("Description", style="white")

    cmds = [
        ("/h", "Help menu"),
        ("/pyc, /pyc web", "Desktop GUI or WebUI"),
        ("/webui, /web", "llama.cpp WebAgent gateway"),
        ("/tui", "Textual UI"),
        ("/v \\[auto], /voice", "Voice to text"),
        ("/tts", "Text out loud"),
        ("/py \\[code_or_cmd]", "Toggle or execute via IPython"),
        ("/box \\[1-5]", "Box style preset"),
        ("/task \\[goal]", "Autonomous task loop"),
        ("/t \\[N|show|hide]", "Set reasoning budget or show/hide"),
        ("/g, /yolo", "Toggle confirmation gates (YOLO / autonomous mode)"),
        ("/m", "Toggle database memory"),
        ("/stats", "Generation speed stats"),
        ("/tok", "Context token usage"),
        ("/sync", "Sync index"),
        ("/clear, /c", "Soft clear active chat history"),
        ("/reset, /purge", "Hard reset (.agent & database purge)"),
        ("/s <query>, /s off", "Skills"),
        ("-save <tag>", "Save session checkpoint"),
        ("-load", "Load or clone checkpoint"),
        ("/f, /tk, /b, /a", "Follow-up, Thinking, Brainstorm, or All"),
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


def select_workspace_profile(workspace_name: str) -> tuple[str, bool, bool]:
    """Renders the workspace profile selector menu with dynamic custom profiles, YOLO, and Index-Map toggles."""
    custom_dir = os.path.join(CFG_DIR, "skills", "profiles", "custom")
    custom_opts = []

    if os.path.isdir(custom_dir):
        for fname in sorted(os.listdir(custom_dir)):
            if fname.endswith(".md"):
                base_name = os.path.splitext(fname)[0]
                lbl = f"Custom {base_name.title()}" if base_name.lower() != "custom" else "Custom"
                custom_opts.append((f"custom/{base_name}", lbl, "~200t", None))

    if custom_opts:
        custom_opts[0] = (custom_opts[0][0], custom_opts[0][1], custom_opts[0][2], "Custom")

    standard_agents = [
        ("pi/pro",         "Pi Pro",         "~180t", "Agents"),
        ("claude/pro",     "Claude Pro",     "~190t", None),
        ("hermes/pro",     "Hermes Pro",     "~180t", None),
        ("pi/pro-map",     "Pi Pro-Map",     "~280t", None),
        ("claude/pro-map", "Claude Pro-Map", "~290t", None),
        ("hermes/pro-map", "Hermes Pro-Map", "~280t", None),

        ("pi/py-pro",         "Pi Py-Pro",         "~200t", "Py"),
        ("claude/py-pro",     "Claude Py-Pro",     "~210t", None),
        ("hermes/py-pro",     "Hermes Py-Pro",     "~200t", None),
        ("pi/py-pro-map",     "Pi Py-Pro-Map",     "~300t", None),
        ("claude/py-pro-map", "Claude Py-Pro-Map", "~310t", None),
        ("hermes/py-pro-map", "Hermes Py-Pro-Map", "~300t", None),
    ]

    options = custom_opts + standard_agents

    sys.stderr.write(
        f"\n\033[1;36m[ai init]\033[0m Select default Agent Profile for workspace \033[1;33m{workspace_name}\033[0m:\n\n\033[?25l"
    )
    sys.stderr.flush()

    current_idx, is_yolo, use_map, num_opts = 0, False, False, len(options)
    last_rendered_lines = 0

    try:
        while True:
            if last_rendered_lines > 0:
                sys.stderr.write(f"\033[{last_rendered_lines}A\r\033[J")

            lines_count = 0
            sub_idx = 1
            for idx, (k, lbl, d, cat) in enumerate(options):
                if cat or k in ("pi/pro", "pi/pro-map", "pi/py-pro", "pi/py-pro-map"):
                    sub_idx = 1

                if idx > 0 and (cat or k in ("pi/pro-map", "pi/py-pro-map")):
                    sys.stderr.write("\r\x1b[K\n")
                    lines_count += 1

                if cat:
                    dashes = "─" * max(5, 30 - len(cat))
                    sys.stderr.write(f"\r\x1b[K\033[1;36m  ─── {cat} {dashes}\033[0m\n")
                    lines_count += 1

                if idx == current_idx:
                    sys.stderr.write(
                        f"\r\x1b[K\033[1;32m  ❯ {sub_idx:2d}. {lbl:<20}\033[0m \033[1;36m({d})\033[0m\n"
                    )
                else:
                    sys.stderr.write(
                        f"\r\x1b[K\033[37m    {sub_idx:2d}. {lbl:<20}\033[0m \033[2m({d})\033[0m\n"
                    )
                lines_count += 1
                sub_idx += 1

            yolo_badge = "\033[1;33m[ON]\033[0m" if is_yolo else "\033[90m[OFF]\033[0m"
            map_badge = "\033[1;32m[ON]\033[0m" if use_map else "\033[90m[OFF]\033[0m"
            sys.stderr.write(
                f"\r\x1b[K\n\r\x1b[K\033[2m  :: ↵ select  ↑/↓ navigate  Tab: YOLO {yolo_badge}\033[2m  m: Map {map_badge}\033[2m  Esc: {options[0][0]}\033[0m"
            )
            lines_count += 1
            sys.stderr.flush()

            last_rendered_lines = lines_count

            char = get_key()
            if char in ("\t", "y", "Y"):
                is_yolo = not is_yolo
            elif char in ("m", "M"):
                use_map = not use_map
            elif char in ("\x03", "\x1b"):
                key, label = options[0][0], options[0][1]
                sys.stderr.write(
                    f"\x1b[{last_rendered_lines}A\r\x1b[J\033[1;32m✓ Profile set to: {label}{' (Autonomous YOLO)' if is_yolo else ''}{' [Map: ON]' if use_map else ''}\033[0m\n\n"
                )
                sys.stderr.flush()
                return key, is_yolo, use_map
            elif char in ("\r", "\n", ""):
                key, label = options[current_idx][0], options[current_idx][1]
                sys.stderr.write(f"\x1b[{last_rendered_lines}A\r\x1b[J")
                if not is_yolo:
                    sys.stderr.write("\033[1;36mEnable Autonomous YOLO mode? [y/N]: \033[0m")
                    sys.stderr.flush()
                    c = get_key().lower()
                    sys.stderr.write("y\n" if c == "y" else "n\n")
                    sys.stderr.flush()
                    if c == "y":
                        is_yolo = True
                sys.stderr.write(
                    f"\033[1;32m✓ Profile set to: {label}{' (Autonomous YOLO)' if is_yolo else ''}{' [Map: ON]' if use_map else ''}\033[0m\n\n"
                )
                sys.stderr.flush()
                return key, is_yolo, use_map
            elif char in ("\x1b[A", "\x1b[B"):
                current_idx = (current_idx + (1 if char == "\x1b[B" else -1) + num_opts) % num_opts
    finally:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()
