#!/usr/bin/env python3
"""Dedicated Zed / GPUI ACP (Agent Client Protocol) Bridge for Py-Agent [Production Ready]"""

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
_sessions_lock = threading.Lock()
_stdout_lock = threading.Lock()

# Pending ACP client requests (session/request_permission)
_pending_requests: dict[str, dict[str, Any]] = {}
_pending_lock = threading.Lock()

_http_session = requests.Session()
_http_adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=1)
_http_session.mount("http://", _http_adapter)
_http_session.mount("https://", _http_adapter)


def log_debug(msg: str) -> None:
    sys.stderr.write(f"[zed-bridge] {msg}\n")
    sys.stderr.flush()


def send_response(req_id: Any, result: Any = None, error: Any = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
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


def _request_client_permission(session_id: str, tool_call_id: str, title: str, timeout: float = 60.0) -> bool:
    """Dispatches a compliant session/request_permission RPC to Zed."""
    perm_id = f"perm_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    event = threading.Event()
    box = {"event": event, "approved": False}

    with _pending_lock:
        _pending_requests[perm_id] = box

    payload = {
        "jsonrpc": "2.0",
        "id": perm_id,
        "method": "session/request_permission",
        "params": {
            "sessionId": session_id,
            "toolCall": {
                "toolCallId": tool_call_id,
                "title": title
            },
            "options": [
                {"kind": "allow_once", "name": "Allow", "optionId": "allow"},
                {"kind": "allow_always", "name": "Always Allow", "optionId": "allow_always"},
                {"kind": "reject_once", "name": "Reject", "optionId": "reject"}
            ]
        }
    }

    with _stdout_lock:
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()

    if event.wait(timeout=timeout):
        return box["approved"]

    with _pending_lock:
        _pending_requests.pop(perm_id, None)
    log_debug(f"Permission timed out for: {title}")
    return False


def _build_session_context(workspace: str) -> tuple[str, str, bool, int, bool]:
    cfg_file = os.path.join(workspace, ".agent", "config.json")
    profile_name = "lingtiny"
    adapters_on = True
    reasoning_budget = 500
    is_yolo = False

    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as cf:
                cfg_data = json.load(cf)
                if isinstance(cfg_data, dict):
                    profile_name = str(cfg_data.get("profile", profile_name))
                    adapters_on = bool(cfg_data.get("adapters", cfg_data.get("adp", adapters_on)))
                    is_yolo = bool(cfg_data.get("yolo", False))
                    b_val = cfg_data.get("reasoning_budget")
                    if isinstance(b_val, (int, float, str)):
                        try:
                            reasoning_budget = min(max(0, int(b_val)), 32000)
                        except ValueError:
                            pass
        except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError):
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

    full_system_prompt = f"{profile_raw}\n\n{rules_text}".strip()
    return full_system_prompt, profile_name, adapters_on, reasoning_budget, is_yolo


# ── ACP Protocol Handlers ───────────────────────────────────────────────────

def handle_initialize(req_id: Any, params: dict[str, Any]) -> None:
    proto_version = params.get("protocolVersion", 1)
    send_response(req_id, {
        "protocolVersion": proto_version,
        "agentCapabilities": {
            "loadSession": False
        },
        "agentInfo": {
            "name": "py-agent",
            "version": "0.9.9.45"
        }
    })


def handle_session_new(req_id: Any, params: dict[str, Any]) -> None:
    session_id = f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    cwd = params.get("cwd") or os.environ.get("AI_WORKSPACE_PATH") or os.getcwd()
    workspace = os.path.realpath(os.path.expanduser(cwd))

    prompt, profile_name, adapters_on, budget, is_yolo = _build_session_context(workspace)

    session_record = {
        "workspace": workspace,
        "history": [{"role": "system", "content": prompt}],
        "cancelled": False,
        "busy": False,
        "lock": threading.Lock(),
        "profile_name": profile_name,
        "adapters_on": adapters_on,
        "reasoning_budget": budget,
        "is_yolo": is_yolo
    }

    with _sessions_lock:
        _sessions[session_id] = session_record

    log_debug(f"Created session '{session_id}' | Workspace: {workspace} | Profile: {profile_name} | YOLO: {is_yolo}")
    send_response(req_id, {"sessionId": session_id})


