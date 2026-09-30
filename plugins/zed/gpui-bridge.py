#!/usr/bin/env python3
"""Dedicated Zed / GPUI ACP (Agent Client Protocol) Bridge for Py-Agent [testing]"""

import json
import os
import re
import sys
import threading
import time
import uuid
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")

if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)
if CFG_DIR not in sys.path:
    sys.path.insert(0, CFG_DIR)

try:
    import agent_adapters as adapters
    import agent_cloud as cloud
    import agent_core as core
    import agent_memories as memories
    import agent_security as security
    import agent_skills as skills
    import agent_tools as tools
    import requests
except ImportError as e:
    sys.stderr.write(f"[zed-bridge error] Failed to load py-agent modules: {e}\n")
    sys.exit(1)

_sessions: dict[str, dict[str, Any]] = {}
_stdout_lock = threading.Lock()


def log_debug(msg: str) -> None:
    sys.stderr.write(f"[zed-bridge] {msg}\n")
    sys.stderr.flush()


def send_response(req_id: Any, result: Any = None, error: Any = None) -> None:
    payload = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result if result is not None else {}

    wire = json.dumps(payload)
    with _stdout_lock:
        sys.stdout.write(wire + "\n")
        sys.stdout.flush()


def send_notification(method: str, params: dict[str, Any]) -> None:
    payload = {"jsonrpc": "2.0", "method": method, "params": params}
    wire = json.dumps(payload)
    with _stdout_lock:
        sys.stdout.write(wire + "\n")
        sys.stdout.flush()


def send_session_update(session_id: str, update: dict[str, Any]) -> None:
    send_notification("session/update", {
        "sessionId": session_id,
        "update": update
    })


def emit_thought_chunk(session_id: str, text: str) -> None:
    clean = text.replace("<think>", "").replace("</think>", "")
    if clean:
        send_session_update(session_id, {
            "sessionUpdate": "agent_thought_chunk",
            "content": {"type": "text", "text": clean}
        })


def emit_message_chunk(session_id: str, text: str) -> None:
    clean = text.replace("<think>", "").replace("</think>", "")
    if clean:
        send_session_update(session_id, {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": clean}
        })


def emit_tool_call(session_id: str, call_id: str, title: str, status: str = "in_progress") -> None:
    send_session_update(session_id, {
        "sessionUpdate": "tool_call",
        "toolCallId": call_id,
        "title": title,
        "status": status
    })


def _build_session_context(workspace: str) -> tuple[str, str, bool, int]:
    cfg_file = os.path.join(workspace, ".agent", "config.json")
    profile_name = "lingtiny"
    adapters_on = True
    reasoning_budget = 500

    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as cf:
                cfg_data = json.load(cf)
                profile_name = cfg_data.get("profile", profile_name)
                adapters_on = bool(cfg_data.get("adapters", cfg_data.get("adp", adapters_on)))
                reasoning_budget = int(cfg_data.get("reasoning_budget", reasoning_budget))
        except (OSError, json.JSONDecodeError):
            pass

    skills_dir = os.path.join(CFG_DIR, "skills")
    profile_raw = skills.load_skill_content(profile_name, skills_dir, CFG_DIR) or "You are an expert autonomous software engineer."

    inst_p = os.path.join(skills_dir, "system_instructions.md")
    rules_text = ""
    if os.path.isfile(inst_p) and os.path.getsize(inst_p) > 0:
        try:
            with open(inst_p, "r", encoding="utf-8") as f:
                rules = [l for l in f if l.strip() and not l.strip().startswith("#")]
                rules_text = "".join(rules).strip()
        except OSError:
            pass

    chat_boundary = (
        "\n\n### CHAT VS TOOL EXECUTION DIRECTIVE:\n"
        "If the user asks for an explanation, a greeting, or code snippets in conversation, "
        "output the answer directly in chat using markdown. "
        "Do NOT call write_file unless the user explicitly requests to save or create a file on disk."
    )

    full_system_prompt = f"{profile_raw}\n\n{rules_text}{chat_boundary}".strip()
    return full_system_prompt, profile_name, adapters_on, reasoning_budget


# ── ACP Protocol Handlers ───────────────────────────────────────────────────

def handle_initialize(req_id: Any, params: dict[str, Any]) -> None:
    proto_version = params.get("protocolVersion", 1)
    send_response(req_id, {
        "protocolVersion": proto_version,
        "agentCapabilities": {
            "loadSession": True
        },
        "agentInfo": {
            "name": "py-agent",
            "version": "0.9.9.44"
        }
    })


