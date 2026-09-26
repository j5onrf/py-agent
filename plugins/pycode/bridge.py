#!/usr/bin/env python3
"""ACP (Agent Client Protocol) stdio Bridge for PyCode / T3 Code WebApp [Hardened Production Ready]
Connects PyCode GUI directly to py-agent engine and local llama.cpp server with full multimodal vision, OKF memory, and adapters.
"""

import json
import os
import sys
import threading
import time
import uuid
from typing import Any

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
SKILLS_DIR = os.path.join(CFG_DIR, "skills")
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_adapters as adapters
import agent_cloud
import agent_core as core
import agent_ipython as ipython
import agent_memories as memories
import agent_sessions as sessions
import agent_skills as skills
import agent_tools as tools
import agent_tts as tts
import requests

BASE_PROMPT_CHAT = "Active, natural conversational assistant."
BASE_PROMPT_AGENT = "Active local workspace developer agent."

MAX_HISTORY_MESSAGES = 40
MAX_TRACKED_SESSIONS = 50
MAX_MAP_FILE_BYTES = 64 * 1024  # 64 KiB cap

# Thread synchronization
STDOUT_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()

SESSION_HISTORIES: dict[str, list[dict[str, Any]]] = {}
SESSION_WORKSPACES: dict[str, str] = {}
SESSION_LAST_ACCESSED: dict[str, float] = {}
SESSION_CANCEL_EVENTS: dict[str, threading.Event] = {}
ACTIVE_RESPONSES: dict[str, requests.Response] = {}

FORBIDDEN_ROOTS = {
    "/", "/root", "/bin", "/sbin", "/usr", "/usr/bin", "/usr/sbin",
    "/etc", "/dev", "/proc", "/sys", "/var",
}
FORBIDDEN_USER_SUBDIRS = {
    ".ssh", ".gnupg", ".aws", ".config/py-agent", ".local/share",
}


def send_rpc_response(req_id: Any, result: Any = None, error: Any = None) -> None:
    if req_id is None:
        return
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result if result is not None else {}
    serialized = json.dumps(payload)
    with STDOUT_LOCK:
        sys.stdout.write(serialized + "\n")
        sys.stdout.flush()


def send_acp_chunk(session_id: str, text: str, is_thought: bool = False) -> None:
    if not text:
        return
    update_type = "agent_thought_chunk" if is_thought else "agent_message_chunk"
    payload = {
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": update_type,
                "content": {
                    "type": "text",
                    "text": text,
                },
            },
        },
    }
    serialized = json.dumps(payload)
    with STDOUT_LOCK:
        sys.stdout.write(serialized + "\n")
        sys.stdout.flush()


def validate_workspace(cwd_candidate: str | None, default_workspace: str) -> str:
    target = os.path.realpath(os.path.expanduser(cwd_candidate or default_workspace))
    if not os.path.isdir(target):
        return default_workspace

    if target in FORBIDDEN_ROOTS:
        sys.stderr.write(f"[pycode security] Blocked forbidden root workspace: {target}\n")
        return default_workspace

    home = os.path.realpath(os.path.expanduser("~"))
    for sensitive in FORBIDDEN_USER_SUBDIRS:
        bad_path = os.path.join(home, sensitive)
        if target == bad_path or target.startswith(bad_path + os.sep):
            sys.stderr.write(f"[pycode security] Blocked sensitive user directory: {target}\n")
            return default_workspace

    return target


def detect_workspace_mode(workspace: str) -> tuple[bool, str, bool]:
    home = os.path.realpath(os.path.expanduser("~"))
    ws_real = os.path.realpath(workspace)
    cfg_file = os.path.join(ws_real, ".agent", "config.json")
    inherited_skill = os.environ.get("AI_ACTIVE_SKILL")
    env_yolo = os.environ.get("AI_YOLO") == "1"

    if ws_real == home or not os.path.exists(os.path.join(ws_real, ".agent")):
        return False, (inherited_skill or "chat"), env_yolo

    selected_profile = inherited_skill or "pi/pro"
    is_yolo = env_yolo
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                selected_profile = inherited_skill or data.get("profile", "pi/pro")
                is_yolo = is_yolo or data.get("yolo", False)
        except Exception as e:
            sys.stderr.write(f"[pycode bridge] warning: failed reading config {cfg_file}: {e}\n")

    return True, selected_profile, is_yolo


