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
    get_accurate_token_count,
)
import agent_security as security
from agent_state import (
    CFG_DIR,
    _get_int_env,
    get_state,
    is_calm_cli,
    save_state as save_state,
    workspace_safe_name as workspace_safe_name,
)
from agent_stream import (
    Markdown,
    RichStreamer,
    _console,
    _console_err,
    _escape_markup,
    _process_stream_chunk,
    get_cursor_up_count,
    prepare_markdown,
)
import agent_tools as tools

ALLOWED_MODULES: frozenset[str] = frozenset({
    "agent_chat.py",
    "agent_cloud.py",
    "agent_context.py",
    "agent_core.py",
    "agent_ipython.py",
    "agent_memories.py",
    "agent_security.py",
    "agent_sessions.py",
    "agent_skills.py",
    "agent_state.py",
    "agent_stream.py",
    "agent_tools.py",
    "agent_tts.py",
    "agent_tui.py",
    "agent_tui_async.py",
    "agent_ui.py",
    "agent_vision.py",
    "agent_voice.py",
    "model-select.py",
    "chat",
    "cheatsheet",
    "new-project",
    "omarchy",
    "system-stack",
    "test-agent",
    "eval-stack",
})


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


_local_session = threading.local()


def _get_session() -> Any:
    if not hasattr(_local_session, "session"):
        import requests
        import requests.adapters
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

RE_FINAL_ANSWER_SENTINEL = re.compile(r"^\s*#{0,3}\s*Final Answer\b", re.IGNORECASE | re.MULTILINE)
TOOL_VERBS: dict[str, str] = getattr(tools, "TOOL_VERBS", {})