def handle_session_new(req_id: Any, params: dict[str, Any]) -> None:
    session_id = f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    cwd = params.get("cwd") or os.environ.get("AI_WORKSPACE_PATH") or os.getcwd()
    workspace = os.path.realpath(os.path.expanduser(cwd))

    prompt, profile_name, adapters_on, budget = _build_session_context(workspace)

    _sessions[session_id] = {
        "workspace": workspace,
        "history": [{"role": "system", "content": prompt}],
        "cancelled": False,
        "profile_name": profile_name,
        "adapters_on": adapters_on,
        "reasoning_budget": budget
    }

    log_debug(f"Created session '{session_id}' | Workspace: {workspace} | Profile: {profile_name}")
    send_response(req_id, {"sessionId": session_id})


def handle_session_load(req_id: Any, params: dict[str, Any]) -> None:
    session_id = params.get("sessionId") or f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    cwd = params.get("cwd") or os.environ.get("AI_WORKSPACE_PATH") or os.getcwd()
    workspace = os.path.realpath(os.path.expanduser(cwd))

    prompt, profile_name, adapters_on, budget = _build_session_context(workspace)

    _sessions[session_id] = {
        "workspace": workspace,
        "history": [{"role": "system", "content": prompt}],
        "cancelled": False,
        "profile_name": profile_name,
        "adapters_on": adapters_on,
        "reasoning_budget": budget
    }

    log_debug(f"Resumed/Loaded session '{session_id}' | Workspace: {workspace}")
    send_response(req_id, {"sessionId": session_id})


def handle_session_cancel(params: dict[str, Any]) -> None:
    session_id = params.get("sessionId")
    if session_id in _sessions:
        _sessions[session_id]["cancelled"] = True
        log_debug(f"Cancelled turn in session '{session_id}'")


def handle_session_prompt(req_id: Any, params: dict[str, Any]) -> None:
    session_id = params.get("sessionId")
    if session_id not in _sessions:
        send_response(req_id, error={"code": -32602, "message": f"Session '{session_id}' not found"})
        return

    session = _sessions[session_id]
    session["cancelled"] = False
    workspace = session["workspace"]

    prompt_blocks = params.get("prompt") or params.get("content") or []
    user_text = ""
    if isinstance(prompt_blocks, list):
        for block in prompt_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                user_text += block.get("text", "")
    elif isinstance(prompt_blocks, str):
        user_text = prompt_blocks

    q_strip = user_text.strip()
    if not q_strip:
        send_response(req_id, {"stopReason": "end_turn"})
        return

    # Slash command interception
    if q_strip.startswith("/"):
        cmd = q_strip.split()[0].lower()
        if cmd == "/clear":
            session["history"] = [session["history"][0]]
            emit_message_chunk(session_id, "[chat: cleared]")
            send_response(req_id, {"stopReason": "end_turn"})
            return
        elif cmd in ("/adp", "/adapter"):
            session["adapters_on"] = not session.get("adapters_on", True)
            emit_message_chunk(session_id, f"[adp: {'on' if session['adapters_on'] else 'off'}]")
            send_response(req_id, {"stopReason": "end_turn"})
            return
        elif cmd == "/stats":
            emit_message_chunk(session_id, "[stats: disabled in editor surface]")
            send_response(req_id, {"stopReason": "end_turn"})
            return

    mem_ctx = memories.get_memory_context(workspace)
    if mem_ctx:
        full_query = f"<context>\n{mem_ctx}\n</context>\n\nUser Question: {q_strip}"
    else:
        full_query = q_strip

    session["history"].append({"role": "user", "content": full_query})

    def _worker():
        try:
            _execute_acp_turn(session_id, req_id)
        except Exception as e:
            log_debug(f"Turn execution error: {e}")
            send_response(req_id, error={"code": -32000, "message": str(e)})

    threading.Thread(target=_worker, daemon=True).start()