def handle_session_load(req_id: Any, params: dict[str, Any]) -> None:
    session_id = str(params.get("sessionId") or "")
    with _sessions_lock:
        if session_id in _sessions:
            send_response(req_id, {"sessionId": session_id})
            return

    send_response(req_id, error={"code": -32602, "message": f"Session '{session_id}' not found"})


def handle_session_cancel(params: dict[str, Any]) -> None:
    session_id = params.get("sessionId")
    with _sessions_lock:
        session = _sessions.get(session_id)
    if session:
        with session["lock"]:
            session["cancelled"] = True
        log_debug(f"Cancelled turn in session '{session_id}'")


def handle_session_prompt(req_id: Any, params: dict[str, Any]) -> None:
    session_id = params.get("sessionId")
    with _sessions_lock:
        session = _sessions.get(session_id)

    if not session:
        send_response(req_id, error={"code": -32602, "message": f"Session '{session_id}' not found"})
        return

    with session["lock"]:
        if session.get("busy"):
            send_response(req_id, error={"code": -32603, "message": "Session is already processing a prompt"})
            return
        session["busy"] = True
        session["cancelled"] = False

    prompt_blocks = params.get("prompt") or params.get("content") or []
    user_text_parts = []

    if isinstance(prompt_blocks, list):
        for block in prompt_blocks:
            if not isinstance(block, dict):
                continue
            b_type = block.get("type")
            if b_type == "text":
                user_text_parts.append(block.get("text", ""))
            elif b_type in ("resource", "resource_link"):
                uri = block.get("uri") or block.get("path") or "resource"
                txt = block.get("text") or block.get("content") or ""
                user_text_parts.append(f"\n[Resource: {uri}]\n{txt}\n")
    elif isinstance(prompt_blocks, str):
        user_text_parts.append(prompt_blocks)

    q_strip = "".join(user_text_parts).strip()
    if not q_strip:
        with session["lock"]:
            session["busy"] = False
        send_response(req_id, {"stopReason": "end_turn"})
        return

    if q_strip.startswith("/"):
        cmd = q_strip.split()[0].lower()
        if cmd == "/clear":
            with session["lock"]:
                session["history"] = [session["history"][0]]
                session["busy"] = False
            emit_message_chunk(session_id, "[chat: cleared]")
            send_response(req_id, {"stopReason": "end_turn"})
            return
        elif cmd in ("/adp", "/adapter"):
            with session["lock"]:
                session["adapters_on"] = not session.get("adapters_on", True)
                state_str = "on" if session["adapters_on"] else "off"
                session["busy"] = False
            emit_message_chunk(session_id, f"[adp: {state_str}]")
            send_response(req_id, {"stopReason": "end_turn"})
            return

    with session["lock"]:
        session["history"].append({"role": "user", "content": q_strip})

    def _worker():
        try:
            _execute_acp_turn(session_id, req_id)
        except Exception as e:
            log_debug(f"Turn execution error: {e}")
            send_response(req_id, error={"code": -32000, "message": str(e)})
        finally:
            with session["lock"]:
                session["busy"] = False

    threading.Thread(target=_worker, daemon=True).start()


