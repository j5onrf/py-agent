#!/usr/bin/env python3
"""Production Minimal Textual TUI for Py Agent Engine"""

import base64
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request as urlreq
from collections.abc import Iterator
from contextlib import closing
from typing import Any

try:
    import uvloop; uvloop.install()
except (ImportError, NotImplementedError): pass

from rich.box import ROUNDED, Box
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Hit, Provider
from textual.containers import Horizontal, Vertical
from textual.theme import Theme
from textual.widgets import Footer, Input, Static

CFG_DIR = os.path.expanduser("~/.config/py-agent")
sys.path.append(os.path.join(CFG_DIR, "modules"))

import agent_cloud
import agent_core as core
import agent_ipython as ipython
import agent_skills as skills
import agent_tts as tts
import agent_tui_async as tui_async
import agent_ui as ui
import agent_voice as voice

CONTEXT_FILE = os.path.join(CFG_DIR, "ai-context.md")
SKILLS_DIR, SESSIONS_DIR = os.path.join(CFG_DIR, "skills"), os.path.join(CFG_DIR, "projects", "database")
LEFT_BAR = Box("▌   \n" * 8)
NO_BOX = Box("    \n" * 8)

TOKEN_RE = re.compile(r"[^\w\s]")
STOP_WORDS = frozenset({"is", "what", "it", "do", "any", "i", "have", "the", "a", "an", "on", "to", "for", "me", "you", "my", "your", "we", "us", "are", "about", "in", "how"})
CSI_U_REGEX = re.compile(r'(?:\x1b\[<|\x1b\[|\[<)?\d+;\d+;\d+[mM]|\x1b\[[0-9;]*[a-zA-Z~]|\x1b[\[\(\=][0-9;]*[a-zA-Z~]?')
ANSI_CLEAN_REGEX = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
REASONIX_STEP_RE = re.compile(r'^(?:\d+\.\s*|Step \d+:?\s*|Phase \d+:?\s*|\#{1,3}\s*)\*\*?([^\n\*:]+)\*\*?:?', re.IGNORECASE)
CLEAN_CODE_BLOCKS_RE = re.compile(r'```\n\s*\n+')
MULTI_NEWLINE_RE = re.compile(r'\n{3,}')
FINAL_ANSWER_RE = re.compile(r'^\s*Final Answer:\s*', re.IGNORECASE)
THINK_TAGS_RE = re.compile(r'<think>.*?</think>', re.DOTALL)

BASE_PROMPT_CHAT = "Active, natural conversational assistant."
BASE_PROMPT_AGENT = "Active local workspace developer agent."

_CACHED_CLIPBOARD_TOOL: list[str] | None = None


def format_dir_path(path: str) -> str:
    p = path.replace(os.path.expanduser("~"), "~")
    return p if len(p) <= 20 else f".../{os.path.basename(p.rstrip('/'))}"


def format_model_name(name: str, max_len: int = 18) -> str:
    if not name: return "Unknown"
    clean = name.strip()
    if len(clean) <= max_len: return clean
    base = clean.rsplit("/", 1)[-1]
    return f".../{base}" if len(base) <= max_len else f"{base[:(max_len-3)//2]}...{base[-(max_len-3)//2:]}"