def _execute_acp_turn(session_id: str, req_id: Any) -> None:
    session = _sessions[session_id]
    workspace = session["workspace"]
    messages = session["history"]
    adapters_on = session.get("adapters_on", True)
    reasoning_budget = session.get("reasoning_budget", 500)

    configs = cloud.get_active_configs(messages)
    if not configs:
        configs = [("http://localhost:8080/v1/chat/completions", {}, {"messages": messages, "stream": True}, 180)]

    url, headers, body, timeout = configs[0]
    http_session = requests.Session()

    for _round in range(10):
        if session["cancelled"]:
            send_response(req_id, {"stopReason": "cancelled"})
            return

        body_tools = {
            **body,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "tools": tools.SMOL_TOOLS,
            "thinking_budget_tokens": reasoning_budget,
            "reasoning_budget": reasoning_budget,
            "chat_template_kwargs": {"enable_thinking": True}
        }

        try:
            res = http_session.post(
                url,
                json=body_tools,
                headers={"Content-Type": "application/json", "User-Agent": "py-agent-zed", **headers},
                timeout=timeout,
                stream=True
            )
        except Exception as e:
            emit_message_chunk(session_id, f"\n[Connection error: {e}]\n")
            send_response(req_id, {"stopReason": "error"})
            return

        acc_content = []
        tool_calls_map = {}
        in_think_block = False

        for line in res.iter_lines():
            if session["cancelled"]:
                res.close()
                send_response(req_id, {"stopReason": "cancelled"})
                return

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

            choices = data.get("choices", [{}])
            if not choices:
                continue
            delta = choices[0].get("delta", {})

            content = delta.get("content", "") or ""
            reasoning = delta.get("reasoning_content", "") or delta.get("thinking", "") or delta.get("reasoning", "") or ""

            chunk_to_stream, is_thinking, in_think_block = core._process_stream_chunk(content, reasoning, in_think_block)
            if chunk_to_stream:
                acc_content.append(chunk_to_stream)

                if "</think>" in chunk_to_stream:
                    parts = chunk_to_stream.split("</think>", 1)
                    if parts[0]:
                        emit_thought_chunk(session_id, parts[0])
                    if len(parts) > 1 and parts[1]:
                        emit_message_chunk(session_id, parts[1])
                elif "<think>" in chunk_to_stream:
                    parts = chunk_to_stream.split("<think>", 1)
                    if parts[0]:
                        emit_message_chunk(session_id, parts[0])
                    if len(parts) > 1 and parts[1]:
                        emit_thought_chunk(session_id, parts[1])
                elif is_thinking:
                    emit_thought_chunk(session_id, chunk_to_stream)
                else:
                    emit_message_chunk(session_id, chunk_to_stream)

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
                if tc.get("function", {}).get("arguments"):
                    tc_entry["function"]["arguments"] += tc["function"]["arguments"]

        res.close()
        ans_text = "".join(acc_content)
        calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None

        if not calls and ans_text and adapters_on:
            calls = adapters.extract_fallback_tool_calls(ans_text) or None

        if not calls:
            clean_reply = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", ans_text).strip()
            messages.append({"role": "assistant", "content": clean_reply or ans_text})
            send_response(req_id, {"stopReason": "end_turn"})
            return

        healed_calls = []
        for call_idx, tc in enumerate(calls):
            raw_fname = tc.get("function", {}).get("name", "")
            raw_args = tc.get("function", {}).get("arguments") or ""
            if adapters_on:
                fname, healed_dict = adapters.heal_tool_call(raw_fname, raw_args)
            else:
                fname = raw_fname
                healed_dict = core._heal_tool_args(raw_args)

            if isinstance(healed_dict, dict) and "path" in healed_dict and isinstance(healed_dict["path"], str):
                p_val = healed_dict["path"].strip()
                if p_val.startswith("/"):
                    p_parts = p_val.strip("/").split("/")
                    _sys_roots = {"etc", "usr", "root", "tmp", "var", "bin", "sbin", "boot", "dev", "proc", "sys", "home", "opt", "srv"}
                    if len(p_parts) == 1 and p_parts[0] not in _sys_roots:
                        healed_dict["path"] = p_parts[0]

            cid = tc.get("id") or f"call_{int(time.time())}_{call_idx}"
            healed_calls.append({"id": cid, "type": "function", "function": {"name": fname, "arguments": json.dumps(healed_dict)}})

        clean_ans_text = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", ans_text).strip()
        messages.append({"role": "assistant", "content": clean_ans_text or "", "tool_calls": healed_calls})

        for tc in healed_calls:
            fname = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            brief = str(args.get("path") or args.get("command") or "")[:80]
            emit_tool_call(session_id, tc["id"], f"{fname} {brief}", "in_progress")

            try:
                result = tools.run_tool(
                    fname,
                    args,
                    workspace,
                    confirm_gate_fn=lambda r: True
                )
            except Exception as e:
                result = f"[tool error] {e}"

            emit_tool_call(session_id, tc["id"], f"{fname} {brief}", "completed")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": fname, "content": result})

    send_response(req_id, {"stopReason": "end_turn"})


# ── Main JSON-RPC Stdio Loop ────────────────────────────────────────────────

def main():
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    log_debug("Bridge process started, awaiting ACP JSON-RPC on stdin...")

    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue

        try:
            msg = json.loads(line_clean)
        except json.JSONDecodeError as e:
            log_debug(f"JSON decode error: {e} (raw={line_clean!r})")
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            handle_initialize(req_id, params)
        elif method == "session/new":
            handle_session_new(req_id, params)
        elif method == "session/load":
            handle_session_load(req_id, params)
        elif method == "session/prompt":
            handle_session_prompt(req_id, params)
        elif method == "session/cancel":
            handle_session_cancel(params)
        elif req_id is not None:
            send_response(req_id, error={"code": -32601, "message": f"Method '{method}' not implemented"})


if __name__ == "__main__":
    main()
