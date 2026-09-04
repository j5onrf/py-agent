#!/usr/bin/env python3
"""Core Module - Streaming SSE, dynamic tool execution, & Rich rendering [Universal High-Performance Engine]"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request as urlreq
from typing import Any

import agent_adapters as adapters
import agent_cloud
import agent_ipython as ipython
import agent_memories as memories
import agent_tools as tools
import agent_ui as ui
import requests
from rich.box import ROUNDED
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
STATE_FILE: str = os.path.join(CFG_DIR, ".state.json")
SESSIONS_DIR: str = os.path.join(CFG_DIR, "projects", "database")


def _get_console(stderr: bool = False) -> Console:
    cols = max(40, shutil.get_terminal_size((80, 24)).columns - 2)
    return Console(stderr=stderr, width=cols)


_console, _console_err, _session = _get_console(False), _get_console(True), requests.Session()

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
RE_THINKING_TITLE = re.compile(r"^\s*Thinking Process:\s*", re.IGNORECASE)
RE_FINAL_ANSWER = re.compile(r"^\s*Final Answer:\s*", re.IGNORECASE)
RE_MULTIPLE_NEWLINES = re.compile(r"\n{2,}")
RE_JSON_OBJECT = re.compile(r"\{[\s\S]*\}")
RE_TOOL_CALL_BLOCK = re.compile(r"<\|tool_call_start\|>.*?<\|tool_call_end\|>", re.DOTALL)
RE_ATTACHED_IMAGE = re.compile(r'\[(?:Attached\s+)?(?:image|file)[^\]]*?saved\s+at:\s*([^\]]+)\]', re.IGNORECASE)

_TPM_SKIP_QUERIES = frozenset({"hello", "hi", "hey", "exit", "quit", "q", "/clear", "/reset", "/stats", "/tok", "/m", "/r"})
_TPM_BLACKLIST = frozenset({"files", "file", "file_list", "project", "code", "description", "features", "dependencies", "project_type", "directory", "folder", "workspace"})

TOOL_VERBS: dict[str, str] = getattr(tools, "TOOL_VERBS", {})

DEFAULTS = {
    "show_stats": True, "memory_active": False, "box_style": 1, "yolo_mode": False,
    "show_thinking": True, "reasoning_active": False, "reasoning_budget": 500,
    "compact_mode": 0, "sidebar_hidden": False, "footer_hidden": True, "tips_card_hidden": False,
    "tui_theme": "code1", "voice_auto_submit": True, "tts_enabled": False, "tui_borders_enabled": True,
    "render_markdown": True
}

try:
    import agent_usage as usage_log
except ImportError:
    usage_log = None
try:
    import speed_test
except ImportError:
    speed_test = None

_state_cache: dict[str, Any] = {}
_state_mtime: float = 0.0


def _get_img_config() -> tuple[str, str]:
    """Retrieves vision model and API key from environment or .env files."""
    k = os.environ.get("IMG_VOICE", "") or os.environ.get("IMG_KEY", "") or os.environ.get("GEM_VOICE", "")
    m = os.environ.get("IMG_MODEL", "") or os.environ.get("GEM_MODEL", "") or "gemini-3.5-flash-lite"
    if not k:
        for p in (os.path.join(CFG_DIR, ".env"), os.path.expanduser("~/.config/local-ai/.env"), ".env"):
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for l in f:
                            if (s := l.strip()) and not s.startswith("#"):
                                if (s.startswith("IMG_VOICE=") or s.startswith("IMG_KEY=") or s.startswith("GEM_VOICE=")) and not k:
                                    k = s.split("=", 1)[1].strip().strip("'\"")
                                if (s.startswith("IMG_MODEL=") or s.startswith("GEM_MODEL=")) and not os.environ.get("IMG_MODEL"):
                                    m = s.split("=", 1)[1].strip().strip("'\"")
                except Exception:
                    pass
    return k.strip(), m.strip() or "gemini-3.5-flash-lite"


def describe_image_gemini(target: Any) -> str:
    """Pre-processes images via Gemini Flash Lite vision for text-only local models."""
    key, model = _get_img_config()
    if not key:
        return "[Error: IMG_VOICE not configured in .env for vision]"
    mime, b64 = "image/png", ""
    try:
        if isinstance(target, dict):
            src = target.get("source", {}) if isinstance(target.get("source"), dict) else {}
            b64 = src.get("data") or target.get("data") or target.get("blob") or ""
            mime = src.get("media_type") or target.get("mimeType") or target.get("mime_type") or "image/png"
            if not b64 and (u := (target.get("image_url", {}).get("url") if isinstance(target.get("image_url"), dict) else target.get("image_url")) or target.get("url") or target.get("path") or src.get("url")):
                return describe_image_gemini(str(u))
        elif isinstance(target, str):
            c = target.strip().strip("'\"").strip()
            if c.startswith("data:image/"):
                h, b64 = c.split(",", 1)
                mime = h.split(";")[0].replace("data:", "")
            elif c.startswith(("http://", "https://")):
                url = c.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/") if ("github.com/" in c and "/blob/" in c) else c
                req = urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36", "Accept": "image/*,*/*;q=0.8"})
                with urlreq.urlopen(req, timeout=15) as resp:
                    b64, ct = base64.b64encode(resp.read()).decode("utf-8"), resp.headers.get_content_type()
                    mime = ct if ct and ct.startswith("image/") else ("image/jpeg" if any(x in url.lower() for x in (".jpg", ".jpeg")) else ("image/webp" if ".webp" in url.lower() else "image/png"))
            else:
                p = urllib.parse.unquote(c[7:]) if c.startswith("file://") else c
                ws = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
                rf = next((f for f in (os.path.expanduser(p), os.path.join(ws, p), os.path.join(os.getcwd(), p), os.path.join(os.path.expanduser("~"), p)) if os.path.isfile(f)), None)
                if rf:
                    ext = os.path.splitext(rf)[1].lower()
                    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}.get(ext, "image/png")
                    with open(rf, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                elif len(c) > 100 and not any(c.startswith(x) for x in ("/", "~", ".", "file:")):
                    b64 = c
                else:
                    return f"[Error: Image file not found at '{target}']"
    except Exception as e:
        return f"[Error loading image: {e}]"

    if not b64:
        return "[Error: Empty image payload]"

    sys_p = "Provide a comprehensive, accurate, and objective description of the image. Transcribe any visible text, code, terminal logs, error messages, line numbers, or data verbatim with exact formatting. Describe all visual subjects, objects, UI layouts, diagrams, charts, colors, and scenes in clear, precise detail."
    payload = {"contents": [{"parts": [{"text": sys_p}, {"inline_data": {"mime_type": mime, "data": b64}}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}}
    try:
        req = urlreq.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlreq.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if "text" in p).strip() or "[No visual elements detected]"
    except Exception as e:
        return f"[Vision Exception: {e}]"


def preprocess_multimodal_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Inspects messages for attached images and runs Gemini OCR/Vision pre-processing."""
    processed, (_, model) = [], _get_img_config()
    for msg in messages:
        c = msg.get("content")
        if isinstance(c, str):
            if paths := RE_ATTACHED_IMAGE.findall(c):
                va = [f"[Visual Analysis ({model})]:\n{describe_image_gemini(p.strip().strip('\'\"'))}" for p in paths]
                txt = RE_ATTACHED_IMAGE.sub("", c).strip()
                processed.append({**msg, "content": "\n\n".join(va + ([f"User Question: {txt}"] if txt else []))})
            else:
                processed.append(msg)
        elif isinstance(c, list):
            tp, va = [], []
            for it in c:
                if isinstance(it, str):
                    if paths := RE_ATTACHED_IMAGE.findall(it):
                        va.extend(f"[Visual Analysis ({model})]:\n{describe_image_gemini(p.strip().strip('\'\"'))}" for p in paths)
                        if clean := RE_ATTACHED_IMAGE.sub("", it).strip():
                            tp.append(clean)
                    else:
                        tp.append(it)
                elif isinstance(it, dict):
                    if it.get("type") == "text":
                        raw = it.get("text", "")
                        if paths := RE_ATTACHED_IMAGE.findall(raw):
                            va.extend(f"[Visual Analysis ({model})]:\n{describe_image_gemini(p.strip().strip('\'\"'))}" for p in paths)
                            if clean := RE_ATTACHED_IMAGE.sub("", raw).strip():
                                tp.append(clean)
                        elif raw:
                            tp.append(raw)
                    else:
                        res = describe_image_gemini(it)
                        if not res.startswith("[Error: Empty image"):
                            va.append(f"[Visual Analysis ({model})]:\n{res}")
            user_txt = "\n".join(t.strip() for t in tp if t.strip())
            processed.append({**msg, "content": "\n\n".join(va + ([f"User Question: {user_txt}"] if (user_txt and va) else ([user_txt] if user_txt else [])))})
        else:
            processed.append(msg)
    return processed