def copy_to_clipboard(text: str) -> bool:
    global _CACHED_CLIPBOARD_TOOL
    if not text: return False
    try:
        sys.stdout.write(f"\x1b]52;c;{base64.b64encode(text.encode('utf-8')).decode('utf-8')}\x07")
        sys.stdout.flush()
    except OSError: pass
    tools = [_CACHED_CLIPBOARD_TOOL] if _CACHED_CLIPBOARD_TOOL else [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["pbcopy"], ["clip.exe"]]
    for tool in filter(None, tools):
        try:
            p = subprocess.Popen(tool, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            p.communicate(input=text.encode("utf-8"), timeout=1.0)
            if p.returncode == 0:
                _CACHED_CLIPBOARD_TOOL = tool
                return True
        except (OSError, subprocess.SubprocessError): continue
    return True


def _format_tui_reasonix_text(text: str, theme: str = "code1") -> Text:
    badge_style = {"code1": "bold #89b4fa", "code2": "bold #ff9e64", "dark": "bold cyan", "mono": "bold white"}.get(theme, "bold cyan")
    res, last_was_empty = Text(), False
    for line in text.splitlines():
        if not (clean_strip := line.strip()):
            if not last_was_empty: res.append("\n"); last_was_empty = True
            continue
        last_was_empty = False
        if m := REASONIX_STEP_RE.match(clean_strip): res.append(f"{m.group(0).strip()}\n", style=badge_style)
        else: res.append(f"{line}\n", style="italic dim")
    res.rstrip()
    return res


code1_theme = Theme(name="code1", primary="#89b4fa", secondary="#a6adc8", accent="#89b4fa", background="#11121d", surface="#161726", panel="#1b1c2b")
code2_theme = Theme(name="code2", primary="#ff9e64", secondary="#e0af68", accent="#ff9e64", background="#11121d", surface="#161726", panel="#1b1c2b")
mono_theme = Theme(name="mono", primary="#ffffff", secondary="#a0a0a0", accent="#ffffff", background="#000000", surface="#0d0d0d", panel="#121212")
dark_theme = Theme(name="dark", primary="#555555", secondary="#b0b0b0", accent="#ffffff", background="#121212", surface="#1c1c1c", panel="#242424")


class FooterToggle(Static):
    def on_click(self) -> None:
        if hasattr(self.app, "action_toggle_footer"): self.app.action_toggle_footer()

class ImageButton(Static):
    def on_click(self) -> None:
        if hasattr(self.app, "action_prompt_image_url"): self.app.action_prompt_image_url()

class CloseCardButton(Static):
    def on_click(self) -> None:
        if hasattr(self.app, "action_close_tips_card"): self.app.action_close_tips_card()


class Message(Static):
    def __init__(self, sender: str, content: Any) -> None:
        super().__init__()
        self.sender, self.content = sender, content
        self._cached_render = None
        self._cached_theme = None
        self._cached_compact = None
        self._cached_borders = None

    def update_content(self, new_content: Any) -> None:
        self.content = new_content
        self._cached_render = None
        self.refresh()

    def render(self) -> Any:
        app_theme = getattr(self.app, "theme", "code1")
        compact_state = getattr(self.app, "compact_mode", 0)
        borders_on = getattr(self.app, "borders_enabled", True)

        if (self._cached_render is not None and 
            self._cached_theme == app_theme and 
            self._cached_compact == compact_state and 
            self._cached_borders == borders_on):
            return self._cached_render

        is_dark = getattr(self.app, "is_dark_theme", True)
        self.styles.color = "#c8d3f5" if ("code" in app_theme and is_dark) else None
        self.styles.margin = (1, 2, 0, 0) if compact_state == 0 else (0, 2, 0, 0)
        u_style = "bold #888888" if app_theme in ("mono", "grok") else ("bold #89b4fa" if "code" in app_theme else ("bold #0265dc" if not is_dark else "bold cyan"))
        code_fmt = "ansi_dark" if is_dark else "ansi_light"

        bg_col = "#0d0d0d" if app_theme in ("mono", "grok") else ("#1a1a1a" if app_theme == "dark" else ("#1b1c2b" if is_dark else "#f0f0f4"))
        border_col = getattr(self.app, "border_accent", "#89b4fa")

        if self.sender == "User":
            raw_text = self.content if isinstance(self.content, str) else next((i["text"] for i in self.content if isinstance(i, dict) and i.get("type") == "text"), "[Multimodal Payload]")
            text = raw_text.split("User Question:", 1)[-1].strip() if "User Question:" in raw_text else raw_text
            if compact_state == 0:
                user_txt_col = "white" if app_theme in ("mono", "grok", "dark") else ("#303446" if not is_dark else "#c8d3f5")
                res = Panel(Text(text, style=user_txt_col), box=LEFT_BAR, border_style=border_col, style=f"on {bg_col}", padding=(0, 2))
            else: res = Text(text, style=u_style)
        else:
            text = str(self.content or "")
            show_think = os.environ.get("AI_SHOW_THINKING", "1") == "1"
            if "<think>" in text:
                before, after = text.split("<think>", 1)
                items = []
                if before.strip(): items.append(Markdown(before.strip(), code_theme=code_fmt))

                if "</think>" in after:
                    think, rest = after.split("</think>", 1)
                    if show_think and think.strip():
                        items.append(Panel(_format_tui_reasonix_text(think.strip(), app_theme), title="⚙", title_align="left", border_style=border_col, box=ROUNDED, expand=True))
                    if rest.strip():
                        clean_rest = MULTI_NEWLINE_RE.sub('\n\n', CLEAN_CODE_BLOCKS_RE.sub('```\n', rest.strip()))
                        items.append(Markdown(clean_rest, code_theme=code_fmt))
                    body = Group(*items) if items else Text("Thinking...", style="italic dim")
                else:
                    think = after.strip()
                    if show_think and think:
                        items.append(Panel(_format_tui_reasonix_text(think, app_theme), title="⚙ Thinking...", title_align="left", border_style=border_col, box=ROUNDED, expand=True))
                    else: items.append(Text("Thinking...", style="italic dim"))
                    body = Group(*items)
            else:
                clean_text = MULTI_NEWLINE_RE.sub('\n\n', CLEAN_CODE_BLOCKS_RE.sub('```\n', text.strip()))
                body = Markdown(clean_text, code_theme=code_fmt) if clean_text else Text("...", style="italic dim")

            if compact_state == 0:
                box_type = ROUNDED if borders_on else NO_BOX
                b_style = ("dim " + border_col) if borders_on else border_col
                res = Panel(body, box=box_type, border_style=b_style, style=f"on {bg_col}", padding=(0, 2))
            else:
                res = body

        self._cached_render = res
        self._cached_theme = app_theme
        self._cached_compact = compact_state
        self._cached_borders = borders_on
        return res


class AgentCommandProvider(Provider):
    async def search(self, query: str) -> Iterator[Hit]:
        m = self.matcher(query)
        cmds = [
            ("Copy Last Response", "copy_last_response", "Copy latest agent response"),
            ("Copy Entire Chat Page", "copy_entire_chat", "Copy complete conversation transcript"),
            ("Cycle Theme", "cycle_theme", "Cycle through color themes"),
            ("Toggle Sidebar", "toggle_sidebar", "Show or hide metadata panel"),
            ("Toggle Compact Mode", "toggle_compact", "Toggle spacing layouts"),
            ("Toggle Reasoning", "toggle_reasoning", "Enable or disable reasoning budget"),
            ("Toggle Mode (Plan/Build)", "toggle_plan_build", "Switch between Plan and Build modes"),
        ]
        for title, action, desc in cmds:
            if (score := m.match(title)) > 0:
                yield Hit(score, Text(title), lambda act=action: self.app.run_action(act), help=desc)


class LocalAITUI(App):
    ENABLE_COMMAND_PALETTE = True
    THEMES = ["code1", "code2", "dark", "mono"]

    @property
    def command_sources(self) -> set[Any]: return {AgentCommandProvider}

    @property
    def border_accent(self) -> str:
        t = str(getattr(self, "theme", "code1")).lower()
        if "mono" in t or "grok" in t: return "bright_white"
        if "dark" in t: return "bright_blue"
        if "code2" in t: return "#ff9e64"
        return "#89b4fa"

    @property
    def is_dark_theme(self) -> bool:
        return not any(kw in str(getattr(self, "theme", "code1")).lower() for kw in ["light", "latte", "day", "solarized-light", "dawn", "paper"])

    CSS = """
    Screen { background: $background; }
    #layout { height: 1fr; }
    #main-container { height: 100%; width: 1fr; background: transparent; overflow: hidden; }
    #chat-area { height: 1fr; width: 100%; background: transparent; overflow-y: scroll; overflow-x: hidden; padding: 0 0 1 2; scrollbar-size-vertical: 1; scrollbar-color: $panel; scrollbar-color-hover: $primary; scrollbar-color-active: $accent; scrollbar-gutter: stable; }
    #welcome-banner { margin-top: 1; margin-bottom: 1; margin-right: 2; }
    #input-pane { height: 3; border: none; background: $surface; padding: 0; margin: 0; align: left middle; }
    #input-bar { width: auto; height: 100%; color: $primary; padding: 0; margin: 0; }
    Input { width: 1fr; border: none; outline: none; background: transparent; height: 1; color: $text; padding: 0 2; margin-top: 1; }
    Input:focus { border: none; outline: none; }
    Input > .input--cursor { background: #ffffff; color: #000000; text-style: bold; }
    #input-toggle { width: auto; height: 1; margin-top: 2; color: $secondary; padding: 0 1; }
    #input-toggle:hover { color: $primary; text-style: bold; }
    #btn-image-url { width: auto; height: 1; color: $secondary; padding: 0 1; margin-top: 2; }
    #btn-image-url:hover { color: $primary; text-style: bold; }
    #sidebar { width: 30; height: 100%; background: $surface; border-left: solid $boost; padding: 1 1; align: left top; }
    Message { margin-top: 1; margin-right: 2; height: auto; max-width: 100%; overflow-x: hidden; }
    Message:first-child { margin-top: 0; margin-right: 2; }
    #chat-area.zero-spacing Message { margin-top: 0; }
    .sidebar-section { height: auto; border-bottom: none; padding-bottom: 1; margin-bottom: 1; }
    .sidebar-label { color: $primary; text-style: bold; margin-bottom: 0; }
    .sidebar-val { color: $text; margin-bottom: 0; }
    .sys-notice { margin-top: 1; margin-bottom: 0; }
    .theme-notice { margin-top: 1; margin-bottom: 0; color: #ffffff; text-style: bold; }
    #card-tips { background: $panel; padding: 1; margin-top: 1; }
    #card-tips-header { height: 1; width: 100%; }
    #lbl-tips-title { width: 1fr; color: $primary; text-style: bold; }
    #btn-close-tips { width: auto; color: $secondary; text-style: bold; }
    #btn-close-tips:hover { color: $error; text-style: bold; }
    #lbl-tips-body { color: $text; margin-top: 1; }
    #footer-bar { dock: bottom; height: 1; width: 100%; background: $surface; }
    #footer-keys { width: 100%; height: 1; }
    #sidebar.blue-sidebar .sidebar-val { color: #c8d3f5; }
    #sidebar.blue-sidebar #lbl-tips-body { color: #c8d3f5; }
    """

    BINDINGS = [
        Binding("tab", "toggle_plan_build", "Toggle Mode", show=False),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
        Binding("ctrl+f", "toggle_borders", "Borders", show=True),
        Binding("ctrl+g", "toggle_compact", "Compact", show=True),
        Binding("ctrl+r", "toggle_reasoning", "Reasoning", show=True),
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
        Binding("ctrl+i", "prompt_image_url", "Image", show=True),
        Binding("ctrl+o", "copy_last_response", "Copy Out", show=True),
        Binding("ctrl+c", "stop_generation", "Stop Out", show=True),
        Binding("pageup", "scroll_page_up", "Page Up", show=False),
        Binding("pagedown", "scroll_page_down", "Page Down", show=False),
        Binding("shift+up", "scroll_up", "Scroll Up", show=False),
        Binding("shift+down", "scroll_down", "Scroll Down", show=False),
        Binding("ctrl+q", "quit", "Exit TUI", show=False),
        Binding("escape", "quit", "Exit TUI", show=False),
    ]

    def watch_theme(self, theme: str) -> None:
        core.save_state("tui_theme", theme)
        self.update_welcome_banner()
        self.set_skill(self.active_skill)

        try:
            sidebar = self.query_one("#sidebar")
            if theme in ("code1", "code2"):
                sidebar.add_class("blue-sidebar")
            else:
                sidebar.remove_class("blue-sidebar")
        except Exception:
            pass

        if hasattr(self, "chat_area"):
            for child in self.chat_area.children:
                if isinstance(child, Message): child.refresh(layout=True)
            self.chat_area.refresh(layout=True)

    def __init__(self, workspace_path: str, model_name: str, is_agent: bool | None = None) -> None:
        super().__init__()
        self.workspace_path, self.model_name = workspace_path, model_name
        self.safe_name = core.workspace_safe_name(workspace_path)
        agent_dir, cfg_file = os.path.join(workspace_path, ".agent"), os.path.join(workspace_path, ".agent", "config.json")

        if is_agent is not None: self.is_agent = is_agent
        elif "AI_IS_AGENT" in os.environ: self.is_agent = os.environ["AI_IS_AGENT"].lower() in ("1", "true", "yes")
        else: self.is_agent = (os.path.abspath(workspace_path) != os.path.abspath(os.path.expanduser("~"))) and (os.path.exists(agent_dir) or "/projects/" in workspace_path)

        if not self.is_agent: self.agent_mode, self.gates_enabled = "Disabled", True
        else:
            env_gates = os.environ.get("AI_CONFIRM_GATES")
            is_yolo = (env_gates == "0") if env_gates is not None else core.get_state("yolo_mode", False)
            self.agent_mode, self.gates_enabled = "Build" if is_yolo else "Plan", not is_yolo
            os.environ["AI_CONFIRM_GATES"] = "0" if is_yolo else "1"

        self.gate_auth_event = threading.Event()
        self.gate_auth_result = self.entering_gate_authorization = self.entering_image_url = False
        self.current_gate_prompt = self.pending_image_url = ""
        self.spell_enabled, self.pending_skill_prefix = True, None

        inherited_skill = os.environ.get("AI_ACTIVE_SKILL")
        if not inherited_skill or inherited_skill.lower() in ("default", "none", ""):
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        inherited_skill = data.get("profile") or data.get("skill")
                except (OSError, json.JSONDecodeError): pass
        if not inherited_skill or inherited_skill.lower() in ("default", "none", ""):
            inherited_skill = "default" if self.is_agent else "chat"

        skills_split = [s for s in inherited_skill.split() if s]
        self.base_skill = skills_split[0] if skills_split else ("default" if self.is_agent else "chat")
        self.on_demand_skill = skills_split[1] if len(skills_split) > 1 else None
        self.active_skill = f"{self.base_skill} {self.on_demand_skill}".strip() if self.on_demand_skill else self.base_skill

        self.memory_active, self.db_turns, self.tpm_count = core.get_state("memory_active", False), 0, 0
        self.refresh_db_counts()

        raw_c = core.get_state("compact_mode", 0)
        self.compact_mode = int(raw_c) if isinstance(raw_c, (int, bool)) else 0
        self.reasoning_active, self.reasoning_budget, self.entering_reasoning_budget = core.get_state("reasoning_active", False), core.get_state("reasoning_budget", 500), False

        cli_hist = os.environ.get("AI_SESSION_HISTORY")
        try: self.history: list[dict[str, Any]] = json.loads(cli_hist) if cli_hist else []
        except (json.JSONDecodeError, TypeError, ValueError): self.history = []

        self.generation_cancelled, self.active_response, self.stats_turns = False, None, 0
        self.borders_enabled = core.get_state("tui_borders_enabled", True)
        self.footer_hidden, self.sidebar_hidden, self.tips_card_hidden = core.get_state("footer_hidden", True), core.get_state("sidebar_hidden", False), core.get_state("tips_card_hidden", False)

    def on_unmount(self) -> None:
        self.gate_auth_result = False
        self.gate_auth_event.set()
        if self.active_response:
            try: self.active_response.close()
            except (AttributeError, OSError): pass

    def _safe_remove_banner(self) -> None:
        for node in self.query("#welcome-banner"):
            try: node.remove()
            except Exception: pass

    def notify(self, text: str, sys_prefix: bool = True, css_class: str = "sys-notice") -> None:
        self.chat_area.mount(Static(f"[dim white][sys] {text}[/dim white]" if sys_prefix else text, classes=css_class))
        self.chat_area.scroll_end(animate=False)

    def set_skill(self, skill_name: str) -> None:
        self.active_skill = skill_name
        t = getattr(self, "theme", "code1")
        styles = {"code1": ("#1b2b3b", "#89b4fa"), "code2": ("#3b2b1b", "#ff9e64"), "mono": ("#222222", "#ffffff"), "dark": ("#333333", "#e0e0e0")}
        bg, fg = styles.get(t, ("#1b2b3b", "#89b4fa"))
        if hasattr(self, "lbl_skill"): self.lbl_skill.update(f"[dim]Skill[/dim]   [bold {fg} on {bg}] {skill_name} [/]")

    def set_mode(self, mode_name: str) -> None:
        self.agent_mode = mode_name
        if hasattr(self, "lbl_mode"): self.lbl_mode.update(f"[dim]Mode[/dim]    {mode_name}")

    def set_reasoning(self, text: str) -> None:
        if hasattr(self, "lbl_reasoning"): self.lbl_reasoning.update(f"[dim]Reasoning[/dim] {text}")

    def action_prompt_image_url(self) -> None:
        if getattr(self, "entering_image_url", False):
            self.entering_image_url, self.pending_image_url, self.chat_input.placeholder = False, "", "Ask your agent anything..."
            self.notify("[dim]Image input cancelled.[/dim]", sys_prefix=False)
        else:
            self.entering_image_url, self.pending_image_url, self.chat_input.placeholder = True, "", "Enter Image URL (e.g. https://.../photo.png):"
        self.chat_input.focus()

    def on_key(self, event) -> None:
        if event.key == "tab":
            self.action_toggle_plan_build()
            event.prevent_default(); event.stop()

    def refresh_db_counts(self) -> None:
        db_path = os.path.join(SESSIONS_DIR, f"{self.safe_name}.db")
        if not os.path.exists(db_path): self.db_turns = self.tpm_count = 0; return
        try:
            with closing(sqlite3.connect(db_path, timeout=2)) as conn:
                cur = conn.cursor()
                try:
                    row = cur.execute("SELECT COUNT(*) FROM turns WHERE workspace = ?", (self.safe_name,)).fetchone()
                    self.db_turns = row[0] if row else 0
                except sqlite3.Error: pass
                try:
                    trow = cur.execute("SELECT COUNT(*) FROM tpm_memories").fetchone()
                    self.tpm_count = trow[0] if trow else 0
                except sqlite3.Error: pass
        except sqlite3.Error: pass

    def ensure_system_context(self) -> None:
        if not any(m.get("role") == "system" for m in self.history):
            s_list = [s.lstrip("-").lower() for s in self.active_skill.split() if s] if (self.active_skill and self.active_skill.lower() not in ("default", "none")) else []
            s_content = skills.load_skill_content(" ".join(s_list), SKILLS_DIR, CFG_DIR) if s_list else ""

            if self.is_agent:
                sys_p = (s_content or BASE_PROMPT_AGENT) + f"\n\n### ACTIVE PROJECT WORKSPACE:\nYour active project root directory is: {self.workspace_path}\nCapabilities: read_symbol, trace_symbol, blast_radius, find_symbol, architecture_overview, read_file, edit_file, write_file, list_dir, run_command.\n"
                try:
                    if os.path.exists(self.workspace_path):
                        if map_files := [f for f in os.listdir(self.workspace_path) if f.startswith("index-map-") and f.endswith(".txt")]:
                            with open(os.path.join(self.workspace_path, map_files[0]), "r", encoding="utf-8", errors="ignore") as mf:
                                if cmap := mf.read().strip(): sys_p += f"\n\n### CODESPACE MAP:\n{cmap}\n"
                except (OSError, UnicodeDecodeError): pass
            else:
                sys_p = s_content or BASE_PROMPT_CHAT

            self.history.insert(0, {"role": "system", "content": sys_p})
            if self.is_agent and len(self.history) == 1: self.history.append({"role": "assistant", "content": "Agent: Workspace loaded. Awaiting instructions."})

    def get_db_status_string(self) -> str:
        return "stateless" if not self.is_agent else (f"active • {self.tpm_count} facts" if self.memory_active else "disabled")

    def update_welcome_banner(self) -> None:
        try:
            if self.query("#welcome-banner"):
                t = Table(show_header=False, box=None, padding=(0, 2), expand=False)
                cmd_style = "bold #89b4fa" if "code" in self.theme else ("bold #0265dc" if not self.is_dark_theme else "bold cyan")
                t.add_column("Key", style=cmd_style, justify="left"); t.add_column("Action", style="default")
                for k, a in [("Tab", "Plan / Build Mode"), ("Ctrl+B", "Toggle Sidebar Panel"), ("Ctrl+T", "Cycle Themes"), ("Ctrl+O", "Copy Latest Response"), ("▲ Show", "Toggle Bottom Shortcut Bar"), ("/help", "View All Commands")]:
                    t.add_row(k, a)
                self.query_one("#welcome-banner", Static).update(Panel(t, title=" ∿ PyTUI ", title_align="left", border_style=self.border_accent, box=ROUNDED, expand=False))
        except Exception: pass

    def compose(self) -> ComposeResult:
        with Horizontal(id="layout"):
            with Vertical(id="main-container"):
                with Vertical(id="chat-area"): yield Static(id="welcome-banner")
                with Horizontal(id="input-pane"):
                    yield Static("▌\n▌\n▌", id="input-bar")
                    yield Input(placeholder="Ask your agent anything...", id="chat-input")
                    yield FooterToggle("▲ Show", id="input-toggle")

            with Vertical(id="sidebar"):
                with Vertical(classes="sidebar-section"):
                    yield Static("MODEL & SESSION", classes="sidebar-label")
                    yield Static(f"[dim]Model[/dim]   {format_model_name(self.model_name)}", id="lbl-model", classes="sidebar-val")
                    yield Static(f"[dim]Dir[/dim]     {format_dir_path(self.workspace_path)}", id="lbl-dir", classes="sidebar-val")
                    yield Static(f"[dim]Skill[/dim]   {self.active_skill}", id="lbl-skill", classes="sidebar-val")
                    yield Static(f"[dim]Mode[/dim]    {self.agent_mode}", id="lbl-mode", classes="sidebar-val")
                    yield Static("[dim]Harness[/dim] Native Tools", id="lbl-harness", classes="sidebar-val")
                    yield Static("[dim]Image[/dim]   None", id="lbl-image", classes="sidebar-val")

                with Vertical(classes="sidebar-section"):
                    yield Static("SETTINGS", classes="sidebar-label")
                    yield Static("[dim]Reasoning[/dim] Disabled", id="lbl-reasoning", classes="sidebar-val")
                    yield Static("[dim]Voice[/dim]   Disabled", id="lbl-voice", classes="sidebar-val")
                    yield Static("[dim]TTS[/dim]     Disabled", id="lbl-tts", classes="sidebar-val")

                with Vertical(classes="sidebar-section"):
                    yield Static("CONTEXT & MEMORY", classes="sidebar-label")
                    yield Static(f"[dim]DB State[/dim]  {self.get_db_status_string()}", id="lbl-database", classes="sidebar-val")
                    yield Static("[dim]Turns[/dim]     0 @ -- t/s", id="lbl-stats", classes="sidebar-val")

                with Vertical(id="card-tips"):
                    with Horizontal(id="card-tips-header"):
                        yield Static("Quick Tips", id="lbl-tips-title")
                        yield CloseCardButton("×", id="btn-close-tips")
                    yield Static("Tab: Switch Mode\nCtrl+B: Sidebar\nCtrl+F: Borders\nCtrl+G: Compact\nCtrl+T: Themes\n/tok: Context\n/py: Harness\n/v: Voice To Text\n/tts: Text To Speech\n/task: Goal\n/help: Commands", id="lbl-tips-body")

        with Horizontal(id="footer-bar"): yield Footer(id="footer-keys")

    def action_close_tips_card(self) -> None:
        self.tips_card_hidden = True
        core.save_state("tips_card_hidden", True)
        try: self.query_one("#card-tips", Vertical).display = False
        except (KeyError, AttributeError): pass

    def on_mount(self) -> None:
        if hasattr(self, "register_theme"):
            for t in (code1_theme, code2_theme, mono_theme, dark_theme):
                try: self.register_theme(t)
                except (ValueError, TypeError, KeyError): pass

        try: self.theme = "mono" if core.get_state("tui_theme", "code1") == "grok" else core.get_state("tui_theme", "code1")
        except (KeyError, ValueError, TypeError): pass

        self.chat_area = self.query_one("#chat-area", Vertical)
        if self.compact_mode == 2: self.chat_area.add_class("zero-spacing")

        self.chat_input = self.query_one("#chat-input", Input)
        self.lbl_skill, self.lbl_mode = self.query_one("#lbl-skill", Static), self.query_one("#lbl-mode", Static)
        self.lbl_harness, self.lbl_reasoning = self.query_one("#lbl-harness", Static), self.query_one("#lbl-reasoning", Static)
        self.lbl_database, self.lbl_stats = self.query_one("#lbl-database", Static), self.query_one("#lbl-stats", Static)
        self.lbl_voice, self.lbl_tts, self.lbl_image = self.query_one("#lbl-voice", Static), self.query_one("#lbl-tts", Static), self.query_one("#lbl-image", Static)

        if hasattr(ipython, "is_ipython_enabled"):
            self.lbl_harness.update("[dim]Harness[/dim] " + ("NOOA IPython" if ipython.is_ipython_enabled() else "Native Tools"))

        if hasattr(voice, "is_bridge_running"):
            is_act = voice.is_bridge_running()
            auto_st = core.get_state().get("voice_auto_submit", True)
            self.lbl_voice.update(f"[dim]Voice[/dim]   {'Active (auto)' if (is_act and auto_st) else ('Active (edit)' if is_act else 'Disabled')}")

        if hasattr(tts, "is_tts_enabled"):
            self.lbl_tts.update(f"[dim]TTS[/dim]     {'Active' if tts.is_tts_enabled() else 'Disabled'}")

        os.environ["AI_SHOW_THINKING"] = "1" if core.get_state("show_thinking", True) else "0"
        self.set_skill(self.active_skill); self.set_mode(self.agent_mode)

        try:
            sidebar = self.query_one("#sidebar")
            if getattr(self, "theme", "code1") in ("code1", "code2"):
                sidebar.add_class("blue-sidebar")
            else:
                sidebar.remove_class("blue-sidebar")
        except Exception:
            pass

        self.set_reasoning(f"{self.reasoning_budget} tokens" if self.reasoning_active else "Disabled")
        self.update_welcome_banner(); self.chat_input.cursor_blink = True
        self.update_footer_visibility(); self.update_sidebar_visibility()

        if self.tips_card_hidden:
            try: self.query_one("#card-tips", Vertical).display = False
            except (KeyError, AttributeError): pass

        if len(self.history) > 1:
            self._safe_remove_banner()
            for msg in self.history:
                r, c = msg.get("role"), msg.get("content")
                if r == "user" and c: self.chat_area.mount(Message("User", c))
                elif r == "assistant" and c: self.chat_area.mount(Message("Agent", c))

        self.run_worker(tui_async.watch_workspace_changes(self), exclusive=False)
        self.run_worker(tui_async.start_subagent_ipc_hub(self), exclusive=False)
        self.chat_input.focus()

    def action_toggle_plan_build(self) -> None:
        if not self.is_agent: return
        self.agent_mode, self.gates_enabled = ("Build", False) if self.agent_mode == "Plan" else ("Plan", True)
        is_yolo = not self.gates_enabled
        os.environ["AI_CONFIRM_GATES"] = "0" if is_yolo else "1"
        core.save_state("yolo_mode", is_yolo)
        self.set_mode(self.agent_mode)

    def on_input_changed(self, event: Input.Changed) -> None:
        if (clean := CSI_U_REGEX.sub('', event.value)) != event.value: event.input.value = clean

    def update_stats_ui(self, turns: int, tps: float, elapsed: float) -> None:
        if hasattr(self, "lbl_stats"): self.lbl_stats.update(f"[dim]Turns[/dim]     {turns} @ {f'{tps:.1f} t/s' if tps > 0 else '-- t/s'}")

    def action_scroll_page_up(self) -> None: self.chat_area.scroll_page_up(animate=False)
    def action_scroll_page_down(self) -> None: self.chat_area.scroll_page_down(animate=False)
    def action_scroll_up(self) -> None: self.chat_area.scroll_up(animate=False)
    def action_scroll_down(self) -> None: self.chat_area.scroll_down(animate=False)

    def action_copy_last_response(self) -> None:
        if last := next((m.get("content", "") for m in reversed(self.history) if m.get("role") == "assistant"), ""):
            copy_to_clipboard(last.split("</think>", 1)[-1].strip() if "</think>" in last else last)
            self.notify("Copied latest agent response to clipboard.")
        else: self.notify("No response available to copy yet.")

    def action_copy_entire_chat(self) -> None:
        if transcript := [f"❯ USER: {m['content']}" if m.get("role") == "user" else f"AGENT:\n{THINK_TAGS_RE.sub('', m['content']).strip()}" for m in self.history if m.get("content") and m.get("role") != "system"]:
            copy_to_clipboard("\n\n".join(transcript))
            self.notify("Copied entire session transcript to clipboard.")
        else: self.notify("No transcript available to copy yet.")

    async def handle_view_file(self, file_path: str) -> None:
        full_p = os.path.expanduser(file_path) if os.path.isabs(os.path.expanduser(file_path)) else os.path.join(self.workspace_path, file_path)
        if os.path.isfile(full_p):
            try:
                with open(full_p, "r", encoding="utf-8", errors="ignore") as f: content = f.read(12000)
                self.history.append({"role": "user", "content": f"[FILE LOADED: {file_path}]\n```\n{content}\n```"})
                self.notify(f"Loaded file content into active context: [bold]{file_path}[/bold]")
            except (OSError, UnicodeDecodeError) as e: self.notify(f"[bold red]Error reading file: {e}[/bold red]", sys_prefix=False)
        else: self.notify(f"[bold red]File not found: {file_path}[/bold red]", sys_prefix=False)

    async def handle_task_command(self, task_args: str = "") -> None:
        self._safe_remove_banner()
        self.ensure_system_context()
        goal = task_args.strip('"\': ') or "TASK.md spec"
        display_cmd = f"/task \"{goal}\""
        await self.chat_area.mount(Message("User", display_cmd))

        assistant_msg = Message("Agent", f"[task] Executing Goal loop: [italic]{goal}[/italic]...")
        await self.chat_area.mount(assistant_msg)
        self.chat_area.scroll_end(animate=False)

        def _run_task_sub():
            ralph_bin = os.path.join(CFG_DIR, "tools", "loop", "ralph.py")
            if os.path.exists(ralph_bin):
                try:
                    env = {**os.environ, "AI_WORKSPACE_PATH": self.workspace_path}
                    res = subprocess.run([sys.executable, ralph_bin, task_args], cwd=self.workspace_path, capture_output=True, text=True, timeout=300, env=env)
                    out = (res.stdout or res.stderr or "").strip()
                    
                    plain_text = ANSI_CLEAN_REGEX.sub('', out.replace('\r', '\n'))
                    clean_lines = []
                    for line in plain_text.splitlines():
                        l_strip = line.strip()
                        if not l_strip or (("Working..." in l_strip or any(c in l_strip for c in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")) and "working •" not in l_strip):
                            continue
                        clean_lines.append(l_strip)

                    formatted_blocks = []
                    for line in clean_lines:
                        if line.startswith("[loop] Starting autonomous execution"):
                            m = re.search(r'in\s+(\S+)\s+\(max\s+(\d+)\s+turns\)\s+::\s+Goal:\s*(.*)', line)
                            if m:
                                formatted_blocks.append(f"> **Goal:** {m.group(3)}\n> **Workspace:** `{m.group(1)}` • **Limit:** `{m.group(2)} turns`\n")
                            else:
                                formatted_blocks.append(f"> **Goal:** {line}\n")
                        elif m_turn := re.search(r'\[loop turn (\d+)/(\d+)\]', line):
                            formatted_blocks.append(f"\n#### Step {m_turn.group(1)} / {m_turn.group(2)}")
                        elif "working •" in line:
                            t_name = line.split("working •")[-1].strip()
                            formatted_blocks.append(f"* Executing tool: `{t_name}`")
                        elif line.startswith("✔ Done") or line.startswith("Done"):
                            timing = f" ({line.split('(')[-1]}" if "(" in line else ""
                            formatted_blocks.append(f"  *Finished step*{timing}")
                        elif "Task completed" in line or "[ok]" in line:
                            m_ok = re.search(r'in (\d+) turn', line)
                            turns_str = f" in {m_ok.group(1)} turns" if m_ok else ""
                            formatted_blocks.append(f"\n---\n### ✔ Task Completed{turns_str}")
                        else:
                            formatted_blocks.append(line)

                    clean_out = "\n".join(formatted_blocks)
                    formatted = f"### Task Execution Report\n\n{clean_out or '✔ Task completed successfully.'}"
                    
                    self.call_from_thread(assistant_msg.update_content, formatted)
                    self.history.append({"role": "user", "content": display_cmd})
                    self.history.append({"role": "assistant", "content": clean_out or "Task complete."})
                    self.refresh_db_counts()
                except (OSError, subprocess.SubprocessError, TimeoutError) as e: 
                    self.call_from_thread(assistant_msg.update_content, f"[red][sys] Task loop error: {e}[/red]")
            else: 
                self.call_from_thread(assistant_msg.update_content, "[red][sys] tools/loop/ralph.py script not found.[/red]")

        self.run_worker(_run_task_sub, thread=True)

    async def handle_slash_command(self, cmd: str) -> None:
        self._safe_remove_banner()

        parts = cmd.split(maxsplit=1)
        root, args = parts[0].lower(), parts[1] if len(parts) > 1 else ""

        if root in ("/help", "/h"):
            t = Table(show_header=False, box=None, padding=(0, 1), expand=False)
            cmd_style = "bold #89b4fa" if "code" in self.theme else ("bold #0265dc" if not self.is_dark_theme else "bold cyan")
            t.add_column("Command", style=cmd_style); t.add_column("Description", style="default")
            for c, d in [("/help, /h", "Help"), ("/v", "Voice to text"), ("/tts", "Text to speech"), ("/py", "NOOA IPython"), ("Tab", "Plan/Build"), ("/task", "Task Loop"), ("/copy", "Copy page"), ("/m", "Memory"), ("/clear, /c", "Soft clear chat"), ("/reset", "Hard workspace reset"), ("/tok", "Tokens"), ("/sync", "Sync index"), ("/s <q>", "Skill"), ("/t <toks>", "Reasoning"), ("/f, /tk, /b, /a", "Presets"), ("file <path>", "Load File"), ("exit, quit, q", "Exit")]:
                t.add_row(c, d)
            border_col = "bright_white" if self.theme in ("mono", "grok") else self.border_accent
            await self.chat_area.mount(Static(Group(Text(""), Panel(t, title="Commands", title_align="left", border_style=border_col, box=ROUNDED, expand=False))))
            self.chat_area.scroll_end(animate=False)

        elif root == "/theme":
            if args:
                t_arg = args.strip().lower()
                if t_arg in self.THEMES:
                    self.theme = t_arg
                    self.notify(f"Theme switched to [bold]{self.theme}[/bold].", css_class="theme-notice")
                else: self.notify(f"Unknown theme '{t_arg}'. Options: {', '.join(self.THEMES)}")
            else: self.action_cycle_theme()

        elif root in ("/py", "/ipython"):
            if args:
                if not ipython.is_ipython_enabled():
                    ipython.toggle_ipython_mode(True)
                    if hasattr(self, "lbl_harness"): self.lbl_harness.update("[dim]Harness[/dim] NOOA IPython")
                    self.notify("NOOA IPython harness enabled.")
                    if "py-" not in self.active_skill:
                        self.notify(f"[yellow]Warning: Active skill '{self.active_skill}' is a classic JSON skill. Use a Py profile (e.g. pi/py-pro) for best in-kernel SDK results.[/yellow]", sys_prefix=False)
                self.run_worker(lambda: self.process_query_worker(args), thread=True)
            else:
                active = ipython.toggle_ipython_mode()
                if hasattr(self, "lbl_harness"): self.lbl_harness.update("[dim]Harness[/dim] " + ("NOOA IPython" if active else "Native Tools"))
                self.notify(f"NOOA IPython harness {'enabled (single tool mode)' if active else 'disabled (classic tools)'}.")
                if active and "py-" not in self.active_skill:
                    self.notify(f"[yellow]Warning: Active skill '{self.active_skill}' is a classic JSON skill. Use a Py profile (e.g. pi/py-pro) for best in-kernel SDK results.[/yellow]", sys_prefix=False)

        elif root in ("/v", "/voice"):
            is_auto = (bool(args) and args.strip().lower() == "auto")
            active, auto_mode = voice.toggle_voice_bridge(auto_toggle=is_auto)
            mode_str = "auto-submit" if auto_mode else "manual edit"
            val_str = f"Active ({'auto' if auto_mode else 'edit'})" if active else "Disabled"
            if hasattr(self, "lbl_voice"): self.lbl_voice.update(f"[dim]Voice[/dim]   {val_str}")
            self.notify(f"Voice to text {'active (' + mode_str + ' mode, port 9999)' if active else 'disabled'}.")

        elif root in ("/tts", "/talk", "/tol"):
            active = tts.toggle_tts()
            if hasattr(self, "lbl_tts"): self.lbl_tts.update(f"[dim]TTS[/dim]     {'Active' if active else 'Disabled'}")
            self.notify(f"Text to speech {'enabled' if active else 'disabled'}.")

        elif root in ("/task", "/loop", "/goal"): await self.handle_task_command(args)
        elif root in ("exit", "quit", "q"): self.exit()
        elif root in ("/copy", "/copy-all", "/copyall"): self.action_copy_entire_chat()
        elif root == "/m":
            self.memory_active = not self.memory_active
            core.save_state("memory_active", self.memory_active)
            if hasattr(self, "lbl_database"): self.lbl_database.update(f"[dim]DB State[/dim]  {self.get_db_status_string()}")
            self.notify(f"Memory {'enabled' if self.memory_active else 'disabled'}.")
        elif root in ("/plan", "/build", "/g", "/yolo"):
            if not self.is_agent: self.notify("Plan/Build modes are only available in project workspace sessions.", sys_prefix=False)
            else:
                if (root == "/plan" and self.agent_mode != "Plan") or (root == "/build" and self.agent_mode != "Build") or root in ("/g", "/yolo"):
                    self.action_toggle_plan_build()
                self.notify(f"Mode set to [bold]{self.agent_mode}[/bold].")
        elif root in ("/clear", "/c"):
            self.history.clear(); self.stats_turns = 0
            self.update_stats_ui(0, 0.0, 0.0)
            if hasattr(self, "lbl_image"): self.lbl_image.update("[dim]Image[/dim]   None")
            for child in list(self.chat_area.children): child.remove()
            self.notify("Active chat history cleared.")

        elif root in ("/reset", "/purge"):
            self.history.clear(); self.stats_turns = 0
            self.update_stats_ui(0, 0.0, 0.0)
            agent_dir = os.path.join(self.workspace_path, ".agent")
            db_path = os.path.join(SESSIONS_DIR, f"{self.safe_name}.db")

            if os.path.exists(agent_dir):
                try: import shutil; shutil.rmtree(agent_dir)
                except OSError: pass

            if os.path.exists(db_path):
                try: os.remove(db_path)
                except OSError: pass

            core.run_mod("ai-agent-sessions", "clear", self.safe_name)
            core.run_mod("ai-agent-memories", "tpm-clear", self.safe_name)

            for child in list(self.chat_area.children): child.remove()
            self.refresh_db_counts()
            if hasattr(self, "lbl_database"): self.lbl_database.update(f"[dim]DB State[/dim]  {self.get_db_status_string()}")
            self.notify("Full workspace reset complete (.agent & database purged).")
        elif root == "/tok":
            limit = int(os.environ.get("AI_MAX_TOKENS", 8192))
            total_toks = sum(core.get_accurate_token_count(m.get("content") or "") for m in self.history)
            pct = min(100.0, (total_toks / limit) * 100)
            filled = int((pct / 100.0) * 20)
            bar = "█" * filled + "░" * (20 - filled)
            status_col = "green" if pct < 70 else ("yellow" if pct < 90 else "red")
            border_col = "bright_white" if self.theme in ("mono", "grok") else self.border_accent

            panel = Panel(
                Group(
                    Text.assemble(("Context Window: ", "dim"), (f"{total_toks:,}", f"bold {status_col}"), (f"/{limit:,} tokens ", "dim"), (f"({pct:.1f}%)", f"bold {status_col}")),
                    Text(f"[{bar}]", style=status_col)
                ),
                title="Context Status", title_align="left", border_style=border_col, box=ROUNDED, expand=False
            )
            await self.chat_area.mount(Static(Group(Text(""), panel)))
            self.chat_area.scroll_end(animate=False)
        elif root in ("/sync", "/re"):
            self.notify("Triggered background AST codebase sync.")
            try: subprocess.Popen(["index-map", self.workspace_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError): pass
        elif root in ("/skill", "/s"):
            if args:
                sub_cmd = args.strip().lower()
                if sub_cmd in ("off", "clear", "reset", "none", "remove"):
                    self.on_demand_skill = None
                    self.set_skill(self.base_skill)
                    if self.history and self.history[0].get("role") == "system":
                        sys_c = self.history[0]["content"]
                        if "### Loaded On-Demand Skill:" in sys_c:
                            self.history[0]["content"] = sys_c.split("### Loaded On-Demand Skill:")[0].strip()
                    os.environ["AI_ACTIVE_SKILL"] = self.base_skill
                    self.notify(f"On-demand skill removed. Reverted to base skill: [bold]{self.base_skill}[/bold]")
                elif content := skills.load_skill_content(args, SKILLS_DIR, CFG_DIR):
                    s_name, s_text = content if isinstance(content, tuple) else (args, content)
                    self.on_demand_skill = s_name
                    combined_skill = f"{self.base_skill} {self.on_demand_skill}"
                    self.set_skill(combined_skill)
                    self.ensure_system_context()
                    if self.history and self.history[0].get("role") == "system":
                        self.history[0]["content"] += f"\n\n### Loaded On-Demand Skill: {s_name}\n{s_text}\n"
                    else:
                        self.history.insert(0, {"role": "system", "content": f"### Loaded On-Demand Skill: {s_name}\n{s_text}\n"})
                    os.environ["AI_ACTIVE_SKILL"] = combined_skill
                    self.notify(f"Active skills: [bold]{combined_skill}[/bold] (Swapped on-demand skill to [bold]{s_name}[/bold])")
                else: self.notify(f"No skill blueprint file found for '[bold]{args}[/bold]'.")
            else: self.notify("Usage: /skill <query>, /s <query>, or /s off")
        elif root in ("/compact", "/c"): self.action_toggle_compact()
        elif root in ("/t", "/thinking"):
            if args:
                sub = args.lower()
                if sub in ("hide", "off", "mute", "quiet"):
                    os.environ["AI_SHOW_THINKING"] = "0"; core.save_state("show_thinking", False)
                    for child in self.chat_area.children:
                        if isinstance(child, Message): child.refresh(layout=True)
                    self.notify("Thinking display hidden (thinking mode remains active).")
                elif sub in ("show", "on", "visible"):
                    os.environ["AI_SHOW_THINKING"] = "1"; core.save_state("show_thinking", True)
                    for child in self.chat_area.children:
                        if isinstance(child, Message): child.refresh(layout=True)
                    self.notify("Thinking display enabled.")
                elif sub.isdigit():
                    val = int(sub)
                    self.reasoning_budget = max(0, val)
                    self.reasoning_active = val > 0
                    core.save_state("reasoning_active", self.reasoning_active)
                    core.save_state("reasoning_budget", self.reasoning_budget)
                    status = f"{self.reasoning_budget} tokens" if self.reasoning_active else "Disabled"
                    self.set_reasoning(status)
                    self.notify(f"Deep reasoning {'enabled' if self.reasoning_active else 'disabled'} ({status}).")
                else: self.action_toggle_reasoning()
            else: self.action_toggle_reasoning()
        elif root in ("/f", "/tk", "/b", "/a"):
            if hasattr(self, "handle_meta_chat_command"):
                await self.handle_meta_chat_command(root, args)
            else:
                self.notify(f"Preset command '{root}' is not configured for this workspace profile.")
        else: self.notify(f"Unknown command '{root}'. Type [bold]/help[/bold] for commands.")

    def prompt_tui_confirm(self, prompt_text: str) -> bool:
        self.gate_auth_event.clear(); self.gate_auth_result = False

        def _show():
            self.entering_gate_authorization, self.current_gate_prompt = True, prompt_text
            self.chat_input.disabled, self.chat_input.value = False, ""
            self.chat_input.placeholder = f"  ▲ Authorize: {prompt_text}? [Y/n]: "
            self.chat_input.focus()

        self.call_from_thread(_show)
        self.gate_auth_event.wait()
        return self.gate_auth_result

    def process_query_worker(self, query: Any) -> None:
        self.call_from_thread(self._safe_remove_banner)
        for notice in self.chat_area.query(".sys-notice, .theme-notice"):
            try: self.call_from_thread(notice.remove)
            except Exception: pass

        self.ensure_system_context()
        self.call_from_thread(self.chat_area.mount, Message("User", query))
        old_confirm = getattr(ui, "confirm_tool", None)
        ui.confirm_tool = lambda reason: self.prompt_tui_confirm(reason)

        try:
            past_mem = tpm_ctx = ""
            user_text = query if isinstance(query, str) else next((i["text"] for i in query if isinstance(i, dict) and i.get("type") == "text"), "Multimodal Query")
            if self.is_agent and self.memory_active and isinstance(query, str):
                try: tpm_ctx = core.run_mod("ai-agent-memories", "tpm-get", self.safe_name)
                except (OSError, subprocess.SubprocessError): pass

            assistant_msg = Message("Agent", "Thinking...")
            self.call_from_thread(self.chat_area.mount, assistant_msg)
            self.call_from_thread(self.chat_area.scroll_end, animate=False)

            try: sys_ctx = skills.get_system_context(user_text, CONTEXT_FILE, STOP_WORDS, SKILLS_DIR, CFG_DIR) if (isinstance(query, str) and hasattr(skills, "get_system_context")) else ""
            except (OSError, ValueError, TypeError, KeyError): sys_ctx = ""
            if sys_ctx == "__ABORT_TURN__": sys_ctx = ""

            combined = "\n\n".join(filter(None, [tpm_ctx, past_mem, sys_ctx]))
            if isinstance(query, list): self.history.append({"role": "user", "content": query})
            else: self.history.append({"role": "user", "content": f"<context>\n{combined}\n</context>\n\nUser Question: {query}" if combined else f"User Question: {query}"})

            self.call_from_thread(self.disable_input)
            self.generation_cancelled, self.active_response = False, None
            accumulated, start_time, first_token_time, token_count = "", time.perf_counter(), None, 0
            last_ui_update = 0.0

            enable_think = self.reasoning_active and self.reasoning_budget > 0
            budget_val = self.reasoning_budget if enable_think else 0
            think_kwargs = {"thinking_budget_tokens": budget_val, "reasoning_budget": budget_val, "chat_template_kwargs": {"enable_thinking": enable_think}}

            for _round in range(10):
                accumulated, in_thinking, tool_calls_map = "", False, {}
                configs = agent_cloud.get_active_configs(self.history) if agent_cloud else []

                if not configs:
                    configs = [("http://localhost:8080/v1/chat/completions", {}, {"messages": self.history, "stream": True, "model": "local-model", **think_kwargs}, 180)]

                response = None
                for url, headers, body, timeout in configs:
                    body["stream"], body["messages"] = True, self.history
                    if "localhost" in url or "127.0.0.1" in url: body.update(think_kwargs)
                    if self.is_agent and hasattr(core, "EDIT_TOOLS"): body["tools"] = core.EDIT_TOOLS
                    req = urlreq.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", **headers}, method="POST")
                    try:
                        resp = urlreq.urlopen(req, timeout=timeout)
                        if resp.status == 200: response = resp; break
                    except (urlreq.URLError, TimeoutError, OSError): continue

                if not response: raise Exception("Failed to establish streaming response connection to AI engine or cloud backups.")

                with response:
                    self.active_response = response
                    for line in response:
                        if self.generation_cancelled: break
                        if not (dec := line.decode("utf-8", errors="ignore").strip()).startswith("data:"): continue
                        if (dec := dec[5:].strip()) == "[DONE]": break

                        try:
                            if not (choices := json.loads(dec).get("choices", [{}])): continue
                            delta = choices[0].get("delta", {})
                            text_chunk, thinking_chunk = delta.get("content") or "", delta.get("reasoning_content") or delta.get("thinking") or ""
                            if text_chunk and "Final Answer:" in text_chunk:
                                text_chunk = FINAL_ANSWER_RE.sub('', text_chunk).lstrip()

                            for tc in delta.get("tool_calls", []):
                                idx = tc.get("index", 0)
                                tc_entry = tool_calls_map.setdefault(idx, {"id": tc.get("id", ""), "type": "function", "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}})
                                if tc.get("function", {}).get("name"): tc_entry["function"]["name"] = tc["function"]["name"]
                                tc_entry["function"]["arguments"] += tc.get("function", {}).get("arguments", "")

                            if text_chunk or thinking_chunk:
                                if first_token_time is None: first_token_time = time.perf_counter()
                                token_count += 1

                            if thinking_chunk:
                                if not in_thinking: accumulated += "<think>"; in_thinking = True
                                accumulated += thinking_chunk
                            elif text_chunk:
                                if in_thinking: accumulated += "</think>"; in_thinking = False
                                accumulated += text_chunk

                            now = time.perf_counter()
                            if (text_chunk or thinking_chunk) and (now - last_ui_update >= 0.08):
                                last_ui_update = now
                                self.call_from_thread(assistant_msg.update_content, accumulated)
                                self.call_from_thread(self.chat_area.scroll_end, animate=False)
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError): pass

                if in_thinking: accumulated += "</think>"
                self.call_from_thread(assistant_msg.update_content, accumulated)
                self.call_from_thread(self.chat_area.scroll_end, animate=False)

                calls = [v for _, v in sorted(tool_calls_map.items())] if tool_calls_map else None
                if not calls:
                    self.history.append({"role": "assistant", "content": accumulated})
                    break

                self.history.append({"role": "assistant", "content": accumulated or None, "tool_calls": calls})
                user_aborted = False

                for tc in calls:
                    fname, raw_args = tc.get("function", {}).get("name", ""), tc.get("function", {}).get("arguments", "")
                    args = core._heal_tool_args(raw_args) if hasattr(core, "_heal_tool_args") else (json.loads(raw_args) if raw_args else {})
                    brief = str(args.get("symbol") or args.get("path") or args.get("command") or "")[:100]
                    verb = getattr(core, "TOOL_VERBS", {}).get(fname, "working")

                    if user_aborted:
                        result = "[denied] execution cancelled by user"
                    else:
                        if self.gates_enabled and not self.prompt_tui_confirm(f"{fname} {brief}"):
                            result, user_aborted = f"[denied] user rejected {fname}", True
                        else:
                            self.call_from_thread(self.notify, f"∗ {verb} • [bold cyan]{fname}[/bold cyan] [italic]{brief}[/italic]")
                            old_g = os.environ.get("AI_CONFIRM_GATES")
                            try:
                                os.environ["AI_CONFIRM_GATES"] = "0"
                                result = core._run_edit_tool(fname, args, self.workspace_path)
                            except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError) as te: result = f"[tool error] {te}"
                            finally:
                                if old_g is not None: os.environ["AI_CONFIRM_GATES"] = old_g
                                else: os.environ.pop("AI_CONFIRM_GATES", None)
                            if "[denied]" in result: user_aborted = True

                    pruned_result = result if len(result) <= 1500 else result[:1200] + f"\n... [Reasonix Harness: Snipped {len(result) - 1200} chars for context stability]"
                    self.history.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned_result})

                if user_aborted:
                    self.call_from_thread(self.notify, "Execution halted by user gate.")
                    break

                assistant_msg = Message("Agent", "Processing tool results...")
                self.call_from_thread(self.chat_area.mount, assistant_msg)

            end_time = time.perf_counter()
            total_elapsed = max(0.01, end_time - start_time)
            gen_dur = max(0.001, end_time - first_token_time) if first_token_time else total_elapsed
            out_toks = core.get_accurate_token_count(accumulated)
            tps = (out_toks / gen_dur) if first_token_time and out_toks > 0 else out_toks / total_elapsed

            self.stats_turns += 1
            self.call_from_thread(self.update_stats_ui, self.stats_turns, tps, total_elapsed)
            if hasattr(tts, "speak_response"):
                tts.speak_response(accumulated)

            if user_text:
                try:
                    core.run_mod("ai-agent-sessions", "log-turn", self.safe_name, user_text, accumulated)
                    self.refresh_db_counts()
                    if hasattr(self, "lbl_database"): self.call_from_thread(self.lbl_database.update, f"[dim]DB State[/dim]  {self.get_db_status_string()}")
                    if self.is_agent and self.memory_active:
                        threading.Thread(target=core.background_tpm_update, args=(user_text, accumulated, self.safe_name, self.workspace_path), daemon=True).start()
                except (OSError, subprocess.SubprocessError): pass

        except Exception as e:
            if self.generation_cancelled: self.call_from_thread(assistant_msg.update_content, (accumulated or "") + " (stopped)")
            else: self.call_from_thread(assistant_msg.update_content, f"Error: {e}")
        finally:
            self.active_response = None
            if old_confirm: ui.confirm_tool = old_confirm
            self.call_from_thread(self.enable_input)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        query = CSI_U_REGEX.sub('', event.value.strip()).strip()
        self.chat_input.value = ""
        self.chat_input.cursor_blink = False

        if getattr(self, "entering_image_url", False):
            if not getattr(self, "pending_image_url", ""):
                if not query:
                    self.entering_image_url = False
                    self.chat_input.placeholder = "Ask your agent anything..."
                    self.notify("[dim]Image input cancelled.[/dim]", sys_prefix=False)
                    return
                self.pending_image_url = query
                self.chat_input.placeholder = "Enter prompt for image (Press Enter for default 'Describe this image'):"
                self.chat_input.focus()
                return
            else:
                img_url, prompt_text = self.pending_image_url, query or "Describe this image in detail."
                self.entering_image_url, self.pending_image_url, self.chat_input.placeholder = False, "", "Ask your agent anything..."

                multimodal_payload = [{"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": img_url}}]
                img_name = os.path.basename(img_url.split("?")[0]) or "Attached"
                if len(img_name) > 12: img_name = f"{img_name[:9]}..."
                if hasattr(self, "lbl_image"): self.lbl_image.update(f"[dim]Image[/dim]   {img_name}")
                self.notify(f"Attached Image URL: [dim]{img_url[:40]}...[/dim]")
                self.run_worker(lambda: self.process_query_worker(multimodal_payload), thread=True)
                return

        if getattr(self, "entering_gate_authorization", False):
            self.entering_gate_authorization = False
            self.chat_input.placeholder = "Ask your agent anything..."
            is_yes = query.lower() in ("y", "yes", "")
            self.gate_auth_result = is_yes
            self.gate_auth_event.set()
            self.notify(f"[dim]Gate: {'Authorized' if is_yes else 'Denied'}[/dim]", sys_prefix=False)
            return

        if self.entering_reasoning_budget:
            self.entering_reasoning_budget, self.chat_input.placeholder = False, "Ask your agent anything..."
            if not query:
                self.reasoning_budget, self.reasoning_active = 500, True
                core.save_state("reasoning_active", True); core.save_state("reasoning_budget", 500)
                self.set_reasoning("500 tokens")
                self.notify("Deep reasoning enabled (default 500 tokens).")
            else:
                try:
                    if (val := int(query)) > 0:
                        self.reasoning_budget, self.reasoning_active = val, True
                        core.save_state("reasoning_active", True); core.save_state("reasoning_budget", val)
                        self.set_reasoning(f"{val} tokens")
                        self.notify(f"Deep reasoning enabled ({val} tokens).")
                    else: raise ValueError
                except ValueError:
                    self.reasoning_active = False
                    core.save_state("reasoning_active", False)
                    self.set_reasoning("Disabled")
                    self.notify("[dim]Invalid budget. Deep reasoning disabled.[/dim]", sys_prefix=False)
            return

        if not query: return
        if query.startswith("/"):
            await self.handle_slash_command(query)
            return

        if self.pending_skill_prefix:
            query, self.pending_skill_prefix = f"{self.pending_skill_prefix} {query}", None
            self.chat_input.placeholder = "Ask your agent anything..."

        if query.lower() in ("exit", "quit", "q"): self.exit(); return
        if query.lower().startswith("file "):
            parts = query.split(maxsplit=1)
            if len(parts) > 1: await self.handle_view_file(parts[1].strip())
            return

        self.run_worker(lambda: self.process_query_worker(query), thread=True)

    def disable_input(self) -> None:
        if not getattr(self, "entering_gate_authorization", False): self.chat_input.disabled = True

    def enable_input(self) -> None:
        self.chat_input.disabled, _ = False, self.chat_input.focus()

    def action_stop_generation(self) -> None:
        if self.chat_input.disabled or getattr(self, "entering_gate_authorization", False):
            self.generation_cancelled = True
            if getattr(self, "entering_gate_authorization", False):
                self.entering_gate_authorization = False
                self.gate_auth_result = False
                self.gate_auth_event.set()
            if self.active_response:
                try: self.active_response.close()
                except (OSError, AttributeError): pass
            self.notify("(Generation stopped by user.)", sys_prefix=False)

    def update_sidebar_visibility(self) -> None:
        try: self.query_one("#sidebar", Vertical).display = not self.sidebar_hidden
        except (KeyError, AttributeError): pass

    def action_toggle_sidebar(self) -> None:
        self.sidebar_hidden = not self.sidebar_hidden
        core.save_state("sidebar_hidden", self.sidebar_hidden)
        self.update_sidebar_visibility()

    def update_footer_visibility(self) -> None:
        try:
            self.query_one("#footer-bar", Horizontal).display = not self.footer_hidden
            self.query_one("#input-toggle", FooterToggle).update("▲ Show" if self.footer_hidden else "▼ Hide")
        except (KeyError, AttributeError): pass

    def action_toggle_footer(self) -> None:
        self.footer_hidden = not self.footer_hidden
        core.save_state("footer_hidden", self.footer_hidden)
        self.update_footer_visibility()

    def action_toggle_compact(self) -> None:
        self.compact_mode = (self.compact_mode + 1) % 3
        core.save_state("compact_mode", self.compact_mode)
        if hasattr(self, "chat_area"):
            self.chat_area.set_class(self.compact_mode == 2, "zero-spacing")
            for child in self.chat_area.children:
                if isinstance(child, Message): child.refresh(layout=True)
            self.chat_area.refresh(layout=True)
        mode_labels = {0: "Normal", 1: "Compact", 2: "Minimal (No Spaces)"}
        self.notify(f"Layout mode: {mode_labels[self.compact_mode]}", sys_prefix=False)

    def action_cycle_theme(self) -> None:
        try:
            idx = self.THEMES.index(self.theme) if self.theme in self.THEMES else 0
            self.theme = self.THEMES[(idx + 1) % len(self.THEMES)]
            self.notify(f"Theme: {self.theme}", sys_prefix=False, css_class="theme-notice")
        except (ValueError, KeyError, AttributeError): pass

    def action_toggle_reasoning(self) -> None:
        self.reasoning_active = not self.reasoning_active
        core.save_state("reasoning_active", self.reasoning_active)
        status = f"{self.reasoning_budget} tokens" if self.reasoning_active else "Disabled"
        self.set_reasoning(status)
        self.notify(f"Deep reasoning {'enabled' if self.reasoning_active else 'disabled'} ({status}).")

    def action_toggle_borders(self) -> None:
        self.borders_enabled = not self.borders_enabled
        core.save_state("tui_borders_enabled", self.borders_enabled)
        if hasattr(self, "chat_area"):
            for child in self.chat_area.children:
                if isinstance(child, Message): child.refresh(layout=True)
            self.chat_area.refresh(layout=True)
        self.notify(f"Message borders: {'Enabled' if self.borders_enabled else 'Disabled (Borderless)'}", sys_prefix=False)


if __name__ == "__main__":
    workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    try:
        configs = agent_cloud.get_active_configs([]) if agent_cloud else []
        model = configs[0][2].get("model", "local-model") if configs else ui.get_local_model_name()
    except (ImportError, AttributeError, KeyError, IndexError, OSError): model = ui.get_local_model_name()

    try: LocalAITUI(workspace, model).run()
    finally:
        try:
            subprocess.run(["stty", "sane"], check=False)
            sys.stdout.write("\033[0m\033[?25h")
            sys.stdout.flush()
        except (OSError, subprocess.SubprocessError): pass
