#!/usr/bin/env python3
"""Core Module - Streaming SSE, dynamic tool execution, & Rich rendering [Hardened Production Ready]"""

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
    estimate_token_count,
    get_accurate_token_count,
    prune_history,
    show_memory_status,
)
import agent_ipython as ipython
import agent_security as security
import agent_tools as tools
import agent_ui as ui
import agent_vision as vision
from agent_vision import (
    _get_img_config,
    describe_image_gemini,
    preprocess_multimodal_messages,
)
import requests
from rich.console import Console

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
STATE_FILE: str = os.path.join(CFG_DIR, ".state.json")


def _get_console(stderr: bool = False) -> Console:
    cols = max(40, shutil.get_terminal_size((80, 24)).columns - 2)
    return Console(stderr=stderr, width=cols)


_console, _console_err = _get_console(False), _get_console(True)

# Thread-local HTTP session storage for safe concurrency
_local_session = threading.local()


def _get_session() -> requests.Session:
    if not hasattr(_local_session, "session"):
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
RE_TOOL_CALL_BLOCK = re.compile(r"<\|tool_call_start\|>.*?<\|tool_call_end\|>", re.DOTALL)

TOOL_VERBS: dict[str, str] = getattr(tools, "TOOL_VERBS", {})

DEFAULTS = {
    "show_stats": False, "memory_active": False, "box_style": 1, "yolo_mode": True,
    "show_thinking": True, "reasoning_active": True, "reasoning_budget": 500,
    "compact_mode": 0, "sidebar_hidden": False, "footer_hidden": True, "tips_card_hidden": False,
    "tui_theme": "code1", "voice_auto_submit": True, "tts_enabled": False, "tui_borders_enabled": True,
    "render_markdown": True, "adapters_active": False, "calm_mode": False
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
    global _state_cache, _state_mtime
    with _state_lock:
        try:
            if os.path.exists(STATE_FILE):
                mtime = os.path.getmtime(STATE_FILE)
                if mtime != _state_mtime or not _state_cache:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        _state_cache = json.load(f)
                    _state_mtime = mtime
        except (OSError, json.JSONDecodeError):
            pass
        merged = {**DEFAULTS, **_state_cache}
        return merged.get(key, default) if key else merged


def save_state(key: str, value: Any) -> None:
    global _state_cache, _state_mtime
    with _state_lock:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    _state_cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
        st = {**DEFAULTS, **_state_cache}
        st[key] = value
        tmp = f"{STATE_FILE}.tmp.{os.getpid()}.{threading.get_ident()}"
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2)
            os.replace(tmp, STATE_FILE)
            _state_cache = st
            _state_mtime = os.path.getmtime(STATE_FILE)
        except OSError:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


def workspace_safe_name(workspace_path: str, home_dir: str = "") -> str:
    home, ws = os.path.realpath(home_dir or os.path.expanduser("~")), os.path.realpath(workspace_path)
    return "home-chat" if ws == home else (ws.replace("/", "-").strip("-.") or "home-chat")


def is_calm_cli() -> bool:
    """Strict gate: Calm mode only runs in interactive CLI terminals (never in TUI, WebUI, PyCode, or subagents)."""
    if os.environ.get("AI_SURFACE") == "1" or os.environ.get("TEXTUAL") or _get_int_env("AI_SUBAGENT_DEPTH", 0) >= 1:
        return False
    if not (sys.stdout.isatty() and sys.stderr.isatty()):
        return False
    return bool(get_state("calm_mode", False))


def run_mod(module_name: str, *args: str) -> str:
    for base in (os.path.join(CFG_DIR, "modules"), os.path.join(CFG_DIR, "tools"), CFG_DIR):
        target = os.path.join(base, module_name)
        if os.path.isfile(target):
            try:
                cmd = [sys.executable, target] + list(args) if target.endswith(".py") else [target] + list(args)
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                return (res.stdout or res.stderr or "").strip()
            except Exception as e:
                return f"[error: {e}]"
    return ""