def _heal_tool_args(raw: Any) -> dict[str, Any]:
    """Heals malformed JSON tool arguments via modular adapter or safe decode."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s == "{}":
            return {}
    elif not raw:
        return {}

    if get_state("adapters_active", False):
        return adapters.heal_json_args(raw) if isinstance(raw, str) else (raw or {})

    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, dict):
            if len(parsed) == 1:
                sole_key, sole_val = next(iter(parsed.items()))
                if isinstance(sole_val, dict) and sole_key.lower() in ("arguments", "args", "input", "params", "parameters"):
                    return sole_val
            return parsed

        if isinstance(parsed, str) and parsed.strip().startswith("{"):
            try:
                inner = json.loads(parsed)
                if isinstance(inner, dict):
                    return inner
            except Exception:
                pass

        return {"_parse_error": f"Expected mapping for tool arguments, got {type(parsed).__name__}", "_raw_args": str(raw)}
    except Exception as e:
        if os.environ.get("AI_DEBUG") == "1":
            sys.stderr.write(f"[debug] Failed to parse tool arguments: {e} (raw={raw!r})\n")
        return {"_parse_error": str(e), "_raw_args": str(raw)}


def run_mod(module_name: str, *args: str) -> str:
    clean_name = os.path.basename(module_name)
    if clean_name not in ALLOWED_MODULES:
        return f"[error: execution of '{clean_name}' is not permitted by module allowlist]"

    for base in (os.path.join(CFG_DIR, "modules"), os.path.join(CFG_DIR, "tools"), CFG_DIR):
        base_real = os.path.realpath(base)
        target = os.path.realpath(os.path.join(base, clean_name))
        if os.path.isfile(target) and os.path.commonpath([base_real, target]) == base_real:
            try:
                cmd = [sys.executable, target] + list(args) if target.endswith(".py") else [target] + list(args)
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
                if res.returncode != 0:
                    err_out = (res.stderr or res.stdout or "").strip()
                    return f"[error: exit {res.returncode}] {err_out}"
                return (res.stdout or res.stderr or "").strip()
            except Exception as e:
                return f"[error: {e}]"
    return f"[error: module '{clean_name}' not found]"


def _log_turn_usage(
    in_tok: int,
    out_tok: int,
    show_stats: bool,
    ctx_max: int,
    cached_tok: int = 0,
    r_tok: int = 0,
    elapsed: float = 0.0,
) -> None:
    """Renders unified compact turn metrics in exact muted gray (\\033[90m) with dialed-in spacing."""
    if not (show_stats and sys.stdout.isatty()):
        return
    try:
        parts = []

        in_s = f"↑{in_tok / 1000:.1f}k" if in_tok >= 1000 else f"↑{in_tok}"
        out_s = f"↓{out_tok / 1000:.1f}k" if out_tok >= 1000 else f"↓{out_tok}"
        tok_s = f"{in_s} {out_s}"
        if r_tok > 0:
            r_s = f"R{r_tok / 1000:.1f}k" if r_tok >= 1000 else f"R{r_tok}"
            tok_s += f" {r_s}"
        parts.append(tok_s)

        if cached_tok > 0 and in_tok > 0:
            cch = int(round((cached_tok / in_tok) * 100))
            parts.append(f"CH{cch}%")

        ctx_used = in_tok + out_tok
        ctx_pct = (ctx_used / max(1, ctx_max)) * 100
        max_k = "8.2k" if ctx_max == 8192 else (f"{ctx_max / 1000:.1f}k" if ctx_max % 1000 != 0 else f"{ctx_max // 1000}k")
        parts.append(f"{ctx_pct:.1f}%/{max_k}")

        if elapsed > 0:
            speed = out_tok / max(0.01, elapsed)
            parts.append(f"{elapsed:.1f}s @ {speed:.1f} t/s")

        sys.stdout.write(f"\n\033[90m [ {' · '.join(parts)} ]\033[0m\n\n")
        sys.stdout.flush()
    except Exception:
        pass


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
    has_assistant_call = any(m.get("role") == "assistant" and m.get("tool_calls") for m in msg_list)
    if not has_assistant_call or not expected_calls:
        return
    existing_ids = {m.get("tool_call_id") for m in msg_list if m.get("role") == "tool"}
    for tc in expected_calls:
        cid = tc.get("id")
        if cid and cid not in existing_ids:
            fn_name = tc.get("function", {}).get("name", "tool")
            msg_list.append({"role": "tool", "tool_call_id": cid, "name": fn_name, "content": fallback_content})
            existing_ids.add(cid)


# ── Autonomous Agentic Turn Engine ───────────────────────────────────────────

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
    resolved_model, streamer = None, None
    max_ctx = _get_int_env("AI_MAX_TOKENS", 8192)
    is_calm = is_calm_cli()
    is_sub = _get_int_env("AI_SUBAGENT_DEPTH", 0) >= 1

    consecutive_tool_failures = 0
    consecutive_context_overflows = 0
    tools_disabled = False
    ans_text = ""

    ephemeral_directives: list[dict[str, str]] = []
    last_prompt_tokens = 0
    last_msg_count = 0

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
    max_rounds = _get_int_env("AI_MAX_AGENT_ROUNDS", 10)

    for _round in range(max_rounds):
        healed_calls: list[dict[str, Any]] = []

        if last_prompt_tokens > 0 and len(messages) >= last_msg_count:
            delta_tokens = _calc_msg_tokens(messages[last_msg_count:]) + _calc_msg_tokens(ephemeral_directives)
            curr_tok = last_prompt_tokens + delta_tokens
        else:
            curr_tok = _calc_msg_tokens(messages) + _calc_msg_tokens(ephemeral_directives)

        if spinner and hasattr(spinner, "update_context"):
            spinner.update_context(curr_tok, max_ctx)

        if curr_tok > int(max_ctx * 0.75):
            messages[:] = prune_history(messages, max_tokens=int(max_ctx * 0.55))
            last_prompt_tokens = 0

        if consecutive_tool_failures >= 2:
            decomp_steer = (
                "[System Directive - Task Decomposition]: Your previous action failed repeatedly. "
                "Stop retrying the whole file. Decompose your immediate next step: "
                "1) Read the exact 15-20 lines using read_file(path, line_start, line_end) or search_code(pattern). "
                "2) Apply a targeted edit_file to only that section with unique context lines."
            )
            ephemeral_directives = [{"role": "user", "content": decomp_steer}]
            consecutive_tool_failures = 0

        body_messages = list(messages) + ephemeral_directives
        body_tools = {**body, "messages": body_messages, "stream": True, "stream_options": {"include_usage": True}}
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

        captured_usage, captured_timings = None, None
        first_chunk = True
        acc_content: list[str] = []
        tool_calls_map: dict[int, dict[str, Any]] = {}
        in_think_block = False

        res = None
        turn_start_time = time.monotonic()
        max_turn_wall_clock = float(timeout * 2 if timeout > 0 else 600.0)
        timeout_tuple = (15, max(timeout, 120))
        saw_done = False

        try:
            res = session.post(
                url,
                json=body_tools,
                headers={"Content-Type": "application/json", "User-Agent": "py-agent", **headers},
                timeout=timeout_tuple,
                stream=True,
            )
            with res:
                if res.status_code != 200:
                    try:
                        err_raw = res.raw.read(2048) if hasattr(res, "raw") else b""
                        err_text = err_raw.decode("utf-8", errors="replace")[:200] if isinstance(err_raw, bytes) else str(err_raw)[:200]
                    except Exception:
                        err_text = res.text[:200] if hasattr(res, "text") else ""
                    err_text = err_text.replace("\n", " ").strip()

                    if res.status_code == 400 and ("exceed" in err_text.lower() or "context" in err_text.lower()):
                        consecutive_context_overflows += 1
                        if consecutive_context_overflows >= 2:
                            if spinner:
                                spinner.stop(leave_on_screen=False)
                            sys.stderr.write("\r\033[1;31m[error] Context window overflow: message payload cannot be pruned further.\033[0m\r\n")
                            return "[error] Context window exceeded."

                        if spinner:
                            spinner.stop(leave_on_screen=False)
                        sys.stderr.write("\r\033[1;33m[sys] Context window full. Auto-compacting conversation history...\033[0m\r\n")
                        messages[:] = prune_history(messages, max_tokens=int(max_ctx * 0.5))
                        last_prompt_tokens = 0
                        continue

                    if spinner:
                        spinner.stop(leave_on_screen=False)
                    sys.stderr.write(f"\r\033[1;31m[error] Server HTTP {res.status_code}: {err_text}\033[0m\r\n")
                    return None

                consecutive_context_overflows = 0
                event_data_lines: list[str] = []

                def _flush_sse_event() -> str | None:
                    nonlocal event_data_lines
                    if not event_data_lines:
                        return None
                    combined = "\n".join(event_data_lines)
                    event_data_lines = []
                    return combined

                for line in res.iter_lines(chunk_size=512):
                    if time.monotonic() - turn_start_time > max_turn_wall_clock:
                        raise TimeoutError(f"Turn stream exceeded wall-clock limit of {int(max_turn_wall_clock)}s")

                    line_str = line.decode("utf-8", errors="replace").rstrip("\r\n") if line else ""
                    if not line_str:
                        data_str = _flush_sse_event()
                        if not data_str:
                            continue
                    elif line_str.startswith("data:"):
                        payload = line_str[5:]
                        if payload.startswith(" "):
                            payload = payload[1:]
                        event_data_lines.append(payload)
                        continue
                    else:
                        continue

                    if data_str == "[DONE]":
                        saw_done = True
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

                        has_tool_deltas = bool(delta.get("tool_calls"))
                        has_xml_tool_tag = False
                        if not has_tool_deltas and content:
                            stripped_c = content.lstrip()
                            has_xml_tool_tag = any(
                                stripped_c.startswith(tag)
                                for tag in ("<tool_call>", "<tool_call ", "<function=", "<｜DSML｜", "<|tool_call|>")
                            )

                        is_tool_incoming = has_tool_deltas or has_xml_tool_tag
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
                                if is_calm and spinner:
                                    spinner.stop(leave_on_screen=False)
                                elif not is_sub:
                                    stream_pfx = prefix or ("Agent:" if is_agent else "AI:")
                                    streamer = RichStreamer(prefix=stream_pfx, spinner=spinner, round_idx=_round)
                                    streamer.start()

                            if streamer and not is_calm and not is_sub:
                                streamer.update(chunk_to_stream)
                        elif has_xml_tool_tag:
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
                    except Exception as e:
                        if os.environ.get("AI_DEBUG") == "1":
                            _console_err.print(f"[dim][debug] Stream chunk error: {e}[/dim]")

                if remaining := _flush_sse_event():
                    if remaining == "[DONE]":
                        saw_done = True
                    else:
                        try:
                            rem_data = json.loads(remaining)
                            captured_usage = rem_data.get("usage") or captured_usage
                        except Exception:
                            pass

        except KeyboardInterrupt:
            if streamer:
                try:
                    streamer.stop(interrupted=True)
                except Exception:
                    pass
            raise
        except Exception as e:
            if spinner:
                try:
                    spinner.stop(leave_on_screen=False)
                except Exception:
                    pass
            sys.stderr.write(f"\r\033[90m[sys] Stream error: {e}\033[0m\r\n")
            return None

        if streamer:
            streamer.stop()

        ans_text = "".join(acc_content)
        in_tok, out_tok = _calc_turn_tokens(ans_text, body_messages, captured_usage, is_local)
        if captured_usage and "prompt_tokens" in captured_usage:
            last_prompt_tokens = captured_usage["prompt_tokens"]
        last_msg_count = len(messages)
        final_model = resolved_model or body.get("model") or "local-model"

        calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None
        adapters_on = get_state("adapters_active", False)

        if not calls and ans_text and is_agent and adapters_on:
            calls = adapters.extract_fallback_tool_calls(ans_text) or None

        has_web_call = use_gnd and any(c.get("function", {}).get("name") == "web_search" for c in (calls or []))

        # ── Turn Complete: Final Model Answer Presentation ──────────────────
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

            try:
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
                    tsize = shutil.get_terminal_size((80, 24))
                    cols, rows = tsize.columns, tsize.lines
                    raw_lines = get_cursor_up_count(streamer.acc_ans, cols)

                    if raw_lines < rows - 1:
                        try:
                            if raw_lines > 0:
                                sys.stdout.write(f"\033[{raw_lines}A\r\x1b[0J")
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
                elif clean_reply and not streamer and not is_sub:
                    clean_reply = prepare_markdown(clean_reply)
                    _console.print(f"[{p_style}]{p_prefix}[/{p_style}]", end=" ")
                    if render_md:
                        code_th = str(get_state("code_theme", "monokai"))
                        _console.print(Markdown(clean_reply, code_theme=code_th, justify="default"))
                    else:
                        _console.print(clean_reply, markup=False, highlight=False)
                        _console.print()
            except Exception as render_err:
                if os.environ.get("AI_DEBUG") == "1":
                    sys.stderr.write(f"\r\n[debug] Markdown render fallback: {render_err}\r\n")
                if clean_reply:
                    _console.print(clean_reply, markup=False, highlight=False)
                    _console.print()

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

            r_tok = 0
            if captured_usage and isinstance(captured_usage, dict):
                details = captured_usage.get("completion_tokens_details") or {}
                r_tok = details.get("reasoning_tokens") or 0
            if not r_tok and streamer and getattr(streamer, "acc_think", None):
                r_tok = get_accurate_token_count(streamer.acc_think)

            elapsed_turn = max(0.01, time.monotonic() - turn_start_time)
            _log_turn_usage(in_tok, final_out, show_stats, max_ctx, cached_tok=cached_tok, r_tok=r_tok, elapsed=elapsed_turn)
            return ans_text if ans_text else "(No response generated)"

        # ── Tool Execution Phase ─────────────────────────────────────────────
        healed_calls = []
        seen_cids: set[str] = set()

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

            base_cid = tc.get("id") or f"call_{int(time.time())}_{call_idx}_{uuid.uuid4().hex[:6]}"
            cid = base_cid
            if cid in seen_cids:
                cid = f"{base_cid}_{call_idx}_{uuid.uuid4().hex[:4]}"
            seen_cids.add(cid)

            healed_calls.append({
                "id": cid,
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
        ephemeral_directives = []

        try:
            for call_idx, tc in enumerate(healed_calls):
                fname = tc.get("function", {}).get("name", "")
                args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                brief = str(args.get("code") or args.get("symbol") or args.get("path") or args.get("command") or args.get("pattern") or args.get("goal") or "")[:100].replace("\n", " ")
                verb = TOOL_VERBS.get(fname, "working")

                if isinstance(args, dict) and "_parse_error" in args:
                    result = f"[tool error] Malformed tool arguments: {args.get('_parse_error')}"
                    res_str = result
                    is_denied = False
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

                    is_denied = False
                    if isinstance(result, (list, tuple)):
                        res_str = "\n".join(str(x) for x in result)
                        is_denied = any(isinstance(x, str) and x.strip().startswith("[denied]") for x in result)
                    elif isinstance(result, str):
                        res_str = result
                        is_denied = res_str.strip().startswith("[denied]") or "[denied]" in res_str[:60]
                    else:
                        res_str = str(result) if result is not None else ""
                        is_denied = "[denied]" in res_str[:60]

                    if not is_calm and not is_sub and spinner and getattr(spinner, "active", False):
                        spinner.stop()

                    if not is_calm:
                        elapsed = max(0.01, time.time() - t_start)
                        _console_err.print(f"  [green]✔[/green] [dim]Done ({elapsed:.1f}s)[/dim]\n")

                res_tok_est = get_accurate_token_count(res_str)
                max_tool_tokens = max(2000, int(max_ctx * 0.30))

                if res_tok_est > max_tool_tokens:
                    scratch_dir = os.path.join(workspace, ".agent", "scratchpad")
                    try:
                        os.makedirs(scratch_dir, exist_ok=True)
                        try:
                            existing_files = [os.path.join(scratch_dir, f) for f in os.listdir(scratch_dir) if f.endswith(".txt")]
                            if len(existing_files) > 30:
                                existing_files.sort(key=lambda p: os.path.getmtime(p))
                                for old_file in existing_files[:-25]:
                                    try:
                                        os.remove(old_file)
                                    except OSError:
                                        pass
                        except Exception:
                            pass

                        safe_fname = re.sub(r"[^A-Za-z0-9_.-]", "_", fname)[:30] or "tool"
                        unique_tag = f"{int(time.time())}_{call_idx}_{uuid.uuid4().hex[:6]}"
                        scratch_file = os.path.join(scratch_dir, f"{safe_fname}_{unique_tag}.txt")

                        with open(scratch_file, "w", encoding="utf-8") as sf:
                            sf.write(res_str)
                        rel_scratch = os.path.relpath(scratch_file, workspace)
                        preview_chars = int(max_tool_tokens * 3.5 * 0.75)
                        pruned_result = (
                            res_str[:preview_chars]
                            + f"\n... [Output truncated: Full {len(res_str):,} chars ({res_tok_est:,} tokens) saved to '{rel_scratch}'. "
                            + f"Use read_file('{rel_scratch}', line_start, line_end) to inspect specific blocks.]"
                        )
                    except OSError:
                        pruned_result = res_str[:6000] + "\n... [snipped]"
                else:
                    pruned_result = res_str

                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned_result})

                if is_denied:
                    messages.extend(
                        {
                            "role": "tool",
                            "tool_call_id": rem_tc.get("id", ""),
                            "name": rem_tc.get("function", {}).get("name", ""),
                            "content": "[cancelled: prior action declined by user]",
                        }
                        for rem_tc in healed_calls[call_idx + 1:]
                    )
                    ephemeral_directives = [{
                        "role": "user",
                        "content": "[System Directive]: Action was explicitly declined by the user. Do not retry or attempt alternative workarounds for this resource.",
                    }]
                    return "[denied] Action cancelled by user."

                if fname == "exec_python" and RE_FINAL_ANSWER_SENTINEL.search(res_str):
                    ephemeral_directives = [{
                        "role": "user",
                        "content": "[System Directive]: final_answer() was received. Output your concise summary to the user now. Do not call any further tools.",
                    }]
                    tools_disabled = True

                if res_str.startswith("[error") or res_str.startswith("[tool error"):
                    consecutive_tool_failures += 1
                else:
                    consecutive_tool_failures = 0

                if fname == "read_file" and len(messages) >= 4:
                    prev_tools = [m for m in messages[-4:] if m.get("role") == "tool" and m.get("name") == "read_file"]
                    if len(prev_tools) >= 2:
                        ephemeral_directives = [{"role": "user", "content": "[System Directive]: File already inspected. Do not read again. Proceed immediately to edit, test, or final answer."}]

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
    sys.stderr.write(f"\r\033[1;33m[sys] Agent loop limit reached ({max_rounds} rounds exhausted without final answer).\033[0m\r\n")
    return f"[notice: agent loop limit reached after {max_rounds} rounds.]"


# ── High-Level Stream Entrypoint ─────────────────────────────────────────────

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
            local_max = _get_int_env("AI_MAX_TOKENS", 8192)
            body = {**body, "max_tokens": local_max, **think_kwargs}

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
        return ans
    except KeyboardInterrupt:
        sys.stderr.write("\r\x1b[2K\033[90m[sys] Interrupted.\033[0m\r\n")
        return None
    finally:
        if spinner:
            try:
                spinner.stop(leave_on_screen=False)
            except Exception:
                pass
        try:
            sys.stderr.write("\033[?25h")
            sys.stderr.flush()
        except Exception:
            pass