def _heal_tool_args(raw: str) -> dict[str, Any]:
    """Heals malformed JSON tool arguments via modular adapter."""
    return adapters.heal_json_args(raw)


def get_state(key: str = "", default: Any = None) -> Any:
    global _state_cache, _state_mtime
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
    st = get_state()
    st[key] = value
    tmp = f"{STATE_FILE}.tmp"
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=2)
        os.replace(tmp, STATE_FILE)
        _state_cache, _state_mtime = st, os.path.getmtime(STATE_FILE)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)


def workspace_safe_name(workspace_path: str, home_dir: str = "") -> str:
    home, ws = os.path.realpath(home_dir or os.path.expanduser("~")), os.path.realpath(workspace_path)
    return "home" if ws == home else (ws.replace("/", "-").strip("-.") or "home")


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


def background_tpm_update(user_msg: str, assistant_msg: str, workspace: str, workspace_path: str) -> None:
    clean = user_msg.lower().strip()
    if len(clean) < 8 or clean in _TPM_SKIP_QUERIES:
        return
    try:
        ex_facts = memories.tpm_get(workspace)
        sys_p = "You are an async memory compiler. Extract ONLY persistent facts, roles, or preferences about the HUMAN USER. Output ONLY a flat JSON object or {} if no user facts exist."
        payload = {"messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": f"### Profile:\n{ex_facts or 'None'}\n\n### Turn:\nUser: {user_msg}\nAssistant: {assistant_msg}\n\nJSON:"}], "stream": False}
        req = urlreq.Request("http://localhost:8080/v1/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlreq.urlopen(req, timeout=10) as resp:
            out = json.loads(resp.read().decode())["choices"][0]["message"].get("content", "")
        if (m := RE_JSON_OBJECT.search(out)) and (parsed := {str(k).strip().lower(): str(v).strip() for k, v in json.loads(m.group(0)).items() if k and v is not None and str(k).strip().lower() not in _TPM_BLACKLIST}):
            memories.tpm_reconcile(workspace, parsed)
            if (res := memories.tpm_get(workspace)) and workspace_path and os.path.isdir(workspace_path) and os.path.realpath(workspace_path) not in (os.path.realpath(os.path.expanduser("~")), os.path.realpath(CFG_DIR)):
                md_dir = os.path.join(workspace_path, ".agent")
                os.makedirs(md_dir, exist_ok=True)
                with open(os.path.join(md_dir, "tpm.md"), "w", encoding="utf-8") as f:
                    f.write(res + "\n")
    except Exception:
        pass


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
            tok = RE_MULTIPLE_NEWLINES.sub("\n", RE_THINKING_TITLE.sub("", token.replace("\\n", "\n")))
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
            tok = RE_FINAL_ANSWER.sub("", token.replace("\\n", "\n"))
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


def _log_turn_usage(model: str, in_tok: int, out_tok: int, cost: float, show_stats: bool, ctx_used: int | None = None, user_msg: str = "", assistant_msg: str = "") -> None:
    try:
        ws = os.environ.get("AI_WORKSPACE_PATH")
        if ws and os.path.isdir(ws) and os.path.realpath(ws) not in (os.path.realpath(os.path.expanduser("~")), os.path.realpath(CFG_DIR)):
            agent_dir = os.path.join(ws, ".agent")
            os.makedirs(agent_dir, exist_ok=True)
            with open(os.path.join(agent_dir, "session.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"timestamp": int(time.time()), "user_msg": user_msg, "assistant_msg": assistant_msg, "model": model, "in_tok": in_tok, "out_tok": out_tok}) + "\n")
    except OSError:
        pass
    if not usage_log:
        return
    try:
        usage_log.record(model, in_tok, out_tok, cost)
        if show_stats and sys.stdout.isatty():
            ctx_max = int(os.environ.get("AI_MAX_TOKENS", 8192)) if ctx_used is not None else None
            print(usage_log.turn_line(in_tok, out_tok, cost, ctx_used, ctx_max))
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
    if spinner:
        spinner.stop()
    is_tty = (hasattr(sys, "__stdout__") and sys.__stdout__ and sys.__stdout__.isatty()) or sys.stdout.isatty()
    return is_tty and ui.confirm_tool(reason)


def _print_tool_output(spinner: Any, text: str) -> None:
    if sys.stdout.isatty() and text.strip():
        if spinner:
            spinner.stop("Done")
        if any(k in text for k in ("#", "|", "```")):
            _console_err.print(Markdown(text, code_theme="ansi_dark"))
        else:
            _console_err.print(text)


def _run_edit_tool(name: str, args: dict[str, Any], workspace: str, spinner: Any = None) -> str:
    return tools.run_tool(name, args, workspace, confirm_gate_fn=lambda r: _confirm_gate(r, spinner), print_output_fn=lambda t: _print_tool_output(spinner, t))


def agentic_turn(messages: list[dict[str, Any]], url: str, headers: dict[str, str], body: dict[str, Any], timeout: int, spinner: Any, show_stats: bool = False, is_agent: bool = False) -> str | None:
    workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    is_local = "localhost" in url or "127.0.0.1" in url or body.get("model") == "local-model"
    resolved_model, streamer, res = None, None, None
    max_ctx = int(os.environ.get("AI_MAX_TOKENS", 8192))

    consecutive_tool_failures = 0

    for _round in range(10):
        if sum(get_accurate_token_count(m.get("content") or "") for m in messages) > int(max_ctx * 0.8):
            messages = prune_history(messages, max_tokens=int(max_ctx * 0.6))

        if consecutive_tool_failures >= 2:
            decomp_steer = (
                "[Harness Directive - Task Decomposition]: Your previous action failed repeatedly. "
                "Stop retrying the whole file. Decompose your immediate next step: "
                "1) Read the exact 15-20 lines using read_file(path, line_start, line_end) or search_code(pattern). "
                "2) Apply a targeted edit_file to only that section with unique context lines."
            )
            messages.append({"role": "system", "content": decomp_steer})
            consecutive_tool_failures = 0

        body_tools = {**body, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
        st = get_state()
        use_gnd = st.get("grounding_active", False)

        if is_agent:
            active_skill = os.environ.get("AI_ACTIVE_SKILL", "").lower()
            is_py_mode = st.get("ipython_mode", False)
            use_map = st.get("use_map", False) or os.environ.get("AI_USE_MAP", "0") == "1"

            if is_py_mode and ipython:
                active_tools = list(ipython.IPYTHON_TOOL)
                if use_map:
                    active_tools += [t for t in tools.EDIT_TOOLS if t["function"]["name"] != "exec_python"]
            elif use_map:
                active_tools = list(tools.EDIT_TOOLS)
            else:
                active_tools = list(getattr(tools, "LEAN_TOOLS", tools.EDIT_TOOLS))

            # RECURSION GUARD: Child sub-agents cannot see or call delegate_task
            if int(os.environ.get("AI_SUBAGENT_DEPTH", "0")) >= 1:
                active_tools = [t for t in active_tools if t.get("function", {}).get("name") != "delegate_task"]

            if use_gnd and hasattr(tools, "WEB_TOOL"):
                active_tools.append(tools.WEB_TOOL)

            body_tools["tools"] = active_tools
        elif use_gnd and hasattr(tools, "WEB_TOOL"):
            body_tools["tools"] = [tools.WEB_TOOL]

        if spinner:
            spinner.start("Working...")
        try:
            res = _session.post(url, json=body_tools, headers={"Content-Type": "application/json", **headers}, timeout=timeout, stream=True)
            if res.status_code != 200:
                err_text = res.text[:200].replace("\n", " ").strip()
                if spinner:
                    spinner.stop()
                sys.stderr.write(f"\r\033[1;31m[error] Server HTTP {res.status_code}: {err_text}\033[0m\r\n")
                return None

            first_chunk, acc_content, tool_calls_map, in_think_block, captured_usage = True, [], {}, False, None

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
                    captured_usage = data.get("usage") or captured_usage
                    resolved_model = data.get("model") or resolved_model
                    choices = data.get("choices", [{}])
                    if not choices:
                        continue

                    finish_reason = choices[0].get("finish_reason")
                    delta = choices[0].get("delta", {})

                    content = delta.get("content", "") or ""
                    reasoning = delta.get("reasoning_content", "") or delta.get("thinking", "") or delta.get("reasoning", "") or ""

                    is_tool_incoming = bool(delta.get("tool_calls")) or any(k in content for k in ("<tool_call", "<function=", "<｜DSML｜", "<|tool_call"))
                    if is_tool_incoming:
                        if streamer and streamer.ans_started:
                            streamer.stop()
                            streamer = None
                        if spinner and not spinner.active:
                            spinner.start("Drafting tool action...")

                    chunk_to_stream, is_thinking, in_think_block = _process_stream_chunk(content, reasoning, in_think_block)

                    if chunk_to_stream:
                        if first_chunk:
                            first_chunk = False
                            streamer = RichStreamer(prefix="Agent:" if is_agent else "AI:", spinner=spinner)
                            streamer.start()
                            if speed_test and show_stats:
                                speed_test.start()

                        if streamer:
                            streamer.update(chunk_to_stream)
                        acc_content.append(chunk_to_stream)
                        if speed_test and show_stats:
                            speed_test.count_token(chunk_to_stream, is_thinking=is_thinking)
                    elif "<tool_call" in content or "<function=" in content:
                        acc_content.append(content)
                        if spinner and not spinner.active:
                            spinner.start("Drafting tool action...")

                    for tc in delta.get("tool_calls", []):
                        idx = tc.get("index", 0)
                        tc_entry = tool_calls_map.setdefault(idx, {"id": tc.get("id", ""), "type": "function", "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}})
                        if tc.get("function", {}).get("name"):
                            tc_entry["function"]["name"] = tc["function"]["name"]
                        arg_chunk = tc.get("function", {}).get("arguments", "")
                        if arg_chunk:
                            tc_entry["function"]["arguments"] += arg_chunk
                            if speed_test and show_stats:
                                speed_test.count_token(arg_chunk, is_thinking=False)
                            if spinner and not spinner.active:
                                spinner.start("Drafting tool action...")

                    if finish_reason in ("stop", "length") and not tool_calls_map:
                        break
                except Exception:
                    pass

            if streamer:
                streamer.stop()
            elif not first_chunk:
                print()

            ans_text = "".join(acc_content)
            in_tok, out_tok = _calc_turn_tokens(ans_text, messages, captured_usage, is_local)

            if speed_test and show_stats and not first_chunk:
                speed_test.end(actual_out_tokens=out_tok, is_local=is_local, resolved_model=resolved_model, active_model=body.get("model"))

            calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None

            # Sub-27B Fallback Extraction via Modular Adapters
            if not calls and ans_text and is_agent:
                calls = adapters.extract_fallback_tool_calls(ans_text) or None

            has_web_call = use_gnd and any(c.get("function", {}).get("name") == "web_search" for c in (calls or []))

            if not calls or (not is_agent and not has_web_call):
                tool_toks = sum(get_accurate_token_count(m.get("content") or "") for m in messages if m.get("role") in ("assistant", "tool"))
                final_out = max(out_tok, tool_toks)
                if spinner:
                    spinner.stop()
                user_msg = next((m.get("content", "") or "" for m in reversed(messages) if m.get("role") == "user"), "")
                _log_turn_usage(resolved_model or body.get("model") or "local-model", in_tok, final_out, 0.0, show_stats, in_tok + final_out, user_msg=user_msg, assistant_msg=ans_text)
                return ans_text if ans_text else "(No response generated)"

            # Re-serialize healed tool arguments
            healed_calls = []
            for tc in calls:
                fname = tc.get("function", {}).get("name", "")
                raw_args = tc.get("function", {}).get("arguments") or ""
                healed_dict = adapters.heal_json_args(raw_args)
                healed_calls.append({
                    "id": tc.get("id") or f"call_{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": fname,
                        "arguments": json.dumps(healed_dict)
                    }
                })

            # 1. Strip reasoning from turn history so older turns don't pollute subsequent context
            clean_ans_text = re.sub(r"<think>[\s\S]*?</think>", "", ans_text).strip()
            messages.append({"role": "assistant", "content": clean_ans_text or "", "tool_calls": healed_calls})

            for tc in healed_calls:
                if spinner:
                    spinner.stop()
                fname = tc.get("function", {}).get("name", "")
                args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                brief = str(args.get("code") or args.get("symbol") or args.get("path") or args.get("command") or args.get("pattern") or args.get("goal") or "")[:100].replace("\n", " ")
                verb = TOOL_VERBS.get(fname, "working")

                _console_err.print(f"[dim]∗ {verb} • [cyan]{fname}[/cyan] [italic]{brief}[/italic][/dim]")
                if spinner and fname != "delegate_task":
                    spinner.start(f"{verb.capitalize()}...")

                try:
                    result = _run_edit_tool(fname, args, workspace, spinner)
                except Exception as e:
                    result = f"[tool error] {e}"
                finally:
                    if spinner:
                        spinner.stop()

                # 2. Large Tool Result Scratchpad Offload (TrueForge-inspired)
                if len(result) > 1500:
                    scratch_dir = os.path.join(workspace, ".agent", "scratchpad")
                    os.makedirs(scratch_dir, exist_ok=True)
                    scratch_file = os.path.join(scratch_dir, f"{fname}_{int(time.time())}.txt")
                    try:
                        with open(scratch_file, "w", encoding="utf-8") as sf:
                            sf.write(result)
                        rel_scratch = os.path.relpath(scratch_file, workspace)
                        pruned_result = (
                            result[:1200]
                            + f"\n... [Output truncated: Full {len(result):,} chars saved to '{rel_scratch}'. "
                            + f"Use read_file('{rel_scratch}', line_start, line_end) to inspect specific blocks.]"
                        )
                    except OSError:
                        pruned_result = result[:1200] + "\n... [snipped]"
                else:
                    pruned_result = result

                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned_result})

                if "[denied]" in result:
                    messages.append({"role": "system", "content": "Action was explicitly declined by the user. Do not retry or attempt alternative workarounds for this resource."})
                    return "[denied] Action cancelled by user."

                if result.startswith("[error") or result.startswith("[tool error"):
                    consecutive_tool_failures += 1
                else:
                    consecutive_tool_failures = 0

        except KeyboardInterrupt:
            if streamer:
                try:
                    streamer.stop(interrupted=True)
                except Exception:
                    pass
            if spinner:
                try:
                    spinner.stop()
                except Exception:
                    pass
            raise
        except Exception as e:
            sys.stderr.write(f"\033[90m[sys] API response error: {e}\033[0m\r\n")
            return None
        finally:
            if res is not None:
                try:
                    res.close()
                except Exception:
                    pass
            if spinner:
                spinner.stop()
    return None


def stream_response(messages: list[dict[str, Any]], prefix: str = "AI: ", cfg_dir: str = "", show_stats: bool = False, thinking_budget: int = 0, is_agent: bool = False) -> str | None:
    is_sub = int(os.environ.get("AI_SUBAGENT_DEPTH", "0")) >= 1
    spinner = None if is_sub else ui.InlineSpinner()
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

        ans = agentic_turn(messages, url, headers, body, timeout, spinner, show_stats, is_agent=is_agent)
        if spinner:
            spinner.stop()
        return ans
    except KeyboardInterrupt:
        if spinner:
            try:
                spinner.stop()
            except Exception:
                pass
        sys.stderr.write("\r\x1b[2K\033[90m[sys] Interrupted.\033[0m\033[0m\r\n")
        return None


def get_accurate_token_count(text: Any, server_url: str = "http://localhost:8080") -> int:
    return max(1, (len(text if isinstance(text, str) else str(text)) * 10) // 36) if text else 0


def show_memory_status(messages: list[dict[str, Any]], max_context: int = 8192, server_url: str = "http://localhost:8080") -> None:
    total_toks = sum(get_accurate_token_count(m.get("content") or "", server_url) for m in messages)
    pct = (total_toks / max_context) * 100
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    color = "green" if pct < 70 else "yellow" if pct < 90 else "red"

    _console.print(Panel(
        Group(
            Text.assemble(("Context Window: ", "dim"), (f"{total_toks}", f"bold {color}"), (f"/{max_context} tokens ", "dim"), (f"({pct:.1f}%)", f"bold {color}")),
            Text(f"[{bar}]", style=color)
        ),
        title="Memory & Context Status", title_align="left", border_style="bright_black", box=ROUNDED, expand=False
    ))


def prune_history(history: list[dict[str, Any]], max_tokens: int | None = None) -> list[dict[str, Any]]:
    """3-Zone Context Compactor with SmolCoder Active Session Working Anchor"""
    if len(history) <= 4:
        return history

    limit = max_tokens or int(os.environ.get("AI_MAX_TOKENS", 8192))
    sys_msg = history[0]

    recent_tail = history[-4:]
    middle_msgs = history[1:-4]

    completed_actions = []
    compacted_middle = []

    for msg in middle_msgs:
        role = msg.get("role")
        content = str(msg.get("content") or "")

        if role == "tool":
            fname = msg.get("name", "tool")
            line_count = len(content.splitlines())

            if "Successfully edited" in content:
                if m := re.search(r"Successfully edited\s+(\S+)", content):
                    completed_actions.append(f"Edited {m.group(1)}")
                summary = f"[{fname}: applied targeted edit]"
            elif "wrote" in content and "chars to" in content:
                if m := re.search(r"wrote \d+ chars to\s+(\S+)", content):
                    completed_actions.append(f"Created {m.group(1)}")
                summary = f"[{fname}: created file]"
            elif "(exit 0" in content:
                completed_actions.append("Passed shell verification")
                summary = f"[{fname}: command passed (exit 0)]"
            elif "### File:" in content or line_count > 10:
                summary = f"[{fname}: {line_count} lines processed successfully]"
            elif "(exit" in content:
                first_err = content.splitlines()[0] if content else "error"
                summary = f"[{fname}: {first_err[:120]}]"
            else:
                summary = content if len(content) <= 150 else content[:120] + "... [snipped]"

            compacted_middle.append({"role": "assistant", "content": summary})
        elif role == "assistant":
            clean_msg = {k: v for k, v in msg.items() if k != "tool_calls"}
            clean_c = re.sub(r"<think>[\s\S]*?</think>", "", str(clean_msg.get("content") or "")).strip()
            if clean_c:
                compacted_middle.append({**clean_msg, "content": clean_c})
        else:
            compacted_middle.append(msg)

    anchors = []
    if mod_files := tools.get_modified_files():
        anchors.append(f"[Active Session Modified Files: {', '.join(mod_files)}]")
    if completed_actions:
        deduped = list(dict.fromkeys(completed_actions))[-6:]
        anchors.append("[Completed Milestones]:\n" + "\n".join(f"✓ {act}" for act in deduped))

    anchor_msg = {"role": "system", "content": "\n\n".join(anchors)} if anchors else None

    assembled = [sys_msg] + ([anchor_msg] if anchor_msg else [])
    curr_tokens = sum(get_accurate_token_count(m.get("content", "")) for m in assembled)
    tail_tokens = sum(get_accurate_token_count(m.get("content") or "") for m in recent_tail)

    budget_for_middle = max(500, limit - tail_tokens - curr_tokens)
    selected_middle = []

    for m in reversed(compacted_middle):
        toks = get_accurate_token_count(m.get("content") or "")
        if curr_tokens + toks > budget_for_middle and selected_middle:
            break
        selected_middle.append(m)
        curr_tokens += toks

    return assembled + list(reversed(selected_middle)) + recent_tail
