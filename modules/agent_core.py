#!/usr/bin/env python3
"""Core Module - Streaming SSE, dynamic tool execution, & Rich rendering [Hardened Production Ready]"""

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

import agent_adapters as adapters
import agent_cloud
import agent_context as context
from agent_context import (
    get_accurate_token_count,
    show_memory_status,
)
import agent_security as security
import agent_tools as tools

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
STATE_FILE: str = os.path.join(CFG_DIR, ".state.json")
STATE_LOCK_FILE: str = os.path.join(CFG_DIR, ".state.lock")


def preprocess_multimodal_messages(*args: Any, **kwargs: Any) -> Any:
    import agent_vision
    return agent_vision.preprocess_multimodal_messages(*args, **kwargs)


def describe_image_gemini(*args: Any, **kwargs: Any) -> Any:
    import agent_vision
    return agent_vision.describe_image_gemini(*args, **kwargs)


def _get_img_config(*args: Any, **kwargs: Any) -> Any:
    import agent_vision
    return agent_vision._get_img_config(*args, **kwargs)


def prune_history(msg_list: list[dict[str, Any]], max_tokens: int | None = None) -> list[dict[str, Any]]:
    """In-place history pruner ensuring caller reference aliasing is preserved."""
    pruned = context.prune_history(msg_list, max_tokens=max_tokens) if max_tokens else context.prune_history(msg_list)
    msg_list[:] = pruned
    return msg_list


_markdown_initialized: bool = False
_console_lock = threading.Lock()


def _init_rich_markdown() -> None:
    global _markdown_initialized
    with _console_lock:
        if _markdown_initialized:
            return
        from rich.markdown import CodeBlock, Markdown as _RM
        from rich.segment import Segment
        from rich.syntax import Syntax

        class CleanCodeBlock(CodeBlock):
            def __rich_console__(self, console: Any, options: Any) -> Any:
                code = str(self.text).rstrip()
                lexer = getattr(self, "lexer_name", "text") or "text"
                theme = getattr(self, "theme", "") or str(get_state("code_theme", "monokai"))
                syntax = Syntax(
                    code,
                    lexer,
                    theme=theme,
                    word_wrap=False,
                    padding=0,
                    background_color="default",
                )
                lines = console.render_lines(syntax, options)
                for line in lines:
                    while line and line[-1].text.isspace():
                        line.pop()
                    if line and line[-1].text != line[-1].text.rstrip(" "):
                        line[-1] = Segment(line[-1].text.rstrip(" "), line[-1].style)
                    yield from line
                    yield Segment.line()

        _RM.elements["fence"] = CleanCodeBlock
        _RM.elements["code_block"] = CleanCodeBlock
        _markdown_initialized = True


def Markdown(*args: Any, **kwargs: Any) -> Any:
    _init_rich_markdown()
    from rich.markdown import Markdown as _RM
    return _RM(*args, **kwargs)


def prepare_markdown(text: str) -> str:
    """Repairs unclosed fences and wraps bare code emitted by small SLMs."""
    if not text:
        return ""
    if text.count("```") % 2 != 0:
        text = text.rstrip() + "\n```"
    elif "```" not in text:
        code_kw = ("import ", "from ", "def ", "class ", "return ", "print(")
        if any(l.lstrip().startswith(code_kw) for l in text.splitlines()):
            text = f"```python\n{text.strip()}\n```"
    return text