def make_confirm_gate(workspace: str, is_yolo: bool):
    """Scoped confirmation gate for non-interactive ACP bridge requests."""
    def confirm_gate(prompt_or_reason: str) -> bool:
        if not is_yolo:
            sys.stderr.write(f"[pycode security] Action rejected (supervised/plan mode): {prompt_or_reason}\n")
            return False
        # In YOLO/build mode, standard in-bounds edits pass.
        # Boundary violations (out-of-bounds or destructive system commands) must fail-closed.
        sys.stderr.write(f"[pycode security] Zero-trust boundary violation rejected: {prompt_or_reason}\n")
        return False

    return confirm_gate


def assemble_system_prompt(workspace: str, is_agent: bool, profile_name: str) -> str:
    use_gnd = core.get_state("grounding_active", False)

    if not is_agent:
        clean_name = profile_name if (profile_name and profile_name != "pi/pro") else "chat"
        skill_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
        prompt = skill_content or BASE_PROMPT_CHAT
        if use_gnd:
            prompt += (
                "\n\nCRITICAL GROUNDING DIRECTIVE: You have access to live Google Search via the 'web_search' tool. "
                "Always call web_search for real-time facts, current dates, or documentation. Base your answer strictly on verified live tool data."
            )
        return prompt

    clean_name = profile_name if profile_name != "init" else "pi/pro"
    profile_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)

    if profile_content:
        profile_content = profile_content.replace(
            'Reply ONLY with: "Workspace loaded. Awaiting instructions."',
            "Execute the requested action immediately.",
        )

    sys_prompt = profile_content or BASE_PROMPT_AGENT
    sys_prompt += f"\n\n### ACTIVE PROJECT WORKSPACE:\nYour active project root directory is: {workspace}\n"

    agent_dir = os.path.join(workspace, ".agent")
    real_agent_dir = os.path.realpath(agent_dir)
    # Prevent traversal or symlink escapes outside the workspace root
    if not real_agent_dir.startswith(workspace):
        return sys_prompt

    use_map = "-map" in profile_name.lower()
    cfg_path = os.path.join(agent_dir, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as cf:
                use_map = json.load(cf).get("map", use_map)
        except Exception as e:
            sys.stderr.write(f"[pycode bridge] warning: failed reading config {cfg_path}: {e}\n")

    if use_map and os.path.isdir(agent_dir):
        try:
            for f in os.listdir(agent_dir):
                if f.startswith("index-map-") and f.endswith(".txt"):
                    fpath = os.path.join(agent_dir, f)
                    try:
                        if os.path.getsize(fpath) <= MAX_MAP_FILE_BYTES:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as mf:
                                sys_prompt += f"### CODESPACE MAP:\n{mf.read().strip()}\n\n"
                                break
                    except OSError:
                        pass
        except OSError as e:
            sys.stderr.write(f"[pycode bridge] warning: failed reading map dir {agent_dir}: {e}\n")

    # Open Knowledge Format (OKF) Git-native memory injection
    if core.get_state("memory_active", False):
        try:
            mem_ctx = memories.get_memory_context(workspace)
            if mem_ctx:
                sys_prompt += f"\n{mem_ctx}\n"
        except Exception as e:
            sys.stderr.write(f"[pycode bridge] warning: memory injection error: {e}\n")

    return sys_prompt


def _prune_history(messages: list[dict[str, Any]], max_messages: int = MAX_HISTORY_MESSAGES) -> None:
    """Safely bound history size without severing assistant-tool call/response pairs."""
    if len(messages) <= max_messages:
        return

    system_msg = messages[0] if (messages and messages[0].get("role") == "system") else None
    start_idx = 1 if system_msg else 0
    tail = messages[-(max_messages - 1 if system_msg else max_messages):]

    # Don't orphan a tool response without its matching assistant tool_calls message
    while tail and tail[0].get("role") == "tool":
        tail = tail[1:]

    new_history = ([system_msg] if system_msg else []) + tail
    messages[:] = new_history


def handle_acp_prompt(
    req_id: Any,
    session_id: str,
    prompt_items: list[dict[str, Any]],
    workspace: str,
    params: dict[str, Any] | None = None,
) -> None:
    cancel_evt = threading.Event()

    with STATE_LOCK:
        if old_evt := SESSION_CANCEL_EVENTS.get(session_id):
            old_evt.set()
        SESSION_CANCEL_EVENTS[session_id] = cancel_evt
        SESSION_LAST_ACCESSED[session_id] = time.time()

        # Enforce LRU session limits to prevent unbounded memory growth
        if len(SESSION_HISTORIES) > MAX_TRACKED_SESSIONS:
            oldest_sid = min(SESSION_LAST_ACCESSED, key=SESSION_LAST_ACCESSED.get)
            if oldest_sid != session_id:
                SESSION_HISTORIES.pop(oldest_sid, None)
                SESSION_WORKSPACES.pop(oldest_sid, None)
                SESSION_LAST_ACCESSED.pop(oldest_sid, None)

    safe_name = core.workspace_safe_name(workspace)
    is_agent, profile_name, is_yolo = detect_workspace_mode(workspace)

    raw_mode = (params or {}).get("runtimeMode", "")
    opt_mode = next((opt.get("value") for opt in (params or {}).get("options", []) if opt.get("id") == "mode"), None)

    if opt_mode == "build" or raw_mode == "full-access":
        is_yolo = True
    elif opt_mode == "plan" or raw_mode == "supervised":
        is_yolo = False

    st = core.get_state()
    use_gnd = st.get("grounding_active", False)
    adapters_on = st.get("adapters_active", False)
    reasoning_active = st.get("reasoning_active", False)
    reasoning_budget = st.get("reasoning_budget", 500) if reasoning_active else 0
    enable_think = reasoning_active and reasoning_budget > 0
    budget_val = reasoning_budget if enable_think else 0
    show_thinking = enable_think

    think_kwargs = {
        "thinking_budget_tokens": budget_val,
        "reasoning_budget": budget_val,
        "chat_template_kwargs": {"enable_thinking": enable_think},
    }

    sys_context = assemble_system_prompt(workspace, is_agent, profile_name)

    with STATE_LOCK:
        if session_id not in SESSION_HISTORIES:
            SESSION_HISTORIES[session_id] = [{"role": "system", "content": sys_context}]
        else:
            if SESSION_HISTORIES[session_id] and SESSION_HISTORIES[session_id][0].get("role") == "system":
                SESSION_HISTORIES[session_id][0]["content"] = sys_context
        messages = SESSION_HISTORIES[session_id]

    # Convert ACP prompt_items into standard multimodal payload
    multimodal_content = []
    text_chunks = []

    for item in prompt_items:
        if not isinstance(item, dict):
            continue
        itype = item.get("type", "")
        if itype == "text":
            txt = item.get("text", "")
            if txt:
                text_chunks.append(txt)
                multimodal_content.append({"type": "text", "text": txt})
        elif itype in ("image", "image_url"):
            data = item.get("data") or item.get("image") or ""
            mime = item.get("mimeType") or item.get("mime_type") or "image/png"
            url = item.get("image_url", {}).get("url") if isinstance(item.get("image_url"), dict) else item.get("url")

            if not url and data:
                url = f"data:{mime};base64,{data}" if not data.startswith("data:") else data

            if url:
                multimodal_content.append({"type": "image_url", "image_url": {"url": url}})

    user_text = " ".join(text_chunks).strip() or "Describe this image."

    # Intercept /gnd slash command directly in PyCode GUI
    if user_text.lower().strip() in ("/gnd", "/ground", "/web"):
        cur_gnd = not core.get_state("grounding_active", False)
        core.save_state("grounding_active", cur_gnd)
        status_msg = f"\n*Google Search grounding via Gemini {'enabled' if cur_gnd else 'disabled'}.*\n"
        send_acp_chunk(session_id, status_msg)
        with STATE_LOCK:
            messages.append({"role": "user", "content": user_text})
            messages.append({"role": "assistant", "content": status_msg})
        send_rpc_response(req_id, result={"stopReason": "end_turn"})
        return

    has_images = any(i.get("type") == "image_url" for i in multimodal_content)
    turn_content = multimodal_content if has_images else user_text

    with STATE_LOCK:
        messages.append({"role": "user", "content": turn_content})
        _prune_history(messages)

    # Preprocess multimodal messages through fallback vision bridge if available
    if hasattr(core, "preprocess_multimodal_messages"):
        messages = core.preprocess_multimodal_messages(messages)

    configs = agent_cloud.get_active_configs(messages) if hasattr(agent_cloud, "get_active_configs") else []
    if not configs:
        configs = [(
            "http://localhost:8080/v1/chat/completions",
            {},
            {"messages": messages, "stream": True, "model": "local-model", **think_kwargs},
            180,
        )]

    accumulated_ans = ""
    in_think_block = False
    max_rounds = 10 if (is_agent or use_gnd) else 1
    confirm_gate = make_confirm_gate(workspace, is_yolo)

    try:
        for _round in range(max_rounds):
            if cancel_evt.is_set():
                break

            tool_calls_map = {}
            round_text = ""

            url, headers, base_body, timeout = configs[0]
            is_local = "localhost" in url or "127.0.0.1" in url or base_body.get("model") == "local-model"

            body = {"messages": messages, "stream": True, **base_body}
            if is_local:
                body.update(think_kwargs)

            active_tools = []
            if is_agent:
                is_py = (
                    "-py" in profile_name.lower()
                    or "py-" in profile_name.lower()
                    or st.get("ipython_mode", False)
                )
                active_tools = list(ipython.IPYTHON_TOOL) if is_py else list(tools.EDIT_TOOLS)
            if use_gnd and hasattr(tools, "WEB_TOOL"):
                active_tools.append(tools.WEB_TOOL)

            if active_tools:
                body["tools"] = active_tools

            res = None
            try:
                res = core._session.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json", **headers},
                    timeout=timeout,
                    stream=True,
                )
                with STATE_LOCK:
                    ACTIVE_RESPONSES[session_id] = res

                if res.status_code != 200:
                    send_acp_chunk(session_id, f"\n[Error: LLM HTTP {res.status_code}: {res.text[:100]}]\n")
                    break

                for line in res.iter_lines():
                    if cancel_evt.is_set():
                        break
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
                        choices = data.get("choices", [{}])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        text_chunk = delta.get("content") or ""
                        thinking_chunk = (
                            delta.get("reasoning_content")
                            or delta.get("thinking")
                            or delta.get("reasoning")
                            or ""
                        )

                        if thinking_chunk:
                            if enable_think:
                                if not in_think_block:
                                    in_think_block = True
                                    send_acp_chunk(session_id, "> *Thinking...* ")
                                send_acp_chunk(session_id, thinking_chunk.replace("\n", "\n> "))

                        elif text_chunk:
                            if in_think_block and "</think>" not in text_chunk:
                                if show_thinking:
                                    send_acp_chunk(session_id, "\n\n")
                                in_think_block = False

                            if "<think>" in text_chunk:
                                in_think_block = True
                                text_chunk = text_chunk.replace("<think>", "")
                                if show_thinking:
                                    send_acp_chunk(session_id, "> *Thinking...* ")

                            if "</think>" in text_chunk:
                                parts = text_chunk.split("</think>", 1)
                                if parts[0] and show_thinking:
                                    send_acp_chunk(session_id, parts[0].replace("\n", "\n> "))
                                in_think_block = False
                                if show_thinking:
                                    send_acp_chunk(session_id, "\n\n")
                                text_chunk = parts[1] if len(parts) > 1 else ""

                        if text_chunk:
                            if in_think_block:
                                if show_thinking:
                                    send_acp_chunk(session_id, text_chunk.replace("\n", "\n> "))
                            else:
                                accumulated_ans += text_chunk
                                round_text += text_chunk
                                send_acp_chunk(session_id, text_chunk, is_thought=False)

                        if is_agent or use_gnd:
                            for tc in delta.get("tool_calls", []):
                                idx = tc.get("index", 0)
                                call_id = tc.get("id") or f"call_{_round}_{idx}"
                                tc_entry = tool_calls_map.setdefault(
                                    idx,
                                    {
                                        "id": call_id,
                                        "type": "function",
                                        "function": {
                                            "name": tc.get("function", {}).get("name", ""),
                                            "arguments": "",
                                        },
                                    },
                                )
                                if tc.get("id"):
                                    tc_entry["id"] = tc["id"]
                                if tc.get("function", {}).get("name"):
                                    tc_entry["function"]["name"] = tc["function"]["name"]
                                tc_entry["function"]["arguments"] += (
                                    tc.get("function", {}).get("arguments") or ""
                                )

                    except (json.JSONDecodeError, KeyError, IndexError) as err:
                        sys.stderr.write(f"[pycode bridge] warning: SSE parse error on chunk: {err}\n")

            except Exception as e:
                if not cancel_evt.is_set():
                    send_acp_chunk(session_id, f"\n[Connection error: {e}]\n")
                break
            finally:
                if res is not None:
                    try:
                        res.close()
                    except Exception:
                        pass
                with STATE_LOCK:
                    ACTIVE_RESPONSES.pop(session_id, None)

            # Ensure GUI quote block closes cleanly
            if in_think_block:
                send_acp_chunk(session_id, "\n\n")
                in_think_block = False

            if cancel_evt.is_set():
                send_acp_chunk(session_id, "\n\n*(Generation stopped)*")
                break

            calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None

            # Self-healing fallback tool extraction for small models in GUI
            if not calls and round_text and is_agent and adapters_on:
                try:
                    calls = adapters.extract_fallback_tool_calls(round_text) or None
                except Exception as e:
                    sys.stderr.write(f"[pycode bridge] warning: fallback adapter error: {e}\n")

            has_web_call = use_gnd and any(
                c.get("function", {}).get("name") == "web_search" for c in (calls or [])
            )

            if not calls or (not is_agent and not has_web_call):
                with STATE_LOCK:
                    messages.append({"role": "assistant", "content": round_text})
                break

            for idx, tc in enumerate(calls):
                if not tc.get("id"):
                    tc["id"] = f"call_{_round}_{idx}"

            with STATE_LOCK:
                messages.append({"role": "assistant", "content": round_text or None, "tool_calls": calls})

            for tc in calls:
                if cancel_evt.is_set():
                    break
                fname = tc.get("function", {}).get("name", "")
                raw_args = tc.get("function", {}).get("arguments") or ""
                cid = tc.get("id") or f"call_{_round}_0"

                if adapters_on:
                    try:
                        fname, args = adapters.heal_tool_call(fname, raw_args)
                    except Exception as e:
                        sys.stderr.write(f"[pycode bridge] warning: adapter healing error: {e}\n")
                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                        except Exception:
                            args = {}
                else:
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except Exception:
                        args = {}

                brief = str(
                    args.get("code")
                    or args.get("symbol")
                    or args.get("path")
                    or args.get("command")
                    or args.get("query")
                    or ""
                )[:80]
                send_acp_chunk(session_id, f"\n\n*Running `{fname}`: `{brief}`...*\n")

                try:
                    result = tools.run_tool(fname, args, workspace, confirm_gate_fn=confirm_gate)
                except Exception as e:
                    result = f"[error] tool execution failed: {e}"

                result_str = str(result) if result is not None else ""
                pruned_result = (
                    result_str
                    if len(result_str) <= 2000
                    else result_str[:1500] + f"\n... [Snipped {len(result_str) - 1500} chars]"
                )
                with STATE_LOCK:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": cid,
                        "name": fname,
                        "content": pruned_result,
                    })

        if is_agent and user_text and accumulated_ans and not cancel_evt.is_set():
            try:
                sessions.log_turn(safe_name, user_text, accumulated_ans)
            except Exception as e:
                sys.stderr.write(f"[pycode bridge] warning: session log error: {e}\n")

        if tts.is_tts_enabled() and accumulated_ans and not cancel_evt.is_set():
            try:
                tts.speak_response(accumulated_ans)
            except Exception as e:
                sys.stderr.write(f"[pycode bridge] warning: TTS error: {e}\n")

    finally:
        with STATE_LOCK:
            SESSION_CANCEL_EVENTS.pop(session_id, None)
        stop_reason = "cancelled" if cancel_evt.is_set() else "end_turn"
        send_rpc_response(req_id, result={"stopReason": stop_reason})