# ── 1. Streaming Rich Streamer ───────────────────────────────────────────────

class RichStreamer:
    def __init__(self, prefix: str = "", active: bool = True, spinner: Any = None) -> None:
        self.prefix, self.active, self.spinner = prefix, active and sys.stdout.isatty(), spinner
        self.acc_think, self.acc_ans, self.phase, self.think_hdr_printed, self.ans_started = "", "", "INIT", False, False

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
                self.phase, token = "ANSWER", token.split("</think>", 1)[1] if "</think>" in token else ""
            if self.phase != "THINKING" and token:
                try:
                    sys.stdout.write(token.replace("\r\n", "\n").replace("\n", "\r\n"))
                    sys.stdout.flush()
                except OSError:
                    pass
            return

        if "<think>" in token:
            self.phase = "THINKING"
            token = token.replace("<think>", "")

        show_think = os.environ.get("AI_SHOW_THINKING", "1") == "1"

        if "</think>" in token:
            parts = token.split("</think>", 1)
            if parts[0]:
                self.update(parts[0])
            if show_think and self.think_hdr_printed:
                sep = "" if self.acc_think.endswith("\n") else "\r\n"
                _console_err.print(f"{sep}[dim]╰────────────────────────────────────────────────────────[/dim]")
                sys.stderr.flush()
            self.phase = "ANSWER"
            if self.spinner and not self.ans_started:
                self.spinner.start("Drafting tool action...")
            if len(parts) > 1 and parts[1]:
                self.update(parts[1])
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
                p_str = f"{p_clean} " if p_clean else ""
                p_style = "\033[1;32m" if "Agent" in p_clean else "\033[1;36m"
                if p_str:
                    try:
                        sys.stdout.write(f"{p_style}{p_str}\033[0m")
                        sys.stdout.flush()
                    except OSError:
                        pass
                self.acc_ans += p_str

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
        if self.phase == "THINKING" and show_think and self.think_hdr_printed:
            sep = "" if self.acc_think.endswith("\n") else "\r\n"
            _console_err.print(f"{sep}[dim]╰────────────────────────────────────────────────────────[/dim]")
            self.phase = "ANSWER"

        if self.ans_started:
            try:
                sys.stdout.write("\r\n")
                sys.stdout.flush()
            except OSError:
                pass


def _log_turn_usage(model: str, in_tok: int, out_tok: int, cost: float, show_stats: bool, ctx_used: int | None = None, cached_tok: int = 0, *args: Any, **kwargs: Any) -> None:
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
        return (f"<think>{reasoning}", True, True) if not in_think_block else (reasoning, True, True)
    if content:
        if in_think_block and "</think>" not in content:
            return f"</think>{content}", False, False
        in_think = True if "<think>" in content else (False if "</think>" in content else in_think_block)
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
        # Copy-safe 4-space indent; disable markup to prevent bracketed logs ([Errno 2]) from crashing Rich
        clean_lines = text.strip().splitlines()
        preview = clean_lines[:15]
        for line in preview:
            _console_err.print(f"    {line}", markup=False, highlight=False)
        if len(clean_lines) > 15:
            _console_err.print(f"    ... ({len(clean_lines) - 15} more lines)", style="dim")