def get_cursor_up_count(text: str, width: int) -> int:
    if not text:
        return 0
    w = max(1, width)
    clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    raw_lines = clean.split("\n")
    up = 0
    for line in raw_lines[:-1]:
        up += max(1, (len(line) + w - 1) // w)
    last = raw_lines[-1]
    if last:
        last_visual = max(1, (len(last) + w - 1) // w)
        up += last_visual - 1
    return up


_console_inst: Any = None
_console_err_inst: Any = None


def _get_console(stderr: bool = False) -> Any:
    global _console_inst, _console_err_inst
    with _console_lock:
        if stderr:
            if _console_err_inst is None:
                from rich.console import Console
                _console_err_inst = Console(stderr=True)
            return _console_err_inst
        if _console_inst is None:
            from rich.console import Console
            _console_inst = Console(stderr=False)
        return _console_inst


class _LazyConsole:
    def __init__(self, stderr: bool = False) -> None:
        self._stderr = stderr

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_console(self._stderr), name)


_console, _console_err = _LazyConsole(False), _LazyConsole(True)

_local_session = threading.local()


def _get_session() -> Any:
    if not hasattr(_local_session, "session"):
        import requests
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        _local_session.session = s
    return _local_session.session


_orig_excepthook = sys.excepthook


def _clean_sigint_handler(exctype, value, tb):
    if isinstance(exctype, type) and issubclass(exctype, KeyboardInterrupt):
        raw_err = getattr(sys, "__stderr__", sys.stderr)
        try:
            raw_err.write("\r\033[0m\033[?25h\x1b[2K\033[90m[sys] Interrupted.\033[0m\r\n")
            raw_err.flush()
        except Exception:
            pass
        return
    if _orig_excepthook and _orig_excepthook is not _clean_sigint_handler:
        _orig_excepthook(exctype, value, tb)
    else:
        sys.__excepthook__(exctype, value, tb)


sys.excepthook = _clean_sigint_handler

RE_THINKING_TITLE = re.compile(r"^\s*Thinking Process:\s*", re.IGNORECASE)
RE_FINAL_ANSWER = re.compile(r"^\s*Final Answer:\s*", re.IGNORECASE)
RE_FINAL_ANSWER_SENTINEL = re.compile(r"^\s*#{0,3}\s*Final Answer\b", re.IGNORECASE | re.MULTILINE)
RE_MULTIPLE_NEWLINES = re.compile(r"\n{2,}")
RE_TOOL_CALL_BLOCK = re.compile(
    r"<\|tool_call_start\|>.*?<\|tool_call_end\|>|<tool_call>[\s\S]*?</tool_call>|<arg_key>[\s\S]*?</arg_value>",
    re.DOTALL
)

TOOL_VERBS: dict[str, str] = getattr(tools, "TOOL_VERBS", {})

DEFAULTS = {
    "show_stats": False, "memory_active": False, "box_style": 7, "yolo_mode": True,
    "show_thinking": True, "reasoning_active": True, "reasoning_budget": 500,
    "voice_auto_submit": True, "tts_enabled": False, "render_markdown": False,
    "adapters_active": False, "calm_mode": False, "code_theme": "monokai"
}

try:
    import agent_usage as usage_log
    speed_test = usage_log
except ImportError:
    usage_log = None
    speed_test = None

_state_lock = threading.Lock()
_state_cache: dict[str, Any] = {}
_state_mtime: float = 0.0
_state_size: int = 0
_state_ino: int = 0


def _get_int_env(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None or not str(val).strip():
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _heal_tool_args(raw: Any) -> dict[str, Any]:
    """Heals malformed JSON tool arguments via modular adapter or safe decode."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s == "{}":
            return {}
    else:
        if not raw:
            return {}

    if get_state("adapters_active", False):
        return adapters.heal_json_args(raw) if isinstance(raw, str) else (raw or {})
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except Exception as e:
        if os.environ.get("AI_DEBUG") == "1":
            sys.stderr.write(f"[debug] Failed to parse tool arguments: {e} (raw={raw!r})\n")
        return {"_parse_error": str(e), "_raw_args": str(raw)}


def get_state(key: str = "", default: Any = None) -> Any:
    global _state_cache, _state_mtime, _state_size, _state_ino
    with _state_lock:
        if os.path.exists(STATE_FILE):
            try:
                st = os.stat(STATE_FILE)
                sig = (st.st_mtime, st.st_size, getattr(st, "st_ino", 0))
                if sig != (_state_mtime, _state_size, _state_ino) or not _state_cache:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        _state_cache = loaded
                    _state_mtime, _state_size, _state_ino = sig
            except (OSError, json.JSONDecodeError):
                pass
        elif _state_cache:
            _state_cache, _state_mtime, _state_size, _state_ino = {}, 0.0, 0, 0
        merged = {**DEFAULTS, **_state_cache}
        return merged.get(key, default) if key else merged


def save_state(key: str, value: Any) -> None:
    global _state_cache, _state_mtime, _state_size, _state_ino
    with _state_lock:
        os.makedirs(CFG_DIR, exist_ok=True)
        lock_fd = None
        tmp = f"{STATE_FILE}.tmp.{os.getpid()}.{threading.get_ident()}"
        try:
            lock_fd = os.open(STATE_LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            current = {}
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        current = json.load(f)
                except (OSError, json.JSONDecodeError):
                    current = {}
            st = {**current, key: value}
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2)
            os.replace(tmp, STATE_FILE)
            _state_cache = st
            try:
                st_stat = os.stat(STATE_FILE)
                _state_mtime, _state_size, _state_ino = st_stat.st_mtime, st_stat.st_size, getattr(st_stat, "st_ino", 0)
            except OSError:
                pass
        except (OSError, TypeError, ValueError) as e:
            sys.stderr.write(f"[sys] Failed to persist state '{key}': {e}\n")
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                except OSError:
                    pass


def workspace_safe_name(workspace_path: str, home_dir: str = "") -> str:
    home, ws = os.path.realpath(home_dir or os.path.expanduser("~")), os.path.realpath(workspace_path)
    return "home-chat" if ws == home else (ws.replace("/", "-").strip("-.") or "home-chat")


def is_calm_cli() -> bool:
    """Strict gate: Calm mode only runs in interactive CLI terminals."""
    if os.environ.get("AI_SURFACE") == "1" or os.environ.get("TEXTUAL") or _get_int_env("AI_SUBAGENT_DEPTH", 0) >= 1:
        return False
    if not (sys.stdout.isatty() and sys.stderr.isatty()):
        return False
    return bool(get_state("calm_mode", False))


def run_mod(module_name: str, *args: str) -> str:
    for base in (os.path.join(CFG_DIR, "modules"), os.path.join(CFG_DIR, "tools"), CFG_DIR):
        base_real = os.path.realpath(base)
        target = os.path.realpath(os.path.join(base, module_name))
        if os.path.isfile(target) and os.path.commonpath([base_real, target]) == base_real:
            try:
                cmd = [sys.executable, target] + list(args) if target.endswith(".py") else [target] + list(args)
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
                return (res.stdout or res.stderr or "").strip()
            except Exception as e:
                return f"[error: {e}]"
    return ""


def _escape_markup(text: str) -> str:
    return str(text).replace("[", "\\[")


# ── 1. Streaming Rich Streamer ───────────────────────────────────────────────

class RichStreamer:
    def __init__(self, prefix: str = "", active: bool = True, spinner: Any = None, round_idx: int = 0) -> None:
        self.prefix, self.active, self.spinner = prefix, active and sys.stdout.isatty(), spinner
        self.acc_think, self.acc_ans, self.phase, self.think_hdr_printed, self.ans_started = "", "", "INIT", False, False
        self.in_post_think = False
        self.round_idx = round_idx

    def _stop_spinner(self, done_msg: str | None = None) -> None:
        if self.spinner:
            try:
                self.spinner.stop(done_msg=done_msg)
            except Exception:
                pass

    def start(self) -> None:
        if self.active:
            try:
                sys.stdout.write("\033[?25h")
                sys.stdout.flush()
            except OSError:
                pass

    def update(self, token: str) -> None:
        if not self.active:
            if "<think>" in token and self.phase != "THINKING":
                self.phase, token = "THINKING", token.replace("<think>", "")
            if "</think>" in token:
                parts = token.split("</think>", 1)
                self.phase, token = "ANSWER", parts[1]
            if self.phase != "THINKING" and token:
                try:
                    sys.stdout.write(token.replace("\r\n", "\n").replace("\n", "\r\n"))
                    sys.stdout.flush()
                except OSError:
                    pass
            return

        if "<think>" in token:
            if self.ans_started:
                self.in_post_think = True
            else:
                self.phase = "THINKING"
            token = token.replace("<think>", "")

        show_think = os.environ.get("AI_SHOW_THINKING", "1") == "1"

        if "</think>" in token:
            parts = token.split("</think>", 1)
            if self.in_post_think:
                self.in_post_think = False
                if len(parts) > 1 and parts[1]:
                    self.update(parts[1])
                return
            if parts[0]:
                self.update(parts[0])
            if show_think and self.think_hdr_printed and not self.ans_started:
                sep = "" if self.acc_think.endswith("\n") else "\r\n"
                _console_err.print(f"{sep}[dim]╰────────────────────────────────────────────────────────[/dim]\n")
                sys.stderr.flush()
            self.phase = "ANSWER"
            if self.spinner and not self.ans_started:
                self.spinner.start("Drafting tool action...")
            if len(parts) > 1 and parts[1]:
                self.update(parts[1])
            return

        if self.in_post_think:
            self.acc_think += token
            return

        if self.phase == "INIT":
            self.phase = "ANSWER"

        if self.phase == "THINKING":
            tok = RE_MULTIPLE_NEWLINES.sub("\n", RE_THINKING_TITLE.sub("", token))
            if self.acc_think.endswith("\n") and tok.startswith("\n"):
                tok = tok.lstrip("\r\n")
            self.acc_think += tok
            if show_think and tok:
                if not self.think_hdr_printed and tok.strip():
                    self.think_hdr_printed = True
                    self._stop_spinner()
                    _console_err.print("[dim]╭─ ∿ ────────────────────────────────────────────────────[/dim]")
                    tok = tok.lstrip("\r\n")
                if tok:
                    try:
                        sys.stderr.write(tok.replace("\r\n", "\n").replace("\n", "\r\n"))
                        sys.stderr.flush()
                    except OSError:
                        pass
        else:
            tok = RE_FINAL_ANSWER.sub("", token)
            if not self.ans_started:
                tok = tok.lstrip("\r\n\t ")
                if not tok:
                    return
                self._stop_spinner()
                self.ans_started, p_clean = True, self.prefix.strip()
                p_str = f"{p_clean}\n\n" if (p_clean and tok.startswith(("```", "#", "---"))) else (f"{p_clean} " if p_clean else "")
                p_style = "\033[1;32m" if "Agent" in p_clean else "\033[1;36m"
                lead = "\n" if (not self.think_hdr_printed and self.round_idx == 0) else ""
                if p_str:
                    try:
                        sys.stdout.write(f"{lead}{p_style}{p_str}\033[0m")
                        sys.stdout.flush()
                    except OSError:
                        pass
                self.acc_ans += lead + p_str

            self.acc_ans += tok
            if tok:
                try:
                    sys.stdout.write(tok.replace("\r\n", "\n").replace("\n", "\r\n"))
                    sys.stdout.flush()
                except OSError:
                    pass

    def stop(self, interrupted: bool = False) -> None:
        self._stop_spinner()
        if interrupted:
            try:
                sys.stdout.write("\033[?25h\r\n")
                sys.stdout.flush()
            except OSError:
                pass
            return

        show_think = os.environ.get("AI_SHOW_THINKING", "1") == "1"
        if self.phase == "THINKING" and show_think and self.think_hdr_printed and not self.ans_started:
            sep = "" if self.acc_think.endswith("\n") else "\r\n"
            _console_err.print(f"{sep}[dim]╰────────────────────────────────────────────────────────[/dim]\n")
            self.phase = "ANSWER"

        render_md = bool(get_state("render_markdown", False))
        if self.ans_started and not render_md:
            try:
                sys.stdout.write("\r\n")
                sys.stdout.flush()
            except OSError:
                pass


def _log_turn_usage(
    model: str,
    in_tok: int,
    out_tok: int,
    cost: float,
    show_stats: bool,
    ctx_used: int | None = None,
    cached_tok: int = 0,
) -> None:
    if not usage_log:
        return
    try:
        usage_log.record(model, in_tok, out_tok, cost)
        if show_stats and sys.stdout.isatty():
            ctx_max = _get_int_env("AI_MAX_TOKENS", 8192) if ctx_used is not None else None
            print(usage_log.turn_line(in_tok, out_tok, cost, ctx_used, ctx_max, cached_tok=cached_tok))
            print()
    except Exception:
        pass


def _process_stream_chunk(content: str, reasoning: str, in_think_block: bool) -> tuple[str, bool, bool]:
    if content:
        if "Final Answer:" in content:
            content = RE_FINAL_ANSWER.sub("", content).lstrip()
        if "<|tool_call" in content:
            content = RE_TOOL_CALL_BLOCK.sub("", content).replace("<|tool_call_start|>", "").replace("<|tool_call_end|>", "")

    if reasoning:
        think_part = f"<think>{reasoning}" if not in_think_block else reasoning
        if content:
            has_closer = "</think>" in content
            closer = "" if has_closer else "</think>"
            new_in_think = ("<think>" in content and content.rindex("<think>") > content.rindex("</think>")) if has_closer else False
            return f"{think_part}{closer}{content}", False, new_in_think
        return think_part, True, True

    if content:
        if in_think_block and "</think>" not in content:
            return f"</think>{content}", False, False

        if "<think>" in content and "</think>" in content:
            in_think = content.rindex("<think>") > content.rindex("</think>")
        elif "<think>" in content:
            in_think = True
        elif "</think>" in content:
            in_think = False
        else:
            in_think = in_think_block

        return content, in_think, in_think

    return "", False, in_think_block


def _calc_turn_tokens(ans_text: str, messages: list[dict[str, Any]], captured_usage: dict[str, Any] | None, is_local: bool) -> tuple[int, int]:
    if captured_usage and "completion_tokens" in captured_usage:
        return captured_usage.get("prompt_tokens", 0), captured_usage.get("completion_tokens", 0)
    if is_local:
        return sum(get_accurate_token_count(m.get("content") or "") for m in messages), get_accurate_token_count(ans_text)
    return sum(len(str(m.get("content") or "")) for m in messages) // 4, len(ans_text) // 4


def _confirm_gate(reason: str, spinner: Any) -> bool:
    is_security_event = reason.startswith(("OUT-OF-BOUNDS", "PYTHON DANGEROUS OP", "PYTHON SHELL ESCAPE"))
    return security.authorize(reason, is_security_event=is_security_event, spinner=spinner)


def _print_tool_output(spinner: Any, text: str) -> None:
    if is_calm_cli():
        return
    if sys.stdout.isatty() and text.strip():
        if spinner:
            spinner.stop()
        clean_lines = text.strip().splitlines()
        preview = clean_lines[:15]
        for line in preview:
            _console_err.print(f"    {line}", markup=False, highlight=False)
        if len(clean_lines) > 15:
            _console_err.print(f"    ... ({len(clean_lines) - 15} more lines)", style="dim")


def _run_edit_tool(name: str, args: dict[str, Any], workspace: str, spinner: Any = None) -> str:
    return tools.run_tool(name, args, workspace, confirm_gate_fn=lambda r: _confirm_gate(r, spinner), print_output_fn=lambda t: _print_tool_output(spinner, t))


def _backfill_missing_tool_results(msg_list: list[dict[str, Any]], expected_calls: list[dict[str, Any]], fallback_content: str = "[tool error] Execution halted.") -> None:
    existing_ids = {m.get("tool_call_id") for m in msg_list if m.get("role") == "tool"}
    for tc in expected_calls:
        cid = tc.get("id")
        if cid and cid not in existing_ids:
            fn_name = tc.get("function", {}).get("name", "tool")
            msg_list.append({"role": "tool", "tool_call_id": cid, "name": fn_name, "content": fallback_content})


# ── 2. Autonomous Agentic Turn Engine ────────────────────────────────────────

def agentic_turn(
    messages: list[dict[str, Any]],
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: int,
    spinner: Any,
    show_stats: bool | None = None,
    is_agent: bool = False,
    prefix: str | None = None,
) -> str | None:
    if show_stats is None:
        show_stats = bool(get_state("show_stats", True))

    workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    is_local = "localhost" in url or "127.0.0.1" in url or body.get("model") == "local-model"
    resolved_model, streamer, res = None, None, None
    max_ctx = _get_int_env("AI_MAX_TOKENS", 8192)
    is_calm = is_calm_cli()
    is_sub = _get_int_env("AI_SUBAGENT_DEPTH", 0) >= 1

    consecutive_tool_failures = 0
    tools_disabled = False
    ans_text = ""

    def _calc_msg_tokens(msg_list: list[dict[str, Any]]) -> int:
        total = 0
        for m in msg_list:
            total += get_accurate_token_count(m.get("content") or "")
            for tc in m.get("tool_calls", []):
                fn = tc.get("function", {})
                total += get_accurate_token_count(fn.get("name", ""))
                total += get_accurate_token_count(fn.get("arguments", ""))
        return total

    session = _get_session()

    for _round in range(10):
        curr_tok = _calc_msg_tokens(messages)
        if spinner and hasattr(spinner, "update_context"):
            spinner.update_context(curr_tok, max_ctx)

        if curr_tok > int(max_ctx * 0.75):
            messages[:] = prune_history(messages, max_tokens=int(max_ctx * 0.55))

        if consecutive_tool_failures >= 2:
            decomp_steer = (
                "[System Directive - Task Decomposition]: Your previous action failed repeatedly. "
                "Stop retrying the whole file. Decompose your immediate next step: "
                "1) Read the exact 15-20 lines using read_file(path, line_start, line_end) or search_code(pattern). "
                "2) Apply a targeted edit_file to only that section with unique context lines."
            )
            messages.append({"role": "user", "content": decomp_steer})
            consecutive_tool_failures = 0

        body_tools = {**body, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
        st = get_state()
        use_gnd = st.get("grounding_active", False) and bool(os.environ.get("GND_KEY") or os.environ.get("GEMINI_API_KEY"))

        if is_agent and not tools_disabled:
            is_py_mode = st.get("ipython_mode", False)
            use_map = st.get("use_map", False) or os.environ.get("AI_USE_MAP", "0") == "1"

            if is_py_mode:
                try:
                    import agent_ipython as ipython
                    active_tools = list(ipython.IPYTHON_TOOL) + [
                        t for t in tools.SMOL_TOOLS if t["function"]["name"] != "exec_python"
                    ]
                except ImportError:
                    active_tools = list(tools.SMOL_TOOLS)
                if use_map:
                    active_tools += [t for t in tools.EDIT_TOOLS if t not in active_tools]
            elif use_map:
                active_tools = list(tools.EDIT_TOOLS)
            else:
                active_tools = list(tools.SMOL_TOOLS)

            if is_sub:
                active_tools = [
                    t for t in active_tools
                    if t.get("function", {}).get("name") not in ("delegate_task", "exec_python")
                ]

            if use_gnd and hasattr(tools, "WEB_TOOL"):
                active_tools.append(tools.WEB_TOOL)

            body_tools["tools"] = active_tools
        elif use_gnd and hasattr(tools, "WEB_TOOL") and not tools_disabled:
            body_tools["tools"] = [tools.WEB_TOOL]
        else:
            body_tools.pop("tools", None)

        if spinner and not getattr(spinner, "active", False):
            user_msg_count = len([m for m in messages if m.get("role") == "user"])
            spinner.start("Preloading..." if (_round == 0 and user_msg_count <= 1) else "Working...")

        chunk_errors = 0
        try:
            res = session.post(url, json=body_tools, headers={"Content-Type": "application/json", "User-Agent": "py-agent", **headers}, timeout=timeout, stream=True)
            if res.status_code != 200:
                err_text = res.text[:200].replace("\n", " ").strip()
                if res.status_code == 400 and ("exceed" in err_text.lower() or "context" in err_text.lower()):
                    if spinner:
                        spinner.stop(leave_on_screen=False)
                    sys.stderr.write("\r\033[1;33m[sys] Context window full. Auto-compacting conversation history...\033[0m\r\n")
                    messages[:] = prune_history(messages, max_tokens=int(max_ctx * 0.5))
                    continue

                if spinner:
                    spinner.stop(leave_on_screen=False)
                sys.stderr.write(f"\r\033[1;31m[error] Server HTTP {res.status_code}: {err_text}\033[0m\r\n")
                return None

            first_chunk, acc_content, tool_calls_map, in_think_block, captured_usage, captured_timings = True, [], {}, False, None, None

            for line in res.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str.startswith("data:"):
                    continue
                data_str = line_str[5:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                try:
                    captured_usage = data.get("usage") or captured_usage
                    captured_timings = data.get("timings") or (data.get("usage") or {}).get("timings") or captured_timings

                    if m_candidate := (data.get("model") or (data.get("choices", [{}])[0].get("model") if data.get("choices") else None)):
                        if not resolved_model or resolved_model == "openrouter/free" or m_candidate != "openrouter/free":
                            resolved_model = m_candidate

                    choices = data.get("choices", [{}])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    content = delta.get("content", "") or ""
                    reasoning = delta.get("reasoning_content", "") or delta.get("thinking", "") or delta.get("reasoning", "") or ""

                    is_tool_incoming = bool(delta.get("tool_calls")) or any(k in content for k in ("<tool_call", "<function=", "<｜DSML｜", "<|tool_call"))
                    if is_tool_incoming and not is_calm and not is_sub:
                        if streamer:
                            streamer.stop()
                            streamer = None
                            first_chunk = True
                        if spinner and not spinner.active:
                            spinner.start("Drafting tool action...")

                    chunk_to_stream, is_thinking, in_think_block = _process_stream_chunk(content, reasoning, in_think_block)

                    if chunk_to_stream:
                        acc_content.append(chunk_to_stream)

                        if first_chunk:
                            first_chunk = False
                            if not is_calm and not is_sub:
                                stream_pfx = prefix or ("Agent:" if is_agent else "AI:")
                                streamer = RichStreamer(prefix=stream_pfx, spinner=spinner, round_idx=_round)
                                streamer.start()
                            if speed_test and show_stats:
                                speed_test.start()

                        if streamer and not is_calm and not is_sub:
                            streamer.update(chunk_to_stream)

                        if speed_test and show_stats:
                            speed_test.count_token(chunk_to_stream, is_thinking=is_thinking)
                    elif "<tool_call" in content or "<function=" in content:
                        acc_content.append(content)
                        if not is_calm and not is_sub and spinner and not spinner.active:
                            spinner.start("Drafting tool action...")

                    for tc in delta.get("tool_calls", []):
                        raw_idx = tc.get("index", 0)
                        try:
                            idx = int(raw_idx)
                        except (TypeError, ValueError):
                            idx = 0
                        tc_entry = tool_calls_map.setdefault(
                            idx,
                            {"id": tc.get("id", ""), "type": "function", "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}}
                        )
                        if tc.get("id"):
                            tc_entry["id"] = tc["id"]
                        if tc.get("function", {}).get("name"):
                            tc_entry["function"]["name"] = tc["function"]["name"]
                        for k in ("thought_signature", "thoughtSignature", "extra_content", "provider_specific_fields"):
                            if k in tc:
                                tc_entry[k] = tc[k]
                        arg_chunk = tc.get("function", {}).get("arguments", "")
                        if arg_chunk:
                            tc_entry["function"]["arguments"] += arg_chunk
                            if speed_test and show_stats and not is_calm:
                                speed_test.count_token(arg_chunk, is_thinking=False)
                except Exception as e:
                    chunk_errors += 1
                    if os.environ.get("AI_DEBUG") == "1" or chunk_errors <= 3:
                        sys.stderr.write(f"\r\n[debug] Stream chunk processing error: {e}\r\n")

            if chunk_errors > 3 and os.environ.get("AI_DEBUG") != "1":
                sys.stderr.write(f"\r\n[debug] Warning: {chunk_errors} stream chunks could not be parsed.\r\n")

            if streamer:
                streamer.stop()

            ans_text = "".join(acc_content)
            in_tok, out_tok = _calc_turn_tokens(ans_text, messages, captured_usage, is_local)
            final_model = resolved_model or body.get("model") or "local-model"

            calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None
            adapters_on = get_state("adapters_active", False)

            if not calls and ans_text and is_agent and adapters_on:
                calls = adapters.extract_fallback_tool_calls(ans_text) or None

            has_web_call = use_gnd and any(c.get("function", {}).get("name") == "web_search" for c in (calls or []))

            # Turn completed - dock boat ONCE and print final response
            if not calls or (not is_agent and not has_web_call):
                final_out = out_tok
                if spinner:
                    if hasattr(spinner, "update_context"):
                        spinner.update_context(in_tok + final_out, max_ctx)
                    spinner.stop(leave_on_screen=is_calm)

                clean_reply = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", ans_text).strip()
                if not clean_reply and ans_text.strip():
                    raw_fallback = re.sub(r"</?think>", "", ans_text).strip()
                    if m := re.search(r"(?:[✓✔]\s*)?Task complete:.*", raw_fallback, re.IGNORECASE):
                        clean_reply = m.group(0).strip()
                    else:
                        clean_reply = raw_fallback.splitlines()[-1].strip() if raw_fallback else ""

                render_md = bool(get_state("render_markdown", False))
                p_prefix = prefix or ("Agent: " if is_agent else "AI: ")
                p_style = "bold green" if "Agent" in p_prefix else "bold cyan"

                if is_calm and ans_text:
                    if clean_reply:
                        clean_reply = prepare_markdown(clean_reply)
                        _console.print(f"[{p_style}]{p_prefix}[/{p_style}] ", end="")
                        if render_md:
                            code_th = str(get_state("code_theme", "monokai"))
                            _console.print(Markdown(clean_reply, code_theme=code_th, justify="default"))
                        else:
                            _console.print(clean_reply, markup=False, highlight=False)
                            _console.print()
                elif render_md and streamer and clean_reply and not is_sub:
                    cols = shutil.get_terminal_size((80, 24)).columns
                    num_lines = get_cursor_up_count(streamer.acc_ans, cols)

                    try:
                        if num_lines > 0:
                            sys.stdout.write(f"\033[{num_lines}A\r\x1b[0J")
                        else:
                            sys.stdout.write("\r\x1b[0J")
                        sys.stdout.flush()
                    except OSError:
                        pass

                    clean_reply = prepare_markdown(clean_reply)
                    code_th = str(get_state("code_theme", "monokai"))
                    p_header = f"[{p_style}]{p_prefix.strip()}[/{p_style}]"
                    if clean_reply.startswith(("```", "#", "---")):
                        _console.print(f"{p_header}\n")
                        _console.print(Markdown(clean_reply, code_theme=code_th, justify="default"))
                    else:
                        _console.print(f"{p_header} ", end="")
                        _console.print(Markdown(clean_reply, code_theme=code_th, justify="default"))

                if show_stats and sys.stdout.isatty():
                    print()

                if speed_test and show_stats and not first_chunk:
                    speed_test.end(actual_out_tokens=out_tok, is_local=is_local, resolved_model=final_model, active_model=body.get("model"))

                cached_tok = 0
                if captured_usage and isinstance(captured_usage, dict):
                    details = captured_usage.get("prompt_tokens_details") or {}
                    cached_tok = (
                        details.get("cached_tokens", 0)
                        or captured_usage.get("prompt_cache_hit_tokens", 0)
                        or captured_usage.get("cached_tokens", 0)
                        or captured_usage.get("cache_read_input_tokens", 0)
                        or captured_usage.get("usageMetadata", {}).get("cachedContentTokenCount", 0)
                        or 0
                    )
                if not cached_tok and captured_timings and isinstance(captured_timings, dict):
                    cached_tok = captured_timings.get("cache_n", 0) or 0

                _log_turn_usage(final_model, in_tok, final_out, 0.0, show_stats, in_tok + final_out, cached_tok=cached_tok)
                return ans_text if ans_text else "(No response generated)"

        except KeyboardInterrupt:
            _backfill_missing_tool_results(messages, healed_calls, "[cancelled: interrupted by user]")
            if streamer:
                try:
                    streamer.stop(interrupted=True)
                except Exception:
                    pass
            raise
        except Exception as e:
            _backfill_missing_tool_results(messages, healed_calls, f"[tool error] {e}")
            if spinner:
                try:
                    spinner.stop(leave_on_screen=False)
                except Exception:
                    pass
            sys.stderr.write(f"\r\033[90m[sys] Tool execution error: {e}\033[0m\r\n")
            return None
        finally:
            if res is not None:
                try:
                    res.close()
                except Exception:
                    pass

        # ── Tool Execution Phase ─────────────────────────────────────────────
        healed_calls = []
        try:
            for call_idx, tc in enumerate(calls):
                raw_fname = tc.get("function", {}).get("name", "")
                raw_args = tc.get("function", {}).get("arguments") or ""
                if adapters_on:
                    fname, healed_dict = adapters.heal_tool_call(raw_fname, raw_args)
                else:
                    fname = raw_fname
                    healed_dict = _heal_tool_args(raw_args)

                sig = (
                    tc.get("thought_signature")
                    or tc.get("thoughtSignature")
                    or (tc.get("extra_content", {}).get("google", {}).get("thought_signature") if isinstance(tc.get("extra_content"), dict) else None)
                    or "skip_thought_signature_validator"
                )
                unique_cid = tc.get("id") or f"call_{int(time.time())}_{call_idx}_{uuid.uuid4().hex[:6]}"
                healed_calls.append({
                    "id": unique_cid,
                    "type": "function",
                    "function": {
                        "name": fname,
                        "arguments": json.dumps(healed_dict)
                    },
                    "thought_signature": sig,
                    "extra_content": {"google": {"thought_signature": sig}}
                })

            clean_ans_text = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", ans_text).strip()
            messages.append({"role": "assistant", "content": clean_ans_text or "", "tool_calls": healed_calls})

            for call_idx, tc in enumerate(healed_calls):
                fname = tc.get("function", {}).get("name", "")
                args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                brief = str(args.get("code") or args.get("symbol") or args.get("path") or args.get("command") or args.get("pattern") or args.get("goal") or "")[:100].replace("\n", " ")
                verb = TOOL_VERBS.get(fname, "working")

                if isinstance(args, dict) and "_parse_error" in args:
                    result = f"[tool error] Malformed tool arguments: {args.get('_parse_error')}"
                    res_str = result
                    consecutive_tool_failures += 1
                else:
                    if not is_calm and not is_sub and spinner and getattr(spinner, "active", False):
                        spinner.stop()

                    if not is_calm:
                        _console_err.print(f"  [dim]∗ {verb} •[/dim] [cyan]{_escape_markup(fname)}[/cyan] [dim italic]{_escape_markup(brief)}[/dim italic]")
                    if spinner and fname != "delegate_task" and not getattr(spinner, "active", False):
                        spinner.start(f"{verb.capitalize()}...")

                    t_start = time.time()
                    try:
                        result = _run_edit_tool(fname, args, workspace, spinner)
                    except Exception as e:
                        result = f"[tool error] {e}"

                    res_str = str(result) if result is not None else ""

                    if not is_calm and not is_sub and spinner and getattr(spinner, "active", False):
                        spinner.stop()

                    if not is_calm:
                        elapsed = max(0.01, time.time() - t_start)
                        _console_err.print(f"  [green]✔[/green] [dim]Done ({elapsed:.1f}s)[/dim]\n")

                scratch_threshold = max(12000, int(max_ctx * 3.5 * 0.35))

                if len(res_str) > scratch_threshold:
                    scratch_dir = os.path.join(workspace, ".agent", "scratchpad")
                    try:
                        os.makedirs(scratch_dir, exist_ok=True)
                        safe_fname = re.sub(r"[^A-Za-z0-9_.-]", "_", fname)[:40] or "tool"
                        scratch_file = os.path.join(scratch_dir, f"{safe_fname}_{int(time.time())}.txt")
                        with open(scratch_file, "w", encoding="utf-8") as sf:
                            sf.write(res_str)
                        rel_scratch = os.path.relpath(scratch_file, workspace)
                        preview_len = int(scratch_threshold * 0.75)
                        pruned_result = (
                            res_str[:preview_len]
                            + f"\n... [Output truncated: Full {len(res_str):,} chars saved to '{rel_scratch}'. "
                            + f"Use read_file('{rel_scratch}', line_start, line_end) to inspect specific blocks.]"
                        )
                    except OSError:
                        pruned_result = res_str[:6000] + "\n... [snipped]"
                else:
                    pruned_result = res_str

                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned_result})

                if res_str.strip().startswith("[denied]"):
                    for rem_tc in healed_calls[call_idx + 1:]:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": rem_tc.get("id", ""),
                            "name": rem_tc.get("function", {}).get("name", ""),
                            "content": "[cancelled: prior action declined by user]",
                        })
                    messages.append({
                        "role": "user",
                        "content": "[System Directive]: Action was explicitly declined by the user. Do not retry or attempt alternative workarounds for this resource.",
                    })
                    return "[denied] Action cancelled by user."

                if fname == "exec_python" and RE_FINAL_ANSWER_SENTINEL.search(res_str):
                    messages.append({
                        "role": "user",
                        "content": "[System Directive]: final_answer() was received. Output your concise summary to the user now. Do not call any further tools.",
                    })
                    tools_disabled = True

                if res_str.startswith("[error") or res_str.startswith("[tool error"):
                    consecutive_tool_failures += 1
                else:
                    consecutive_tool_failures = 0

                if fname == "read_file" and len(messages) >= 4:
                    prev_tools = [m for m in messages[-4:] if m.get("role") == "tool" and m.get("name") == "read_file"]
                    if len(prev_tools) >= 2:
                        messages.append({"role": "user", "content": "[System Directive]: File already inspected. Do not read again. Proceed immediately to edit, test, or final answer."})

        except KeyboardInterrupt:
            _backfill_missing_tool_results(messages, healed_calls, "[cancelled: interrupted by user]")
            if streamer:
                try:
                    streamer.stop(interrupted=True)
                except Exception:
                    pass
            raise
        except Exception as e:
            _backfill_missing_tool_results(messages, healed_calls, f"[tool error] {e}")
            if spinner:
                try:
                    spinner.stop(leave_on_screen=False)
                except Exception:
                    pass
            sys.stderr.write(f"\r\033[90m[sys] Tool execution error: {e}\033[0m\r\n")
            return None

    if spinner:
        spinner.stop(leave_on_screen=False)
    sys.stderr.write("\r\033[1;33m[sys] Agent loop limit reached (10 rounds exhausted without final answer).\033[0m\r\n")
    return ans_text or "(Agent loop limit reached)"


# ── 3. High-Level Stream Entrypoint ──────────────────────────────────────────

def stream_response(
    messages: list[dict[str, Any]],
    prefix: str = "AI: ",
    show_stats: bool | None = None,
    thinking_budget: int = 0,
    is_agent: bool = False,
) -> str | None:
    if show_stats is None:
        show_stats = bool(get_state("show_stats", True))

    is_sub = _get_int_env("AI_SUBAGENT_DEPTH", 0) >= 1
    is_calm = is_calm_cli()
    max_ctx = _get_int_env("AI_MAX_TOKENS", 8192)
    initial_toks = sum(get_accurate_token_count(m.get("content") or "") for m in messages)

    import agent_ui as ui
    spinner = None if is_sub else (ui.CalmBoatSpinner(tokens_used=initial_toks, max_tokens=max_ctx) if is_calm else ui.InlineSpinner())

    try:
        configs = agent_cloud.get_active_configs(messages)
        enable_think = thinking_budget > 0
        think_kwargs = (
            {
                "thinking_budget_tokens": thinking_budget,
                "reasoning_budget": thinking_budget,
                "chat_template_kwargs": {"enable_thinking": True},
            }
            if enable_think
            else {
                "thinking_budget_tokens": 0,
                "reasoning_budget": 0,
                "chat_template_kwargs": {"enable_thinking": False},
            }
        )

        if not configs:
            configs = [("http://localhost:8080/v1/chat/completions", {}, {"messages": messages, "stream": True, **think_kwargs}, 180)]

        url, headers, body, timeout = configs[0]
        if "localhost" in url or "127.0.0.1" in url or body.get("model") == "local-model":
            body = {**body, "max_tokens": 2048, **think_kwargs}

        ans = agentic_turn(
            messages,
            url,
            headers,
            body,
            timeout,
            spinner,
            show_stats,
            is_agent=is_agent,
            prefix=prefix,
        )
        if spinner:
            spinner.stop(leave_on_screen=False)
        return ans
    except KeyboardInterrupt:
        if spinner:
            try:
                spinner.stop(leave_on_screen=False)
            except Exception:
                pass
        sys.stderr.write("\r\x1b[2K\033[90m[sys] Interrupted.\033[0m\r\n")
        return None