def _execute_acp_turn(session_id: str, req_id: Any) -> None:
    with _sessions_lock:
        session = _sessions.get(session_id)
    if not session:
        send_response(req_id, error={"code": -32602, "message": "Session expired"})
        return

    workspace = session["workspace"]
    adapters_on = session.get("adapters_on", True)
    reasoning_budget = session.get("reasoning_budget", 500)
    is_yolo = session.get("is_yolo", False)

    with session["lock"]:
        raw_messages = list(session["history"])

    messages = [dict(m) for m in raw_messages]
    mem_ctx = memories.get_memory_context(workspace) if hasattr(memories, "get_memory_context") else ""
    if mem_ctx and messages and messages[-1].get("role") == "user":
        orig_content = messages[-1]["content"]
        messages[-1]["content"] = f"<context>\n{mem_ctx}\n</context>\n\nUser Question: {orig_content}"

    max_tokens = int(os.environ.get("AI_MAX_TOKENS", 8192))
    messages = core.prune_history(messages, max_tokens=int(max_tokens * 0.75))

    configs = cloud.get_active_configs(messages)
    if not configs:
        configs = [("http://localhost:8080/v1/chat/completions", {}, {"messages": messages, "stream": True}, 180)]

    url, headers, body, timeout = configs[0]

    for _round in range(10):
        with session["lock"]:
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
            res = _http_session.post(
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

        if res.status_code != 200:
            err_msg = res.text[:200].replace("\n", " ").strip()
            res.close()
            emit_message_chunk(session_id, f"\n[HTTP {res.status_code} Error: {err_msg}]\n")
            send_response(req_id, {"stopReason": "error"})
            return

        acc_content = []
        tool_calls_map = {}
        in_think_block = False

        with res:
            for line in res.iter_lines():
                with session["lock"]:
                    if session["cancelled"]:
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

        ans_text = "".join(acc_content)
        calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None

        if not calls and ans_text and adapters_on:
            calls = adapters.extract_fallback_tool_calls(ans_text) or None

        if not calls:
            clean_reply = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", ans_text).strip()
            with session["lock"]:
                session["history"].append({"role": "assistant", "content": clean_reply or ans_text})
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

            # Clean single-component leading slash emitted by small models
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

            # In-bounds gate with ACP permission prompt fallback
            def _confirm_gate(reason: str) -> bool:
                is_sec = reason.startswith(("OUT-OF-BOUNDS", "PYTHON DANGEROUS OP", "PYTHON SHELL ESCAPE"))
                if not is_sec and (is_yolo or os.environ.get("AI_CONFIRM_GATES") == "0"):
                    return True
                return _request_client_permission(session_id, tc["id"], f"{fname} {brief}")

            try:
                result = tools.run_tool(
                    fname,
                    args,
                    workspace,
                    confirm_gate_fn=_confirm_gate
                )
            except Exception as e:
                result = f"[tool error] {e}"

            tool_failed = (
                str(result).startswith("[error")
                or str(result).startswith("[tool error")
                or str(result).startswith("[denied]")
            )
            emit_tool_call(session_id, tc["id"], f"{fname} {brief}", "failed" if tool_failed else "completed")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": fname, "content": result})

            if str(result).startswith("[denied]"):
                with session["lock"]:
                    session["history"].extend(messages[len(session["history"]):])
                send_response(req_id, {"stopReason": "end_turn"})
                return

    with session["lock"]:
        session["history"].extend(messages[len(session["history"]):])
    send_response(req_id, {"stopReason": "end_turn"})


# ── Main JSON-RPC Stdio Loop ────────────────────────────────────────────────

def main():
    log_debug("Bridge process started, awaiting ACP JSON-RPC on stdin...")

    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue

        try:
            msg = json.loads(line_clean)
        except json.JSONDecodeError as e:
            log_debug(f"JSON decode error: {e}")
            continue

        if not isinstance(msg, dict):
            continue

        req_id = msg.get("id")

        # 1. Handle user permission answers from Zed
        if req_id is not None and ("result" in msg or "error" in msg):
            with _pending_lock:
                box = _pending_requests.pop(str(req_id), None)
            if box:
                res = msg.get("result") or {}
                approved = False
                if isinstance(res, dict):
                    outcome = res.get("outcome")
                    if isinstance(outcome, dict):
                        opt = outcome.get("optionId", "")
                        approved = outcome.get("outcome") == "selected" and ("allow" in opt)
                    elif isinstance(outcome, str):
                        approved = "allow" in outcome.lower()
                box["approved"] = approved
                box["event"].set()
            continue

        # 2. Dispatch incoming client requests
        method = msg.get("method")
        params = msg.get("params")
        if not isinstance(params, dict):
            params = {}

        try:
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
        except Exception as e:
            log_debug(f"Unhandled error in '{method}': {e}")
            if req_id is not None:
                send_response(req_id, error={"code": -32603, "message": f"Internal bridge error: {e}"})


if __name__ == "__main__":
    main()