def _run_edit_tool(name: str, args: dict[str, Any], workspace: str, spinner: Any = None) -> str:
    return tools.run_tool(name, args, workspace, confirm_gate_fn=lambda r: _confirm_gate(r, spinner), print_output_fn=lambda t: _print_tool_output(spinner, t))


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
            messages = prune_history(messages, max_tokens=int(max_ctx * 0.55))

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

            if is_py_mode and ipython:
                active_tools = list(ipython.IPYTHON_TOOL) + [
                    t for t in tools.SMOL_TOOLS if t["function"]["name"] != "exec_python"
                ]
                if use_map:
                    active_tools += [t for t in tools.EDIT_TOOLS if t not in active_tools]
            elif use_map:
                active_tools = list(tools.EDIT_TOOLS)
            else:
                active_tools = list(tools.SMOL_TOOLS)

            if _get_int_env("AI_SUBAGENT_DEPTH", 0) >= 1:
                active_tools = [t for t in active_tools if t.get("function", {}).get("name") != "delegate_task"]

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
        try:
            res = session.post(url, json=body_tools, headers={"Content-Type": "application/json", "User-Agent": "py-agent", **headers}, timeout=timeout, stream=True)
            if res.status_code != 200:
                err_text = res.text[:200].replace("\n", " ").strip()
                if res.status_code == 400 and ("exceed" in err_text.lower() or "context" in err_text.lower()):
                    if spinner:
                        spinner.stop(leave_on_screen=False)
                    sys.stderr.write("\r\033[1;33m[sys] Context window full. Auto-compacting conversation history...\033[0m\r\n")
                    messages = prune_history(messages, max_tokens=int(max_ctx * 0.5))
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
                    captured_timings = data.get("timings") or data.get("usage", {}).get("timings") or captured_timings

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
                    if is_tool_incoming and not is_calm:
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
                            if not is_calm:
                                stream_pfx = prefix or ("Agent:" if is_agent else "AI:")
                                streamer = RichStreamer(prefix=stream_pfx, spinner=spinner)
                                streamer.start()
                            if speed_test and show_stats:
                                speed_test.start()

                        if streamer and not is_calm:
                            streamer.update(chunk_to_stream)

                        if speed_test and show_stats:
                            speed_test.count_token(chunk_to_stream, is_thinking=is_thinking)
                    elif "<tool_call" in content or "<function=" in content:
                        acc_content.append(content)
                        if not is_calm and spinner and not spinner.active:
                            spinner.start("Drafting tool action...")

                    for tc in delta.get("tool_calls", []):
                        idx = tc.get("index", 0)
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
                    if os.environ.get("AI_DEBUG") == "1":
                        sys.stderr.write(f"\r\n[debug] Stream chunk processing error: {e}\r\n")

            if streamer and not is_calm:
                print()

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
                tool_toks = sum(get_accurate_token_count(m.get("content") or "") for m in messages if m.get("role") in ("assistant", "tool"))
                final_out = max(out_tok, tool_toks)
                if spinner:
                    if hasattr(spinner, "update_context"):
                        spinner.update_context(in_tok + final_out, max_ctx)
                    spinner.stop(leave_on_screen=is_calm)

                if is_calm and ans_text:
                    p_prefix = prefix or ("Agent: " if is_agent else "AI: ")
                    clean_reply = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", ans_text).strip()
                    if clean_reply:
                        _console.print(f"[bold green]{p_prefix}[/bold green]", end="")
                        _console.print(clean_reply, markup=False, highlight=False)

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

            healed_calls = []
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

                if not is_calm and spinner and getattr(spinner, "active", False):
                    spinner.stop()

                if not is_calm:
                    _console_err.print(f"\n  [dim]∗ {verb} •[/dim] [cyan]{fname}[/cyan] [dim italic]{brief}[/dim italic]")
                if spinner and fname != "delegate_task" and not getattr(spinner, "active", False):
                    spinner.start(f"{verb.capitalize()}...")

                t_start = time.time()
                try:
                    result = _run_edit_tool(fname, args, workspace, spinner)
                except Exception as e:
                    result = f"[tool error] {e}"

                if not is_calm and spinner and getattr(spinner, "active", False):
                    spinner.stop()

                if not is_calm:
                    elapsed = max(0.01, time.time() - t_start)
                    _console_err.print(f"  [green]✔[/green] [dim]Done ({elapsed:.1f}s)[/dim]")

                scratch_threshold = max(12000, int(max_ctx * 3.5 * 0.35))

                if len(result) > scratch_threshold:
                    scratch_dir = os.path.join(workspace, ".agent", "scratchpad")
                    os.makedirs(scratch_dir, exist_ok=True)
                    scratch_file = os.path.join(scratch_dir, f"{fname}_{int(time.time())}.txt")
                    try:
                        with open(scratch_file, "w", encoding="utf-8") as sf:
                            sf.write(result)
                        rel_scratch = os.path.relpath(scratch_file, workspace)
                        preview_len = int(scratch_threshold * 0.75)
                        pruned_result = (
                            result[:preview_len]
                            + f"\n... [Output truncated: Full {len(result):,} chars saved to '{rel_scratch}'. "
                            + f"Use read_file('{rel_scratch}', line_start, line_end) to inspect specific blocks.]"
                        )
                    except OSError:
                        pruned_result = result[:6000] + "\n... [snipped]"
                else:
                    pruned_result = result

                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned_result})

                # Check for explicit user decline; backfill unexecuted parallel calls to maintain schema consistency
                if str(result).strip().startswith("[denied]"):
                    for rem_tc in healed_calls[call_idx + 1:]:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": rem_tc.get("id", ""),
                            "name": rem_tc.get("function", {}).get("name", ""),
                            "content": "[cancelled: prior action declined by user]",
                        })
                    messages.append({
                        "role": "user",
                        "content": "[System Notice]: Action was explicitly declined by the user. Do not retry or attempt alternative workarounds for this resource.",
                    })
                    return "[denied] Action cancelled by user."

                # Line-anchored check for Final Answer in exec_python tool output
                if fname == "exec_python" and RE_FINAL_ANSWER_SENTINEL.search(result):
                    messages.append({
                        "role": "user",
                        "content": "[System Directive]: final_answer() was received. Output your concise summary to the user now. Do not call any further tools.",
                    })
                    tools_disabled = True
                    body_tools.pop("tools", None)

                if result.startswith("[error") or result.startswith("[tool error"):
                    consecutive_tool_failures += 1
                else:
                    consecutive_tool_failures = 0

                if fname == "read_file" and len(messages) >= 4:
                    prev_tools = [m for m in messages[-4:] if m.get("role") == "tool" and m.get("name") == "read_file"]
                    if len(prev_tools) >= 2:
                        messages.append({"role": "user", "content": "[System Directive]: File already inspected. Do not read again. Proceed immediately to edit, test, or final answer."})

        except KeyboardInterrupt:
            if streamer:
                try:
                    streamer.stop(interrupted=True)
                except Exception:
                    pass
            if spinner:
                try:
                    spinner.stop(leave_on_screen=False)
                except Exception:
                    pass
            raise
        except Exception as e:
            if spinner:
                try:
                    spinner.stop(leave_on_screen=False)
                except Exception:
                    pass
            err_msg = str(e)
            if "Failed to establish a new connection" in err_msg or "Connection refused" in err_msg:
                if "8080" in url or "localhost" in url or "127.0.0.1" in url:
                    sys.stderr.write("\r\033[1;31m[error] Local model not loaded (server offline at localhost:8080).\033[0m\r\n")
                else:
                    sys.stderr.write(f"\r\033[1;31m[error] Connection refused to {url}.\033[0m\r\n")
            else:
                sys.stderr.write(f"\r\033[90m[sys] API response error: {err_msg}\033[0m\r\n")
            return None
        finally:
            if res is not None:
                try:
                    res.close()
                except Exception:
                    pass

    if spinner:
        spinner.stop(leave_on_screen=False)
    sys.stderr.write("\r\033[1;33m[sys] Agent loop limit reached (10 rounds exhausted without final answer).\033[0m\r\n")
    return ans_text or "(Agent loop limit reached)"


# ── 3. High-Level Stream Entrypoint ──────────────────────────────────────────

def stream_response(
    messages: list[dict[str, Any]],
    prefix: str = "AI: ",
    cfg_dir: str = "",
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