def main():
    default_workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    active_session_id = f"pyagent-{uuid.uuid4().hex[:8]}"

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(req, dict):
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})
        if not isinstance(params, dict):
            params = {}

        if method == "initialize":
            send_rpc_response(req_id, result={
                "protocolVersion": 1,
                "agentCapabilities": {
                    "sessionCapabilities": {
                        "list": {},
                    },
                },
                "agentInfo": {
                    "name": "py-agent",
                    "version": "1.0.0",
                },
            })
        elif method == "authenticate":
            send_rpc_response(req_id, result={})
        elif method in ("session/new", "createSession", "session/create"):
            active_session_id = params.get("sessionId") or f"pyagent-{uuid.uuid4().hex[:8]}"
            session_cwd = validate_workspace(params.get("cwd"), default_workspace)
            with STATE_LOCK:
                SESSION_WORKSPACES[active_session_id] = session_cwd
                SESSION_LAST_ACCESSED[active_session_id] = time.time()
            send_rpc_response(req_id, result={"sessionId": active_session_id})
        elif method in ("session/list", "listSessions"):
            with STATE_LOCK:
                active_cwd = SESSION_WORKSPACES.get(active_session_id, default_workspace)
            send_rpc_response(req_id, result={"sessions": [{"sessionId": active_session_id, "cwd": active_cwd}]})
        elif method in ("session/prompt", "prompt"):
            req_session_id = params.get("sessionId") or active_session_id
            with STATE_LOCK:
                active_cwd = SESSION_WORKSPACES.get(req_session_id, default_workspace)
            prompt_items = params.get("prompt", [])
            threading.Thread(
                target=handle_acp_prompt,
                args=(req_id, req_session_id, prompt_items, active_cwd, params),
                daemon=True,
            ).start()
        elif method in ("session/cancel", "cancel"):
            req_session_id = params.get("sessionId") or active_session_id
            with STATE_LOCK:
                if evt := SESSION_CANCEL_EVENTS.get(req_session_id):
                    evt.set()
                resp = ACTIVE_RESPONSES.get(req_session_id)
            if resp:
                try:
                    resp.close()
                except Exception:
                    pass
            send_rpc_response(req_id, result={})
        elif method == "tools/list":
            t_list = list(tools.EDIT_TOOLS)
            if core.get_state("grounding_active", False) and hasattr(tools, "WEB_TOOL"):
                t_list.append(tools.WEB_TOOL)
            send_rpc_response(req_id, result={"tools": t_list})
        elif method == "shutdown":
            send_rpc_response(req_id, result={"status": "ok"})
            break
        else:
            send_rpc_response(req_id, result={})


if __name__ == "__main__":
    main()
