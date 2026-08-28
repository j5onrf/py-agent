#!/usr/bin/env python3
"""Production Minimal Textual TUI for Py Agent Engine"""

import base64, json, os, re, sqlite3, subprocess, sys, threading, time, urllib.request as urlreq
from collections.abc import Iterator
from contextlib import closing
from typing import Any

try: import uvloop; uvloop.install()
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

import agent_cloud, agent_core as core, agent_ipython as ipython, agent_skills as skills, agent_tts as tts, agent_tui_async as tui_async, agent_ui as ui, agent_voice as voice

CONTEXT_FILE = os.path.join(CFG_DIR, "ai-context.md")
SKILLS_DIR, SESSIONS_DIR = os.path.join(CFG_DIR, "skills"), os.path.join(CFG_DIR, "projects", "database")
LEFT_BAR, NO_BOX = Box("▌   \n" * 8), Box("    \n" * 8)

TOKEN_RE = re.compile(r"[^\w\s]")
STOP_WORDS = frozenset({"is", "what", "it", "do", "any", "i", "have", "the", "a", "an", "on", "to", "for", "me", "you", "my", "your", "we", "us", "are", "about", "in", "how"})
CSI_U_REGEX = re.compile(r'(?:\x1b\[<|\x1b\[|\[<)?\d+;\d+;\d+[mM]|\x1b\[[0-9;]*[a-zA-Z~]|\x1b[\[\(\=][0-9;]*[a-zA-Z~]?')
ANSI_CLEAN_REGEX = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
REASONIX_STEP_RE = re.compile(r'^(?:\d+\.\s*|Step \d+:?\s*|Phase \d+:?\s*|\#{1,3}\s*)\*\*?([^\n\*:]+)\*\*?:?', re.I)
CLEAN_CODE_BLOCKS_RE = re.compile(r'```\n\s*\n+')
MULTI_NEWLINE_RE = re.compile(r'\n{3,}')
FINAL_ANSWER_RE = re.compile(r'^\s*Final Answer:\s*', re.I)
THINK_TAGS_RE = re.compile(r'<think>.*?</think>', re.DOTALL)
BASE_PROMPT_CHAT, BASE_PROMPT_AGENT = "Active, natural conversational assistant.", "Active local workspace developer agent."
_CACHED_CLIPBOARD_TOOL: list[str] | None = None


def format_dir_path(p: str) -> str:
    h = p.replace(os.path.expanduser("~"), "~")
    return h if len(h) <= 20 else f".../{os.path.basename(h.rstrip('/'))}"


def format_model_name(name: str, max_len: int = 18) -> str:
    if not name: return "Unknown"
    c = name.strip()
    if len(c) <= max_len: return c
    b = c.rsplit("/", 1)[-1]
    return f".../{b}" if len(b) <= max_len else f"{b[:(max_len-3)//2]}...{b[-(max_len-3)//2:]}"


