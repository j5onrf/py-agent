#!/usr/bin/env python3
"""ACP (Agent Client Protocol) stdio Bridge for PyCode / T3 Code WebApp [In-Memory Edition]
Connects PyCode GUI directly to py-agent engine and local llama.cpp server with full multimodal vision and grounding.
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

SESSION_HISTORIES: dict[str, list[dict[str, Any]]] = {}
SESSION_WORKSPACES: dict[str, str] = {}
CANCELLED_SESSIONS: set[str] = set()
ACTIVE_RESPONSES: dict[str, requests.Response] = {}


def send_rpc_response(req_id: Any, result: Any = None, error: Any = None) -> None:
    if req_id is None:
        return
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error:
        payload["error"] = error
    else:
        payload["result"] = result if result is not None else {}
    sys.stdout.write(json.dumps(payload) + "\n")
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
                    "text": text
                }
            }
        }
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def detect_workspace_mode(workspace: str) -> tuple[bool, str, bool]:
    home = os.path.realpath(os.path.expanduser("~"))
    ws_real = os.path.realpath(workspace)
    cfg_file = os.path.join(workspace, ".agent", "config.json")
    inherited_skill = os.environ.get("AI_ACTIVE_SKILL")

    if ws_real == home or not os.path.exists(os.path.join(workspace, ".agent")):
        return False, (inherited_skill or "chat"), False

    selected_profile, is_yolo = inherited_skill or "pi/pro", False
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                selected_profile = inherited_skill or data.get("profile", "pi/pro")
                is_yolo = data.get("yolo", False)
        except Exception:
            pass

    return True, selected_profile, is_yolo


def assemble_system_prompt(workspace: str, is_agent: bool, profile_name: str) -> str:
    safe_name = core.workspace_safe_name(workspace)
    use_gnd = core.get_state("grounding_active", False)

    if not is_agent:
        clean_name = profile_name if (profile_name and profile_name != "pi/pro") else "chat"
        skill_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
        prompt = skill_content or BASE_PROMPT_CHAT
        if use_gnd:
            prompt += "\n\nCRITICAL GROUNDING DIRECTIVE: You have access to live Google Search via the 'web_search' tool. Always call web_search for real-time facts, current dates, market prices, or recent software releases. When tool results are returned, you MUST base your final answer strictly on the verified live tool data and disregard any outdated pre-training knowledge."
        return prompt

    clean_name = profile_name if profile_name != "init" else "pi/pro"
    profile_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
    
    if profile_content:
        profile_content = profile_content.replace('Reply ONLY with: "Workspace loaded. Awaiting instructions."', "Execute the requested action immediately.")

    sys_prompt = profile_content or BASE_PROMPT_AGENT
    sys_prompt += f"\n\n### ACTIVE PROJECT WORKSPACE:\nYour active project root directory is: {workspace}\n"

    agent_dir = os.path.join(workspace, ".agent")
    use_map = "-map" in profile_name.lower()
    cfg_path = os.path.join(agent_dir, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as cf:
                use_map = json.load(cf).get("map", use_map)
        except Exception:
            pass

    if use_map and os.path.exists(agent_dir):
        for f in os.listdir(agent_dir):
            if f.startswith("index-map-") and f.endswith(".txt"):
                try:
                    with open(os.path.join(agent_dir, f), "r", encoding="utf-8", errors="ignore") as mf:
                        sys_prompt += f"### CODESPACE MAP:\n{mf.read().strip()}\n\n"
                        break
                except OSError:
                    pass

    if core.get_state("memory_active", False):
        try:
            tpm_facts = memories.tpm_get(safe_name)
            if tpm_facts:
                sys_prompt += f"\n{tpm_facts}\n"
        except Exception:
            pass

    return sys_prompt


def handle_acp_prompt(req_id: Any, session_id: str, prompt_items: list[dict[str, Any]], workspace: str, params: dict[str, Any] | None = None) -> None:
    CANCELLED_SESSIONS.discard(session_id)
    safe_name = core.workspace_safe_name(workspace)
    is_agent, profile_name, is_yolo = detect_workspace_mode(workspace)

    raw_mode = (params or {}).get("runtimeMode", "")
    opt_mode = next((opt.get("value") for opt in (params or {}).get("options", []) if opt.get("id") == "mode"), None)

    if opt_mode == "build" or raw_mode == "full-access":
        is_yolo = True
    elif opt_mode == "plan" or raw_mode == "supervised":
        is_yolo = False

    os.environ["AI_CONFIRM_GATES"] = "0" if (is_agent and is_yolo) else "1"
    core.save_state("yolo_mode", is_yolo)

    st = core.get_state()
    use_gnd = st.get("grounding_active", False)
    reasoning_active = st.get("reasoning_active", False)
    reasoning_budget = st.get("reasoning_budget", 500) if reasoning_active else 0
    enable_think = reasoning_active and reasoning_budget > 0
    budget_val = reasoning_budget if enable_think else 0
    show_thinking = enable_think

    think_kwargs = {
        "thinking_budget_tokens": budget_val,
        "reasoning_budget": budget_val,
        "chat_template_kwargs": {"enable_thinking": enable_think}
    }

    sys_context = assemble_system_prompt(workspace, is_agent, profile_name)
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
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": status_msg})
        send_rpc_response(req_id, result={"stopReason": "end_turn"})
        return

    has_images = any(i.get("type") == "image_url" for i in multimodal_content)
    turn_content = multimodal_content if has_images else user_text

    messages.append({"role": "user", "content": turn_content})

    configs = agent_cloud.get_active_configs(messages) if hasattr(agent_cloud, "get_active_configs") else []
    if not configs:
        configs = [("http://localhost:8080/v1/chat/completions", {}, {"messages": messages, "stream": True, "model": "local-model", **think_kwargs}, 180)]

    accumulated_ans = ""
    in_think_block = False
    max_rounds = 10 if (is_agent or use_gnd) else 1

    try:
        for _round in range(max_rounds):
            if session_id in CANCELLED_SESSIONS:
                break

            tool_calls_map = {}
            round_text = ""

            url, headers, base_body, timeout = configs[0]
            is_local = "localhost" in url or "127.0.0.1" in url or base_body.get("model") == "local-model"

            body = {
                "messages": messages,
                "stream": True,
                **base_body
            }
            if is_local:
                body.update(think_kwargs)

            active_tools = []
            if is_agent:
                is_py = "-py" in profile_name.lower() or "py-" in profile_name.lower()
                active_tools = list(ipython.IPYTHON_TOOL) if (is_py and ipython) else list(tools.EDIT_TOOLS)
            if use_gnd and hasattr(tools, "WEB_TOOL"):
                active_tools.append(tools.WEB_TOOL)

            if active_tools:
                body["tools"] = active_tools

            res = None
            try:
                res = core._session.post(url, json=body, headers={"Content-Type": "application/json", **headers}, timeout=timeout, stream=True)
                ACTIVE_RESPONSES[session_id] = res

                if res.status_code != 200:
                    send_acp_chunk(session_id, f"\n[Error: LLM HTTP {res.status_code}: {res.text[:100]}]\n")
                    break

                for line in res.iter_lines():
                    if session_id in CANCELLED_SESSIONS:
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
                        thinking_chunk = delta.get("reasoning_content") or delta.get("thinking") or delta.get("reasoning") or ""

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
                                tc_entry = tool_calls_map.setdefault(idx, {"id": tc.get("id", ""), "type": "function", "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}})
                                if tc.get("function", {}).get("name"):
                                    tc_entry["function"]["name"] = tc["function"]["name"]
                                tc_entry["function"]["arguments"] += tc.get("function", {}).get("arguments", "")

                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

            except Exception as e:
                if session_id not in CANCELLED_SESSIONS:
                    send_acp_chunk(session_id, f"\n[Connection error: {e}]\n")
                break
            finally:
                if res is not None:
                    try:
                        res.close()
                    except Exception:
                        pass
                ACTIVE_RESPONSES.pop(session_id, None)

            if session_id in CANCELLED_SESSIONS:
                send_acp_chunk(session_id, "\n\n*(Generation stopped)*")
                break

            calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None
            has_web_call = use_gnd and any(c.get("function", {}).get("name") == "web_search" for c in (calls or []))

            if not calls or (not is_agent and not has_web_call):
                messages.append({"role": "assistant", "content": round_text})
                break

            messages.append({"role": "assistant", "content": round_text or None, "tool_calls": calls})

            for tc in calls:
                if session_id in CANCELLED_SESSIONS:
                    break
                fname = tc.get("function", {}).get("name", "")
                raw_args = tc.get("function", {}).get("arguments") or ""
                args = core._heal_tool_args(raw_args)

                # Strategy A: Safe Read-Only Exception for web_search
                if fname == "web_search":
                    query_term = str(args.get("query", "")).strip()
                    send_acp_chunk(session_id, f"\n\n*Searching Google for: `{query_term}`...*\n")
                    try:
                        result = tools.search_web_gemini(query_term) if hasattr(tools, "search_web_gemini") else tools.run_tool(fname, args, workspace)
                    except Exception as e:
                        result = f"[error] web search failed: {e}"
                else:
                    send_acp_chunk(session_id, f"\n\n*Running tool: `{fname}`...*\n")
                    try:
                        result = tools.run_tool(fname, args, workspace)
                    except Exception as e:
                        result = f"[error] tool execution failed: {e}"

                pruned_result = result if len(result) <= 2000 else result[:1500] + f"\n... [Snipped {len(result) - 1500} chars]"
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned_result})

        if is_agent and user_text and accumulated_ans and session_id not in CANCELLED_SESSIONS:
            try:
                sessions.log_turn(safe_name, user_text, accumulated_ans)
                if core.get_state("memory_active", False):
                    core.background_tpm_update(user_text, accumulated_ans, safe_name, workspace)
            except Exception:
                pass

        if tts.is_tts_enabled() and accumulated_ans and session_id not in CANCELLED_SESSIONS:
            try:
                tts.speak_response(accumulated_ans)
            except Exception:
                pass

    finally:
        stop_reason = "cancelled" if session_id in CANCELLED_SESSIONS else "end_turn"
        send_rpc_response(req_id, result={"stopReason": stop_reason})


def main():
    default_workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    active_session_id = f"pyagent-{uuid.uuid4().hex[:8]}"

    def _voice_watcher():
        pending_file = os.path.join(CFG_DIR, ".voice_pending.txt")
        while True:
            try:
                time.sleep(0.3)
                if os.path.exists(pending_file) and os.path.getsize(pending_file) > 0:
                    with open(pending_file, "r", encoding="utf-8") as vf:
                        text = vf.read().strip()
                    try:
                        os.remove(pending_file)
                    except OSError:
                        pass
                    if text and active_session_id:
                        active_cwd = SESSION_WORKSPACES.get(active_session_id, default_workspace)
                        sys.stdout.write(json.dumps({
                            "jsonrpc": "2.0",
                            "method": "session/update",
                            "params": {
                                "sessionId": active_session_id,
                                "update": {
                                    "sessionUpdate": "user_message_chunk",
                                    "content": {"type": "text", "text": text}
                                }
                            }
                        }) + "\n")
                        sys.stdout.flush()
                        threading.Thread(target=handle_acp_prompt, args=(None, active_session_id, [{"type": "text", "text": text}], active_cwd), daemon=True).start()
            except Exception:
                pass

    threading.Thread(target=_voice_watcher, daemon=True).start()

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            send_rpc_response(req_id, result={
                "protocolVersion": 1,
                "agentCapabilities": {
                    "sessionCapabilities": {
                        "list": {}
                    }
                },
                "agentInfo": {
                    "name": "py-agent",
                    "version": "1.0.0"
                }
            })
        elif method == "authenticate":
            send_rpc_response(req_id, result={})
        elif method in ("session/new", "createSession", "session/create"):
            active_session_id = params.get("sessionId") or f"pyagent-{uuid.uuid4().hex[:8]}"
            session_cwd = params.get("cwd") or default_workspace
            SESSION_WORKSPACES[active_session_id] = os.path.realpath(session_cwd)
            send_rpc_response(req_id, result={"sessionId": active_session_id})
        elif method in ("session/list", "listSessions"):
            active_cwd = SESSION_WORKSPACES.get(active_session_id, default_workspace)
            send_rpc_response(req_id, result={"sessions": [{"sessionId": active_session_id, "cwd": active_cwd}]})
        elif method in ("session/prompt", "prompt"):
            req_session_id = params.get("sessionId") or active_session_id
            active_cwd = SESSION_WORKSPACES.get(req_session_id, default_workspace)
            prompt_items = params.get("prompt", [])
            threading.Thread(target=handle_acp_prompt, args=(req_id, req_session_id, prompt_items, active_cwd, params), daemon=True).start()
        elif method in ("session/cancel", "cancel"):
            req_session_id = params.get("sessionId") or active_session_id
            CANCELLED_SESSIONS.add(req_session_id)
            if resp := ACTIVE_RESPONSES.get(req_session_id):
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