def copy_to_clipboard(text: str) -> bool:
    global _CACHED_CLIPBOARD_TOOL
    if not text: return False
    try:
        sys.stdout.write(f"\x1b]52;c;{base64.b64encode(text.encode()).decode()}\x07"); sys.stdout.flush()
    except OSError: pass
    tools = [_CACHED_CLIPBOARD_TOOL] if _CACHED_CLIPBOARD_TOOL else [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["pbcopy"], ["clip.exe"]]
    for tool in filter(None, tools):
        try:
            p = subprocess.Popen(tool, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            p.communicate(input=text.encode(), timeout=1.0)
            if p.returncode == 0: _CACHED_CLIPBOARD_TOOL = tool; return True
        except (OSError, subprocess.SubprocessError): continue
    return True


def _format_tui_reasonix_text(text: str, theme: str = "code1") -> Text:
    style = {"code1": "bold #89b4fa", "code2": "bold #ff9e64", "dark": "bold cyan", "mono": "bold white"}.get(theme, "bold cyan")
    res, last_empty = Text(), False
    for line in text.splitlines():
        if not (clean := line.strip()):
            if not last_empty: res.append("\n"); last_empty = True
            continue
        last_empty = False
        if m := REASONIX_STEP_RE.match(clean): res.append(f"{m.group(0).strip()}\n", style=style)
        else: res.append(f"{line}\n", style="italic dim")
    return res.rstrip()


code1_theme = Theme(name="code1", primary="#89b4fa", secondary="#a6adc8", accent="#89b4fa", background="#11121d", surface="#161726", panel="#1b1c2b")
code2_theme = Theme(name="code2", primary="#ff9e64", secondary="#e0af68", accent="#ff9e64", background="#11121d", surface="#161726", panel="#1b1c2b")
mono_theme = Theme(name="mono", primary="#ffffff", secondary="#a0a0a0", accent="#ffffff", background="#000000", surface="#0d0d0d", panel="#121212")
dark_theme = Theme(name="dark", primary="#555555", secondary="#b0b0b0", accent="#ffffff", background="#121212", surface="#1c1c1c", panel="#242424")


class FooterToggle(Static):
    def on_click(self) -> None: getattr(self.app, "action_toggle_footer", lambda: None)()

class ImageButton(Static):
    def on_click(self) -> None: getattr(self.app, "action_prompt_image_url", lambda: None)()

class CloseCardButton(Static):
    def on_click(self) -> None: getattr(self.app, "action_close_tips_card", lambda: None)()


class Message(Static):
    def __init__(self, sender: str, content: Any) -> None:
        super().__init__()
        self.sender, self.msg_content = sender, content
        self._cached_render = self._cached_theme = self._cached_compact = self._cached_borders = None

    def update_content(self, new_content: Any) -> None:
        self.msg_content = new_content
        self._cached_render = None
        self.refresh()

    def render(self) -> Any:
        app_t, c_mode, b_on = getattr(self.app, "theme", "code1"), getattr(self.app, "compact_mode", 0), getattr(self.app, "borders_enabled", True)
        if self._cached_render and (self._cached_theme, self._cached_compact, self._cached_borders) == (app_t, c_mode, b_on):
            return self._cached_render

        is_d = getattr(self.app, "is_dark_theme", True)
        self.styles.color = "#c8d3f5" if ("code" in app_t and is_d) else None
        self.styles.margin = (1, 2, 0, 0) if c_mode == 0 else (0, 2, 0, 0)
        u_style = "bold #888888" if app_t in ("mono", "grok") else ("bold #89b4fa" if "code" in app_t else ("bold #0265dc" if not is_d else "bold cyan"))
        code_fmt = "ansi_dark" if is_d else "ansi_light"
        bg_col = "#0d0d0d" if app_t in ("mono", "grok") else ("#1a1a1a" if app_t == "dark" else ("#1b1c2b" if is_d else "#f0f0f4"))
        b_col = getattr(self.app, "border_accent", "#89b4fa")

        if self.sender == "User":
            raw = self.msg_content if isinstance(self.msg_content, str) else next((i["text"] for i in self.msg_content if isinstance(i, dict) and i.get("type") == "text"), "[Multimodal Payload]")
            txt = raw.split("User Question:", 1)[-1].strip() if "User Question:" in raw else raw
            if c_mode == 0:
                fg = "white" if app_t in ("mono", "grok", "dark") else ("#303446" if not is_d else "#c8d3f5")
                res = Panel(Text(txt, style=fg), box=LEFT_BAR, border_style=b_col, style=f"on {bg_col}", padding=(0, 2))
            else: res = Text(txt, style=u_style)
        else:
            txt, show_th = str(self.msg_content or ""), os.environ.get("AI_SHOW_THINKING", "1") == "1"
            if "<think>" in txt:
                bef, aft = txt.split("<think>", 1)
                items = [Markdown(bef.strip(), code_theme=code_fmt)] if bef.strip() else []
                if "</think>" in aft:
                    th, rest = aft.split("</think>", 1)
                    if show_th and th.strip(): items.append(Panel(_format_tui_reasonix_text(th.strip(), app_t), title="⚙", title_align="left", border_style=b_col, box=ROUNDED, expand=True))
                    if rest.strip(): items.append(Markdown(MULTI_NEWLINE_RE.sub('\n\n', CLEAN_CODE_BLOCKS_RE.sub('```\n', rest.strip())), code_theme=code_fmt))
                elif show_th and aft.strip():
                    items.append(Panel(_format_tui_reasonix_text(aft.strip(), app_t), title="⚙ Thinking...", title_align="left", border_style=b_col, box=ROUNDED, expand=True))
                body = Group(*items) if items else Text("Thinking...", style="italic dim")
            else:
                cl = MULTI_NEWLINE_RE.sub('\n\n', CLEAN_CODE_BLOCKS_RE.sub('```\n', txt.strip()))
                body = Markdown(cl, code_theme=code_fmt) if cl else Text("...", style="italic dim")
            res = Panel(body, box=ROUNDED if b_on else NO_BOX, border_style=("dim " + b_col) if b_on else b_col, style=f"on {bg_col}", padding=(0, 2)) if c_mode == 0 else body

        self._cached_render, self._cached_theme, self._cached_compact, self._cached_borders = res, app_t, c_mode, b_on
        return res


class AgentCommandProvider(Provider):
    async def search(self, query: str) -> Iterator[Hit]:
        m = self.matcher(query)
        cmds = [("Copy Last Response", "copy_last_response", "Copy latest agent response"), ("Copy Entire Chat Page", "copy_entire_chat", "Copy complete transcript"), ("Cycle Theme", "cycle_theme", "Cycle color themes"), ("Toggle Sidebar", "toggle_sidebar", "Show/hide metadata panel"), ("Toggle Compact Mode", "toggle_compact", "Toggle spacing layout"), ("Toggle Reasoning", "toggle_reasoning", "Toggle reasoning budget"), ("Toggle Mode (Plan/Build)", "toggle_plan_build", "Switch Plan/Build mode")]
        for t, a, d in cmds:
            if (score := m.match(t)) > 0: yield Hit(score, Text(t), lambda act=a: self.app.run_action(act), help=d)


class LocalAITUI(App):
    ENABLE_COMMAND_PALETTE = True
    THEMES = ["code1", "code2", "dark", "mono"]

    @property
    def command_sources(self) -> set[Any]: return {AgentCommandProvider}

    @property
    def border_accent(self) -> str:
        t = str(getattr(self, "theme", "code1")).lower()
        return "bright_white" if ("mono" in t or "grok" in t) else ("bright_blue" if "dark" in t else ("#ff9e64" if "code2" in t else "#89b4fa"))

    @property
    def is_dark_theme(self) -> bool:
        return not any(k in str(getattr(self, "theme", "code1")).lower() for k in ["light", "latte", "day", "solarized-light", "dawn", "paper"])

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
    #input-toggle, #btn-image-url { width: auto; height: 1; color: $secondary; padding: 0 1; margin-top: 2; }
    #input-toggle:hover, #btn-image-url:hover { color: $primary; text-style: bold; }
    #sidebar { width: 30; height: 100%; background: $surface; border-left: solid $boost; padding: 1 1; align: left top; }
    Message { margin-top: 1; margin-right: 2; height: auto; max-width: 100%; overflow-x: hidden; }
    Message:first-child { margin-top: 0; margin-right: 2; }
    #chat-area.zero-spacing Message { margin-top: 0; }
    .sidebar-section { height: auto; border-bottom: none; padding-bottom: 1; margin-bottom: 1; }
    .sidebar-label { color: $primary; text-style: bold; margin-bottom: 0; }
    .sidebar-val { color: $text; margin-bottom: 0; }
    .sys-notice, .theme-notice { margin-top: 1; margin-bottom: 0; }
    .theme-notice { color: #ffffff; text-style: bold; }
    #card-tips { background: $panel; padding: 1; margin-top: 1; }
    #card-tips-header { height: 1; width: 100%; }
    #lbl-tips-title { width: 1fr; color: $primary; text-style: bold; }
    #btn-close-tips { width: auto; color: $secondary; text-style: bold; }
    #btn-close-tips:hover { color: $error; text-style: bold; }
    #lbl-tips-body { color: $text; margin-top: 1; }
    #footer-bar { dock: bottom; height: 1; width: 100%; background: $surface; }
    #footer-keys { width: 100%; height: 1; }
    #sidebar.blue-sidebar .sidebar-val, #sidebar.blue-sidebar #lbl-tips-body { color: #c8d3f5; }
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
        Binding("ctrl+q", "quit", "Exit TUI", show=True),
    ]

    def watch_theme(self, theme: str) -> None:
        core.save_state("tui_theme", theme); self.update_welcome_banner(); self.set_skill(self.active_skill)
        try:
            sb = self.query_one("#sidebar")
            sb.add_class("blue-sidebar") if theme in ("code1", "code2") else sb.remove_class("blue-sidebar")
        except Exception: pass
        if hasattr(self, "chat_area"):
            for c in self.chat_area.children:
                if isinstance(c, Message): c.refresh(layout=True)
            self.chat_area.refresh(layout=True)

    def __init__(self, ws_path: str, model_name: str, is_agent: bool | None = None) -> None:
        super().__init__()
        self.workspace_path, self.model_name = ws_path, model_name
        self.safe_name = core.workspace_safe_name(ws_path)
        a_dir, cfg_f = os.path.join(ws_path, ".agent"), os.path.join(ws_path, ".agent", "config.json")

        if is_agent is not None: self.is_agent = is_agent
        elif "AI_IS_AGENT" in os.environ: self.is_agent = os.environ["AI_IS_AGENT"].lower() in ("1", "true", "yes")
        else: self.is_agent = (os.path.abspath(ws_path) != os.path.abspath(os.path.expanduser("~"))) and (os.path.exists(a_dir) or "/projects/" in ws_path)

        if not self.is_agent: self.agent_mode, self.gates_enabled = "Disabled", True
        else:
            yolo = (os.environ.get("AI_CONFIRM_GATES") == "0") if os.environ.get("AI_CONFIRM_GATES") is not None else core.get_state("yolo_mode", False)
            self.agent_mode, self.gates_enabled = ("Build" if yolo else "Plan"), not yolo
            os.environ["AI_CONFIRM_GATES"] = "0" if yolo else "1"

        self.gate_auth_event = threading.Event()
        self.gate_auth_result = self.entering_gate_authorization = self.entering_image_url = False
        self.current_gate_prompt = self.pending_image_url = ""
        self.spell_enabled, self.pending_skill_prefix = True, None

        inh = os.environ.get("AI_ACTIVE_SKILL")
        if (not inh or inh.lower() in ("default", "none", "")) and os.path.exists(cfg_f):
            try:
                with open(cfg_f, "r", encoding="utf-8") as f: inh = json.load(f).get("profile") or json.load(f).get("skill")
            except Exception: pass
        inh = inh or ("pi/pro" if self.is_agent else "chat")
        sp = [s for s in inh.split() if s]
        self.base_skill = sp[0] if sp else ("pi/pro" if self.is_agent else "chat")
        self.on_demand_skill = sp[1] if len(sp) > 1 else None
        self.active_skill = f"{self.base_skill} {self.on_demand_skill}".strip() if self.on_demand_skill else self.base_skill

        self.memory_active, self.db_turns, self.tpm_count = core.get_state("memory_active", False), 0, 0
        self.refresh_db_counts()
        self.compact_mode = int(core.get_state("compact_mode", 0))
        self.reasoning_active, self.reasoning_budget, self.entering_reasoning_budget = core.get_state("reasoning_active", False), core.get_state("reasoning_budget", 500), False

        try: self.history: list[dict[str, Any]] = json.loads(os.environ.get("AI_SESSION_HISTORY", "")) if os.environ.get("AI_SESSION_HISTORY") else []
        except Exception: self.history = []

        self.generation_cancelled, self.active_response, self.stats_turns = False, None, 0
        self.borders_enabled = core.get_state("tui_borders_enabled", True)
        self.footer_hidden, self.sidebar_hidden, self.tips_card_hidden = core.get_state("footer_hidden", True), core.get_state("sidebar_hidden", False), core.get_state("tips_card_hidden", False)

    def on_unmount(self) -> None:
        self.gate_auth_result = False; self.gate_auth_event.set()
        if self.active_response:
            try: self.active_response.close()
            except Exception: pass

    def _safe_remove_banner(self) -> None:
        for n in self.query("#welcome-banner"):
            try: n.remove()
            except Exception: pass

    def notify(self, text: str, sys_prefix: bool = True, css_class: str = "sys-notice") -> None:
        self.chat_area.mount(Static(f"[dim white][sys] {text}[/dim white]" if sys_prefix else text, classes=css_class))
        self.chat_area.scroll_end(animate=False)

    def set_skill(self, name: str) -> None:
        self.active_skill = name
        bg, fg = {"code1": ("#1b2b3b", "#89b4fa"), "code2": ("#3b2b1b", "#ff9e64"), "mono": ("#222222", "#ffffff"), "dark": ("#333333", "#e0e0e0")}.get(getattr(self, "theme", "code1"), ("#1b2b3b", "#89b4fa"))
        if hasattr(self, "lbl_skill"): self.lbl_skill.update(f"[dim]Skill[/dim]   [bold {fg} on {bg}] {name} [/]")

    def set_mode(self, m: str) -> None:
        self.agent_mode = m
        if hasattr(self, "lbl_mode"): self.lbl_mode.update(f"[dim]Mode[/dim]    {m}")

    def set_reasoning(self, t: str) -> None:
        if hasattr(self, "lbl_reasoning"): self.lbl_reasoning.update(f"[dim]Reasoning[/dim] {t}")

    def action_prompt_image_url(self) -> None:
        if getattr(self, "entering_image_url", False):
            self.entering_image_url, self.pending_image_url, self.chat_input.placeholder = False, "", "Ask your agent anything..."
            self.notify("[dim]Image input cancelled.[/dim]", sys_prefix=False)
        else:
            self.entering_image_url, self.pending_image_url, self.chat_input.placeholder = True, "", "Enter Image Path or URL (e.g. Downloads/dog.jpg or https://...):"
        self.chat_input.focus()

    def on_key(self, event) -> None:
        if event.key == "tab": self.action_toggle_plan_build(); event.prevent_default(); event.stop()

    def refresh_db_counts(self) -> None:
        db = os.path.join(SESSIONS_DIR, f"{self.safe_name}.db")
        if not os.path.exists(db): self.db_turns = self.tpm_count = 0; return
        try:
            with closing(sqlite3.connect(db, timeout=2)) as conn:
                c = conn.cursor()
                try: self.db_turns = (c.execute("SELECT COUNT(*) FROM turns WHERE workspace = ?", (self.safe_name,)).fetchone() or [0])[0]
                except Exception: pass
                try: self.tpm_count = (c.execute("SELECT COUNT(*) FROM tpm_memories").fetchone() or [0])[0]
                except Exception: pass
        except Exception: pass

    def ensure_system_context(self) -> None:
        if not any(m.get("role") == "system" for m in self.history):
            sl = [s.lstrip("-").lower() for s in self.active_skill.split() if s] if (self.active_skill and self.active_skill.lower() not in ("default", "none")) else []
            sc = skills.load_skill_content(" ".join(sl), SKILLS_DIR, CFG_DIR) if sl else ""
            if self.is_agent:
                sys_p = (sc or BASE_PROMPT_AGENT) + f"\n\n### ACTIVE PROJECT WORKSPACE:\nYour active root: {self.workspace_path}\n"
                a_dir = os.path.join(self.workspace_path, ".agent")
                if os.path.exists(a_dir):
                    for mf in [f for f in os.listdir(a_dir) if f.startswith("index-map-") and f.endswith(".txt")]:
                        try:
                            with open(os.path.join(a_dir, mf), "r", encoding="utf-8", errors="ignore") as f:
                                sys_p += f"\n\n### CODESPACE MAP:\n{f.read().strip()}\n"
                                break
                        except Exception: pass
            else: sys_p = sc or BASE_PROMPT_CHAT
            self.history.insert(0, {"role": "system", "content": sys_p})
            if self.is_agent and len(self.history) == 1: self.history.append({"role": "assistant", "content": "Agent: Workspace loaded. Awaiting instructions."})

    def get_db_status_string(self) -> str: return f"active • {self.tpm_count} facts" if (self.is_agent and self.memory_active) else "stateless"

    def update_welcome_banner(self) -> None:
        try:
            if self.query("#welcome-banner"):
                t = Table(show_header=False, box=None, padding=(0, 2), expand=False)
                t.add_column("Key", style="bold #89b4fa" if "code" in self.theme else "bold cyan"); t.add_column("Action", style="default")
                for k, a in [("Tab", "Plan / Build Mode"), ("Ctrl+B", "Toggle Sidebar"), ("Ctrl+T", "Cycle Themes"), ("Ctrl+I", "Attach Image"), ("Ctrl+O", "Copy Response"), ("Ctrl+Q", "Quit TUI"), ("/help", "Commands")]: t.add_row(k, a)
                self.query_one("#welcome-banner", Static).update(Panel(t, title=" ∿ PyTUI ", title_align="left", border_style=self.border_accent, box=ROUNDED, expand=False))
        except Exception: pass

    def compose(self) -> ComposeResult:
        with Horizontal(id="layout"):
            with Vertical(id="main-container"):
                with Vertical(id="chat-area"): yield Static(id="welcome-banner")
                with Horizontal(id="input-pane"):
                    yield Static("▌\n▌\n▌", id="input-bar"); yield Input(placeholder="Ask your agent anything...", id="chat-input"); yield FooterToggle("▲ Show", id="input-toggle")
            with Vertical(id="sidebar"):
                with Vertical(classes="sidebar-section"):
                    yield Static("MODEL & SESSION", classes="sidebar-label")
                    yield Static(f"[dim]Model[/dim]   {format_model_name(self.model_name)}", id="lbl-model", classes="sidebar-val")
                    yield Static(f"[dim]Dir[/dim]     {format_dir_path(self.workspace_path)}", id="lbl-dir", classes="sidebar-val")
                    yield Static(f"[dim]Skill[/dim]   {self.active_skill}", id="lbl-skill", classes="sidebar-val")
                    yield Static(f"[dim]Mode[/dim]    {self.agent_mode}", id="lbl-mode", classes="sidebar-val")
                    yield Static("[dim]Harness[/dim] Chat Mode", id="lbl-harness", classes="sidebar-val")
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
                        yield Static("Quick Tips", id="lbl-tips-title"); yield CloseCardButton("×", id="btn-close-tips")
                    yield Static("Tab: Switch Mode\nCtrl+B: Sidebar\nCtrl+F: Borders\nCtrl+G: Compact\nCtrl+T: Themes\nCtrl+I: Vision Image\nCtrl+Q: Exit TUI\n/tok: Context\n/py: Harness\n/v: Voice\n/tts: Speak\n/task: Goal\n/help: Help", id="lbl-tips-body")
        with Horizontal(id="footer-bar"): yield Footer(id="footer-keys")

    def action_close_tips_card(self) -> None:
        self.tips_card_hidden = True; core.save_state("tips_card_hidden", True)
        try: self.query_one("#card-tips", Vertical).display = False
        except Exception: pass

    def on_mount(self) -> None:
        if hasattr(self, "register_theme"):
            for t in (code1_theme, code2_theme, mono_theme, dark_theme):
                try: self.register_theme(t)
                except Exception: pass
        try: self.theme = core.get_state("tui_theme", "code1")
        except Exception: pass

        self.chat_area = self.query_one("#chat-area", Vertical)
        if self.compact_mode == 2: self.chat_area.add_class("zero-spacing")
        self.chat_input = self.query_one("#chat-input", Input)
        self.lbl_skill, self.lbl_mode, self.lbl_harness, self.lbl_reasoning = self.query_one("#lbl-skill", Static), self.query_one("#lbl-mode", Static), self.query_one("#lbl-harness", Static), self.query_one("#lbl-reasoning", Static)
        self.lbl_database, self.lbl_stats, self.lbl_voice, self.lbl_tts, self.lbl_image = self.query_one("#lbl-database", Static), self.query_one("#lbl-stats", Static), self.query_one("#lbl-voice", Static), self.query_one("#lbl-tts", Static), self.query_one("#lbl-image", Static)

        use_ip = ("py-" in self.active_skill.lower() or (ipython and ipython.is_ipython_enabled())) if self.is_agent else False
        self.lbl_harness.update("[dim]Harness[/dim] " + ("NOOA IPython" if use_ip else ("Native Tools" if self.is_agent else "Chat Mode")))
        if hasattr(voice, "is_bridge_running"): self.lbl_voice.update(f"[dim]Voice[/dim]   {'Active' if voice.is_bridge_running() else 'Disabled'}")
        if hasattr(tts, "is_tts_enabled"): self.lbl_tts.update(f"[dim]TTS[/dim]     {'Active' if tts.is_tts_enabled() else 'Disabled'}")

        os.environ["AI_SHOW_THINKING"] = "1" if core.get_state("show_thinking", True) else "0"
        self.set_skill(self.active_skill); self.set_mode(self.agent_mode)
        self.set_reasoning(f"{self.reasoning_budget} tokens" if self.reasoning_active else "Disabled")
        self.update_welcome_banner(); self.chat_input.cursor_blink = True
        self.update_footer_visibility(); self.update_sidebar_visibility()
        if self.tips_card_hidden:
            try: self.query_one("#card-tips", Vertical).display = False
            except Exception: pass

        if len(self.history) > 1:
            self._safe_remove_banner()
            for msg in self.history:
                r, c = msg.get("role"), msg.get("content")
                if r in ("user", "assistant") and c: self.chat_area.mount(Message("User" if r == "user" else "Agent", c))

        self.run_worker(tui_async.watch_workspace_changes(self), exclusive=False)
        self.run_worker(tui_async.start_subagent_ipc_hub(self), exclusive=False)
        self.chat_input.focus()

    def action_toggle_plan_build(self) -> None:
        if not self.is_agent: return
        self.agent_mode, self.gates_enabled = ("Build", False) if self.agent_mode == "Plan" else ("Plan", True)
        os.environ["AI_CONFIRM_GATES"] = "0" if not self.gates_enabled else "1"
        core.save_state("yolo_mode", not self.gates_enabled)
        self.set_mode(self.agent_mode)

    def on_input_changed(self, event: Input.Changed) -> None:
        if (cl := CSI_U_REGEX.sub('', event.value)) != event.value: event.input.value = cl

    def update_stats_ui(self, turns: int, tps: float, elapsed: float) -> None:
        if hasattr(self, "lbl_stats"): self.lbl_stats.update(f"[dim]Turns[/dim]     {turns} @ {f'{tps:.1f} t/s' if tps > 0 else '-- t/s'}")

    def action_scroll_page_up(self) -> None: self.chat_area.scroll_page_up(animate=False)
    def action_scroll_page_down(self) -> None: self.chat_area.scroll_page_down(animate=False)
    def action_scroll_up(self) -> None: self.chat_area.scroll_up(animate=False)
    def action_scroll_down(self) -> None: self.chat_area.scroll_down(animate=False)

    def action_copy_last_response(self) -> None:
        if last := next((m.get("content", "") for m in reversed(self.history) if m.get("role") == "assistant"), ""):
            copy_to_clipboard(last.split("</think>", 1)[-1].strip() if "</think>" in last else last); self.notify("Copied response to clipboard.")
        else: self.notify("No response to copy.")

    def action_copy_entire_chat(self) -> None:
        if tr := [f"❯ USER: {m['content']}" if m.get("role") == "user" else f"AGENT:\n{THINK_TAGS_RE.sub('', str(m['content'])).strip()}" for m in self.history if m.get("content") and m.get("role") != "system"]:
            copy_to_clipboard("\n\n".join(tr)); self.notify("Copied transcript to clipboard.")
        else: self.notify("No transcript to copy.")

    async def handle_view_file(self, path: str) -> None:
        fp = os.path.expanduser(path) if os.path.isabs(os.path.expanduser(path)) else os.path.join(self.workspace_path, path)
        if os.path.isfile(fp):
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f: self.history.append({"role": "user", "content": f"[FILE: {path}]\n```\n{f.read(12000)}\n```"})
                self.notify(f"Loaded file context: [bold]{path}[/bold]")
            except Exception as e: self.notify(f"[bold red]File error: {e}[/bold red]", sys_prefix=False)
        else: self.notify(f"[bold red]File not found: {path}[/bold red]", sys_prefix=False)

    async def handle_task_command(self, args: str = "") -> None:
        self._safe_remove_banner(); self.ensure_system_context()
        goal = args.strip('"\': ') or "TASK.md spec"
        await self.chat_area.mount(Message("User", f"/task \"{goal}\""))
        asst = Message("Agent", f"[task] Executing Goal loop: [italic]{goal}[/italic]...")
        await self.chat_area.mount(asst); self.chat_area.scroll_end(animate=False)

        def _sub():
            r_bin = os.path.join(CFG_DIR, "tools", "loop", "ralph.py")
            if os.path.exists(r_bin):
                try:
                    res = subprocess.run([sys.executable, r_bin, args], cwd=self.workspace_path, capture_output=True, text=True, timeout=300, env={**os.environ, "AI_WORKSPACE_PATH": self.workspace_path})
                    out = ANSI_CLEAN_REGEX.sub('', (res.stdout or res.stderr or "").replace('\r', '\n')).strip()
                    self.call_from_thread(asst.update_content, f"### Task Report\n\n{out or '✔ Task completed.'}")
                    self.history.extend([{"role": "user", "content": f"/task \"{goal}\""}, {"role": "assistant", "content": out or "Task complete."}])
                    self.refresh_db_counts()
                except Exception as e: self.call_from_thread(asst.update_content, f"[red]Task error: {e}[/red]")
            else: self.call_from_thread(asst.update_content, "[red]Task script not found.[/red]")
        self.run_worker(_sub, thread=True)

    async def handle_slash_command(self, cmd: str) -> None:
        self._safe_remove_banner()
        p = cmd.split(maxsplit=1); root, args = p[0].lower(), p[1] if len(p) > 1 else ""

        if root in ("/help", "/h"):
            t = Table(show_header=False, box=None, padding=(0, 1), expand=False)
            t.add_column("Command", style="bold #89b4fa" if "code" in self.theme else "bold cyan"); t.add_column("Description", style="default")
            for c, d in [("/help, /h", "Help"), ("/v", "Voice to text"), ("/tts", "Text to speech"), ("/py", "NOOA IPython"), ("Tab", "Plan/Build"), ("/task", "Task Loop"), ("/copy", "Copy transcript"), ("/m", "Memory toggle"), ("/clear, /c", "Clear chat"), ("/reset", "Hard reset"), ("/tok", "Tokens"), ("/sync", "Sync AST index"), ("/s <q>", "Load Skill"), ("/t <toks>", "Reasoning"), ("Ctrl+I", "Attach Image"), ("file <p>", "Load File"), ("q", "Exit")]: t.add_row(c, d)
            await self.chat_area.mount(Static(Group(Text(""), Panel(t, title="Commands", title_align="left", border_style=self.border_accent, box=ROUNDED, expand=False))))
            self.chat_area.scroll_end(animate=False)
        elif root == "/theme":
            if args and args.strip().lower() in self.THEMES: self.theme = args.strip().lower(); self.notify(f"Theme: [bold]{self.theme}[/bold].", css_class="theme-notice")
            else: self.action_cycle_theme()
        elif root in ("/py", "/ipython"):
            act = ipython.toggle_ipython_mode(True if args else None) if ipython else False
            if hasattr(self, "lbl_harness"): self.lbl_harness.update("[dim]Harness[/dim] " + ("NOOA IPython" if act else "Native Tools"))
            self.notify(f"NOOA IPython {'enabled' if act else 'disabled'}.")
            if args: self.run_worker(lambda: self.process_query_worker(args), thread=True)
        elif root in ("/v", "/voice"):
            act, auto = voice.toggle_voice_bridge(auto_toggle=(bool(args) and args.strip().lower() == "auto")) if hasattr(voice, "toggle_voice_bridge") else (False, False)
            if hasattr(self, "lbl_voice"): self.lbl_voice.update(f"[dim]Voice[/dim]   {'Active' if act else 'Disabled'}")
            self.notify(f"Voice {'active' if act else 'disabled'}.")
        elif root in ("/tts", "/talk", "/tol"):
            act = tts.toggle_tts() if hasattr(tts, "toggle_tts") else False
            if hasattr(self, "lbl_tts"): self.lbl_tts.update(f"[dim]TTS[/dim]     {'Active' if act else 'Disabled'}")
            self.notify(f"TTS {'enabled' if act else 'disabled'}.")
        elif root in ("/task", "/loop", "/goal"): await self.handle_task_command(args)
        elif root in ("exit", "quit", "q"): self.exit()
        elif root in ("/copy", "/copy-all", "/copyall"): self.action_copy_entire_chat()
        elif root == "/m":
            self.memory_active = not self.memory_active; core.save_state("memory_active", self.memory_active)
            if hasattr(self, "lbl_database"): self.lbl_database.update(f"[dim]DB State[/dim]  {self.get_db_status_string()}")
            self.notify(f"Memory {'enabled' if self.memory_active else 'disabled'}.")
        elif root in ("/plan", "/build", "/g", "/yolo"):
            if not self.is_agent: self.notify("Plan/Build is for project workspaces only.", sys_prefix=False)
            else: self.action_toggle_plan_build(); self.notify(f"Mode: [bold]{self.agent_mode}[/bold].")
        elif root in ("/clear", "/c"):
            self.history.clear(); self.stats_turns = 0; self.update_stats_ui(0, 0.0, 0.0)
            if hasattr(self, "lbl_image"): self.lbl_image.update("[dim]Image[/dim]   None")
            for c in list(self.chat_area.children): c.remove()
            self.notify("Chat cleared.")
        elif root in ("/reset", "/purge"):
            self.history.clear(); self.stats_turns = 0; self.update_stats_ui(0, 0.0, 0.0)
            for d in [os.path.join(self.workspace_path, ".agent"), os.path.join(SESSIONS_DIR, f"{self.safe_name}.db")]:
                try: (os.remove(d) if os.path.isfile(d) else shutil.rmtree(d)) if os.path.exists(d) else None
                except Exception: pass
            core.run_mod("ai-agent-sessions", "clear", self.safe_name); core.run_mod("ai-agent-memories", "tpm-clear", self.safe_name)
            for c in list(self.chat_area.children): c.remove()
            self.refresh_db_counts(); self.notify("Workspace reset complete.")
        elif root == "/tok":
            limit = int(os.environ.get("AI_MAX_TOKENS", 8192))
            toks = sum(core.get_accurate_token_count(m.get("content") or "") for m in self.history)
            pct = min(100.0, (toks / limit) * 100); bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            col = "green" if pct < 70 else ("yellow" if pct < 90 else "red")
            p = Panel(Group(Text.assemble(("Context: ", "dim"), (f"{toks:,}", f"bold {col}"), (f"/{limit:,} ", "dim"), (f"({pct:.1f}%)", f"bold {col}")), Text(f"[{bar}]", style=col)), title="Context Status", title_align="left", border_style=self.border_accent, box=ROUNDED, expand=False)
            await self.chat_area.mount(Static(Group(Text(""), p))); self.chat_area.scroll_end(animate=False)
        elif root in ("/sync", "/re"):
            self.notify("Triggered AST codebase sync.")
            try: subprocess.Popen(["index-map", self.workspace_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception: pass
        elif root in ("/skill", "/s"):
            if args:
                if args.strip().lower() in ("off", "clear", "reset", "none", "remove"):
                    self.on_demand_skill = None; self.set_skill(self.base_skill)
                    os.environ["AI_ACTIVE_SKILL"] = self.base_skill
                    self.notify(f"Skill reverted to: [bold]{self.base_skill}[/bold]")
                elif content := skills.load_skill_content(args, SKILLS_DIR, CFG_DIR):
                    sn, st = content if isinstance(content, tuple) else (args, content)
                    self.on_demand_skill = sn; comb = f"{self.base_skill} {self.on_demand_skill}"
                    self.set_skill(comb); self.ensure_system_context()
                    if self.history and self.history[0].get("role") == "system": self.history[0]["content"] += f"\n\n### Loaded Skill: {sn}\n{st}\n"
                    os.environ["AI_ACTIVE_SKILL"] = comb; self.notify(f"Active skill: [bold]{comb}[/bold]")
                else: self.notify(f"Skill not found for '{args}'.")
            else: self.notify("Usage: /skill <query> or /s off")
        elif root in ("/compact", "/c"): self.action_toggle_compact()
        elif root in ("/t", "/thinking"):
            if args and args.isdigit():
                v = int(args); self.reasoning_budget, self.reasoning_active = max(0, v), v > 0
                core.save_state("reasoning_active", self.reasoning_active); core.save_state("reasoning_budget", self.reasoning_budget)
                self.set_reasoning(f"{self.reasoning_budget} tokens" if self.reasoning_active else "Disabled")
                self.notify(f"Reasoning set to {self.reasoning_budget} tokens.")
            else: self.action_toggle_reasoning()
        else: self.notify(f"Unknown command '{root}'. Type [bold]/help[/bold] for commands.")

    def prompt_tui_confirm(self, prompt_text: str) -> bool:
        self.gate_auth_event.clear(); self.gate_auth_result = False
        def _show():
            self.entering_gate_authorization, self.current_gate_prompt = True, prompt_text
            self.chat_input.disabled, self.chat_input.value = False, ""
            self.chat_input.placeholder = f"  ▲ Authorize: {prompt_text}? [Y/n]: "; self.chat_input.focus()
        self.call_from_thread(_show); self.gate_auth_event.wait()
        return self.gate_auth_result

    def process_query_worker(self, query: Any) -> None:
        self.call_from_thread(self._safe_remove_banner)
        for n in self.chat_area.query(".sys-notice, .theme-notice"):
            try: self.call_from_thread(n.remove)
            except Exception: pass

        self.ensure_system_context()
        self.call_from_thread(self.chat_area.mount, Message("User", query))
        old_confirm = getattr(ui, "confirm_tool", None)
        ui.confirm_tool = lambda reason: self.prompt_tui_confirm(reason)

        try:
            tpm_ctx = (core.run_mod("ai-agent-memories", "tpm-get", self.safe_name) if (self.is_agent and self.memory_active and isinstance(query, str)) else "")
            user_txt = query if isinstance(query, str) else next((i["text"] for i in query if isinstance(i, dict) and i.get("type") == "text"), "Multimodal Query")
            assistant_msg = Message("Agent", "Thinking...")
            self.call_from_thread(self.chat_area.mount, assistant_msg)
            self.call_from_thread(self.chat_area.scroll_end, animate=False)

            sys_ctx = skills.get_system_context(user_txt, CONTEXT_FILE, STOP_WORDS, SKILLS_DIR, CFG_DIR) if (isinstance(query, str) and hasattr(skills, "get_system_context")) else ""
            comb = "\n\n".join(filter(None, [tpm_ctx, sys_ctx if sys_ctx != "__ABORT_TURN__" else ""]))

            if isinstance(query, list): self.history.append({"role": "user", "content": query})
            else: self.history.append({"role": "user", "content": f"<context>\n{comb}\n</context>\n\nUser Question: {query}" if comb else f"User Question: {query}"})

            self.call_from_thread(self.disable_input)
            self.generation_cancelled, self.active_response = False, None
            accumulated, start_time, first_tok_time, last_ui = "", time.perf_counter(), None, 0.0

            enable_th = self.reasoning_active and self.reasoning_budget > 0
            b_val = self.reasoning_budget if enable_th else 0
            think_kw = {"thinking_budget_tokens": b_val, "reasoning_budget": b_val, "chat_template_kwargs": {"enable_thinking": enable_th}}

            if hasattr(core, "preprocess_multimodal_messages"):
                self.history = core.preprocess_multimodal_messages(self.history)

            for _round in range(10):
                accumulated, in_th, tool_map = "", False, {}
                configs = agent_cloud.get_active_configs(self.history) if agent_cloud else []
                if not configs: configs = [("http://localhost:8080/v1/chat/completions", {}, {"messages": self.history, "stream": True, "model": "local-model", **think_kw}, 180)]

                response = None
                for url, headers, body, timeout in configs:
                    body["stream"], body["messages"] = True, self.history
                    if "localhost" in url or "127.0.0.1" in url: body.update(think_kw)
                    if self.is_agent and hasattr(core, "EDIT_TOOLS"): body["tools"] = core.EDIT_TOOLS
                    req = urlreq.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
                    try:
                        resp = urlreq.urlopen(req, timeout=timeout)
                        if resp.status == 200: response = resp; break
                    except Exception: continue

                if not response: raise Exception("Failed to connect to AI engine.")

                with response:
                    self.active_response = response
                    for line in response:
                        if self.generation_cancelled: break
                        if not (dec := line.decode("utf-8", errors="ignore").strip()).startswith("data:"): continue
                        if (dec := dec[5:].strip()) == "[DONE]": break
                        try:
                            if not (choices := json.loads(dec).get("choices", [{}])): continue
                            delta = choices[0].get("delta", {})
                            tc_chunk, th_chunk = delta.get("content") or "", delta.get("reasoning_content") or delta.get("thinking") or delta.get("reasoning") or ""
                            if tc_chunk and "Final Answer:" in tc_chunk: tc_chunk = FINAL_ANSWER_RE.sub('', tc_chunk).lstrip()

                            for tc in delta.get("tool_calls", []):
                                idx = tc.get("index", 0)
                                ent = tool_map.setdefault(idx, {"id": tc.get("id", ""), "type": "function", "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}})
                                if tc.get("function", {}).get("name"): ent["function"]["name"] = tc["function"]["name"]
                                ent["function"]["arguments"] += tc.get("function", {}).get("arguments", "")

                            if tc_chunk or th_chunk:
                                if first_tok_time is None: first_tok_time = time.perf_counter()
                            if th_chunk:
                                if not in_th: accumulated += "<think>"; in_th = True
                                accumulated += th_chunk
                            elif tc_chunk:
                                if in_th: accumulated += "</think>"; in_th = False
                                accumulated += tc_chunk

                            now = time.perf_counter()
                            if (tc_chunk or th_chunk) and (now - last_ui >= 0.08):
                                last_ui = now
                                self.call_from_thread(assistant_msg.update_content, accumulated)
                                self.call_from_thread(self.chat_area.scroll_end, animate=False)
                        except Exception: pass

                if in_th: accumulated += "</think>"
                self.call_from_thread(assistant_msg.update_content, accumulated)
                self.call_from_thread(self.chat_area.scroll_end, animate=False)

                calls = [v for _, v in sorted(tool_map.items())] if tool_map else None
                if not calls:
                    self.history.append({"role": "assistant", "content": accumulated}); break

                self.history.append({"role": "assistant", "content": accumulated or None, "tool_calls": calls})
                aborted = False

                for tc in calls:
                    fn, r_args = tc.get("function", {}).get("name", ""), tc.get("function", {}).get("arguments", "")
                    args = core._heal_tool_args(r_args) if hasattr(core, "_heal_tool_args") else (json.loads(r_args) if r_args else {})
                    brief = str(args.get("symbol") or args.get("path") or args.get("command") or "")[:100]
                    verb = getattr(core, "TOOL_VERBS", {}).get(fn, "working")

                    if aborted: res = "[denied] cancelled"
                    elif self.gates_enabled and not self.prompt_tui_confirm(f"{fn} {brief}"): res, aborted = f"[denied] rejected {fn}", True
                    else:
                        self.call_from_thread(self.notify, f"∗ {verb} • [bold cyan]{fn}[/bold cyan] [italic]{brief}[/italic]")
                        old_g = os.environ.get("AI_CONFIRM_GATES"); os.environ["AI_CONFIRM_GATES"] = "0"
                        try: res = core._run_edit_tool(fn, args, self.workspace_path)
                        except Exception as te: res = f"[tool error] {te}"
                        finally:
                            if old_g is not None: os.environ["AI_CONFIRM_GATES"] = old_g
                            else: os.environ.pop("AI_CONFIRM_GATES", None)
                        if "[denied]" in res: aborted = True

                    pruned = res if len(res) <= 1500 else res[:1200] + f"\n... [Snipped {len(res) - 1200} chars]"
                    self.history.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fn, "content": pruned})

                if aborted: self.call_from_thread(self.notify, "Execution halted by user gate."); break
                assistant_msg = Message("Agent", "Processing tool results...")
                self.call_from_thread(self.chat_area.mount, assistant_msg)

            tot_el = max(0.01, time.perf_counter() - start_time)
            dur = max(0.001, time.perf_counter() - first_tok_time) if first_tok_time else tot_el
            out_toks = core.get_accurate_token_count(accumulated)
            tps = (out_toks / dur) if first_tok_time and out_toks > 0 else out_toks / tot_el

            self.stats_turns += 1
            self.call_from_thread(self.update_stats_ui, self.stats_turns, tps, tot_el)
            if hasattr(tts, "speak_response"): tts.speak_response(accumulated)
            if user_txt:
                try:
                    core.run_mod("ai-agent-sessions", "log-turn", self.safe_name, user_txt, accumulated)
                    self.refresh_db_counts()
                    if hasattr(self, "lbl_database"): self.call_from_thread(self.lbl_database.update, f"[dim]DB State[/dim]  {self.get_db_status_string()}")
                    if self.is_agent and self.memory_active: threading.Thread(target=core.background_tpm_update, args=(user_txt, accumulated, self.safe_name, self.workspace_path), daemon=True).start()
                except Exception: pass

        except Exception as e:
            msg = (accumulated or "") + " (stopped)" if self.generation_cancelled else f"Error: {e}"
            self.call_from_thread(assistant_msg.update_content, msg)
        finally:
            self.active_response = None
            if old_confirm: ui.confirm_tool = old_confirm
            self.call_from_thread(self.enable_input)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        query = CSI_U_REGEX.sub('', event.value.strip()).strip()
        self.chat_input.value = ""; self.chat_input.cursor_blink = False

        if getattr(self, "entering_image_url", False):
            if not getattr(self, "pending_image_url", ""):
                if not query:
                    self.entering_image_url = False; self.chat_input.placeholder = "Ask your agent anything..."
                    self.notify("[dim]Image input cancelled.[/dim]", sys_prefix=False); return
                self.pending_image_url = query
                self.chat_input.placeholder = "Enter prompt for image (Press Enter for default 'Describe this image'):"
                self.chat_input.focus(); return
            else:
                img_url, prompt_text = self.pending_image_url, query or "Describe this image in detail."
                self.entering_image_url, self.pending_image_url, self.chat_input.placeholder = False, "", "Ask your agent anything..."
                multimodal_payload = [{"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": img_url}}]
                img_name = os.path.basename(img_url.split("?")[0]) or "Attached"
                if len(img_name) > 12: img_name = f"{img_name[:9]}..."
                if hasattr(self, "lbl_image"): self.lbl_image.update(f"[dim]Image[/dim]   {img_name}")
                self.notify(f"Attached Image: [dim]{img_url[:40]}...[/dim]")
                self.run_worker(lambda: self.process_query_worker(multimodal_payload), thread=True)
                return

        if getattr(self, "entering_gate_authorization", False):
            self.entering_gate_authorization = False; self.chat_input.placeholder = "Ask your agent anything..."
            is_yes = query.lower() in ("y", "yes", "")
            self.gate_auth_result = is_yes; self.gate_auth_event.set()
            self.notify(f"[dim]Gate: {'Authorized' if is_yes else 'Denied'}[/dim]", sys_prefix=False); return

        if self.entering_reasoning_budget:
            self.entering_reasoning_budget, self.chat_input.placeholder = False, "Ask your agent anything..."
            try:
                v = int(query) if query else 500
                self.reasoning_budget, self.reasoning_active = max(0, v), v > 0
                core.save_state("reasoning_active", self.reasoning_active); core.save_state("reasoning_budget", self.reasoning_budget)
                self.set_reasoning(f"{self.reasoning_budget} tokens" if self.reasoning_active else "Disabled")
                self.notify(f"Deep reasoning set to {self.reasoning_budget} tokens.")
            except Exception:
                self.reasoning_active = False; core.save_state("reasoning_active", False); self.set_reasoning("Disabled")
            return

        if not query: return
        if query.startswith("/"): await self.handle_slash_command(query); return
        if query.lower() in ("exit", "quit", "q"): self.exit(); return
        if query.lower().startswith("file "):
            p = query.split(maxsplit=1)
            if len(p) > 1: await self.handle_view_file(p[1].strip())
            return

        self.run_worker(lambda: self.process_query_worker(query), thread=True)

    def disable_input(self) -> None:
        if not getattr(self, "entering_gate_authorization", False): self.chat_input.disabled = True

    def enable_input(self) -> None: self.chat_input.disabled, _ = False, self.chat_input.focus()

    def action_stop_generation(self) -> None:
        if self.chat_input.disabled or getattr(self, "entering_gate_authorization", False):
            self.generation_cancelled = True
            if getattr(self, "entering_gate_authorization", False):
                self.entering_gate_authorization = self.gate_auth_result = False; self.gate_auth_event.set()
            if self.active_response:
                try: self.active_response.close()
                except Exception: pass
            self.notify("(Generation stopped by user.)", sys_prefix=False)

    def update_sidebar_visibility(self) -> None:
        try: self.query_one("#sidebar", Vertical).display = not self.sidebar_hidden
        except Exception: pass

    def action_toggle_sidebar(self) -> None:
        self.sidebar_hidden = not self.sidebar_hidden; core.save_state("sidebar_hidden", self.sidebar_hidden); self.update_sidebar_visibility()

    def update_footer_visibility(self) -> None:
        try:
            self.query_one("#footer-bar", Horizontal).display = not self.footer_hidden
            self.query_one("#input-toggle", FooterToggle).update("▲ Show" if self.footer_hidden else "▼ Hide")
        except Exception: pass

    def action_toggle_footer(self) -> None:
        self.footer_hidden = not self.footer_hidden; core.save_state("footer_hidden", self.footer_hidden); self.update_footer_visibility()

    def action_toggle_compact(self) -> None:
        self.compact_mode = (self.compact_mode + 1) % 3; core.save_state("compact_mode", self.compact_mode)
        if hasattr(self, "chat_area"):
            self.chat_area.set_class(self.compact_mode == 2, "zero-spacing")
            for c in self.chat_area.children:
                if isinstance(c, Message): c.refresh(layout=True)
            self.chat_area.refresh(layout=True)
        self.notify(f"Layout mode: {['Normal', 'Compact', 'Minimal'][self.compact_mode]}", sys_prefix=False)

    def action_cycle_theme(self) -> None:
        try:
            idx = self.THEMES.index(self.theme) if self.theme in self.THEMES else 0
            self.theme = self.THEMES[(idx + 1) % len(self.THEMES)]
            self.notify(f"Theme: {self.theme}", sys_prefix=False, css_class="theme-notice")
        except Exception: pass

    def action_toggle_reasoning(self) -> None:
        self.reasoning_active = not self.reasoning_active; core.save_state("reasoning_active", self.reasoning_active)
        self.set_reasoning(f"{self.reasoning_budget} tokens" if self.reasoning_active else "Disabled")
        self.notify(f"Deep reasoning {'enabled' if self.reasoning_active else 'disabled'}.")

    def action_toggle_borders(self) -> None:
        self.borders_enabled = not self.borders_enabled; core.save_state("tui_borders_enabled", self.borders_enabled)
        if hasattr(self, "chat_area"):
            for c in self.chat_area.children:
                if isinstance(c, Message): c.refresh(layout=True)
            self.chat_area.refresh(layout=True)
        self.notify(f"Borders: {'Enabled' if self.borders_enabled else 'Disabled'}", sys_prefix=False)


if __name__ == "__main__":
    ws = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    try:
        cfgs = agent_cloud.get_active_configs([]) if agent_cloud else []
        mdl = cfgs[0][2].get("model", "local-model") if cfgs else ui.get_local_model_name()
    except Exception: mdl = ui.get_local_model_name()

    try: LocalAITUI(ws, mdl).run()
    finally:
        try:
            subprocess.run(["stty", "sane"], check=False)
            sys.stdout.write("\033[0m\033[?25h"); sys.stdout.flush()
        except Exception: pass
