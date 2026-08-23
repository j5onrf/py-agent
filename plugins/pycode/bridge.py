#!/usr/bin/env python3
"""ACP (Agent Client Protocol) stdio Bridge for PyCode / T3 Code WebApp
Connects PyCode GUI directly to py-agent engine and local llama.cpp server.
"""

import os
import sys
import json
import uuid
import time
import threading
from typing import Dict, Any, List, Optional, Tuple

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
SKILLS_DIR = os.path.join(CFG_DIR, "skills")
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_core as core
import agent_tools as tools
import agent_skills as skills
import agent_cloud
import agent_tts as tts
import agent_voice as voice

BASE_PROMPT_CHAT = "### Conversational Guidelines:\n- Role: Active, natural, and highly articulate conversational assistant.\n- Tone: Professional, warm, objective, and intellectually engaging.\n\n"
BASE_PROMPT_AGENT = "Active local project workspace developer agent.\nIf <context> is provided, answer directly using only its facts. Otherwise, answer normally.\n\n"

SESSION_HISTORIES: Dict[str, List[Dict[str, Any]]] = {}
SESSION_WORKSPACES: Dict[str, str] = {}


def send_rpc_response(req_id: Any, result: Any = None, error: Any = None) -> None:
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
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


def detect_workspace_mode(workspace: str) -> Tuple[bool, str, bool]:
    home = os.path.realpath(os.path.expanduser("~"))
    ws_real = os.path.realpath(workspace)
    cfg_file = os.path.join(workspace, ".agent", "config.json")

    inherited_skill = os.environ.get("AI_ACTIVE_SKILL")

    if ws_real == home or not os.path.exists(os.path.join(workspace, ".agent")):
        return False, (inherited_skill or "chat"), False

    selected_profile, is_yolo = inherited_skill or "default", False
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                selected_profile = inherited_skill or data.get("profile", "default")
                is_yolo = data.get("yolo", False)
        except Exception:
            pass

    return True, selected_profile, is_yolo


def assemble_system_prompt(workspace: str, is_agent: bool, profile_name: str) -> str:
    safe_name = core.workspace_safe_name(workspace)

    if not is_agent:
        skill_content = skills.load_skill_content("chat", SKILLS_DIR, CFG_DIR)
        return skill_content or BASE_PROMPT_CHAT

    clean_name = profile_name if profile_name not in ("default", "init") else "init"
    profile_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
    
    # Clean startup greeting directive for GUI sessions
    if profile_content:
        profile_content = profile_content.replace('Reply ONLY with: "Workspace loaded. Awaiting instructions."', "Execute the requested action immediately.")

    sys_prompt = (BASE_PROMPT_AGENT + f"\n\n### Active Skill/Role Instructions:\n{profile_content}\n") if (clean_name == "init" and profile_content) else (profile_content or BASE_PROMPT_AGENT)
    sys_prompt += f"\n\n### ACTIVE PROJECT WORKSPACE:\nYour active project root directory is: {workspace}\n"
    sys_prompt += "Capabilities: read_symbol, trace_symbol, blast_radius, find_symbol, architecture_overview, read_file, write_file, list_dir, run_command.\n\n"

    agent_dir = os.path.join(workspace, ".agent")
    if os.path.exists(agent_dir):
        for f in os.listdir(agent_dir):
            if f.startswith("index-map-") and f.endswith(".txt"):
                try:
                    with open(os.path.join(agent_dir, f), "r", encoding="utf-8", errors="ignore") as mf:
                        sys_prompt += f"### CODESPACE MAP:\n{mf.read().strip()}\n\n"
                        break
                except OSError:
                    pass

    try:
        tpm_facts = core.run_mod("ai-agent-memories", "tpm-get", safe_name)
        if tpm_facts:
            sys_prompt += f"### USER FACTS & PREFERENCES (TPM):\n{tpm_facts}\n\n"
    except Exception:
        pass

    return sys_prompt


def handle_acp_prompt(req_id: Any, session_id: str, prompt_items: List[Dict[str, Any]], workspace: str) -> None:
    user_text = " ".join(item.get("text", "") for item in prompt_items if isinstance(item, dict) and item.get("type") == "text").strip()
    if not user_text:
        user_text = "Hello"

    safe_name = core.workspace_safe_name(workspace)
    is_agent, profile_name, is_yolo = detect_workspace_mode(workspace)
    
    # YOLO only active in workspace agent mode, strictly OFF in plain chat mode
    if is_agent and is_yolo:
        os.environ["AI_CONFIRM_GATES"] = "0"
    else:
        os.environ["AI_CONFIRM_GATES"] = "1"

    # Read state directly from .state.json
    st = core.get_state()
    reasoning_active = st.get("reasoning_active", False)
    reasoning_budget = st.get("reasoning_budget", 500) if reasoning_active else 0
    show_thinking = st.get("show_thinking", True)
    enable_think = reasoning_active and reasoning_budget > 0

    think_kwargs = {
        "thinking_budget_tokens": reasoning_budget,
        "reasoning_budget": reasoning_budget,
        "chat_template_kwargs": {"enable_thinking": enable_think}
    }

    if session_id not in SESSION_HISTORIES:
        sys_context = assemble_system_prompt(workspace, is_agent, profile_name)
        SESSION_HISTORIES[session_id] = [{"role": "system", "content": sys_context}]

    messages = SESSION_HISTORIES[session_id]
    messages.append({"role": "user", "content": user_text})

    configs = agent_cloud.get_active_configs(messages) if hasattr(agent_cloud, "get_active_configs") else []
    if not configs:
        configs = [("http://localhost:8080/v1/chat/completions", {}, {"messages": messages, "stream": True, "model": "local-model", **think_kwargs}, 180)]

    accumulated_ans = ""
    in_think_block = False
    max_rounds = 10 if is_agent else 1

    for _round in range(max_rounds):
        tool_calls_map = {}
        round_text = ""

        url, headers, base_body, timeout = configs[0]
        is_local = "localhost" in url or "127.0.0.1" in url or base_body.get("model") == "local-model"

        body = {
            "messages": messages,
            "stream": True,
            **(think_kwargs if is_local else {})
        }
        if is_agent:
            body["tools"] = tools.EDIT_TOOLS

        body = {**base_body, **body}

        try:
            res = core._session.post(url, json=body, headers={"Content-Type": "application/json", **headers}, timeout=timeout, stream=True)
            if res.status_code != 200:
                send_acp_chunk(session_id, f"\n[Error: LLM HTTP {res.status_code}: {res.text[:100]}]\n")
                break

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
                    choices = data.get("choices", [{}])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    text_chunk = delta.get("content") or ""
                    thinking_chunk = delta.get("reasoning_content") or delta.get("thinking") or delta.get("reasoning") or ""

                    # 1. Dedicated reasoning token arrived
                    if thinking_chunk:
                        if show_thinking:
                            if not in_think_block:
                                in_think_block = True
                                send_acp_chunk(session_id, "> *Thinking...* ")
                            send_acp_chunk(session_id, thinking_chunk.replace("\n", "\n> "))

                    # 2. Content chunk arrived
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

                    if is_agent:
                        for tc in delta.get("tool_calls", []):
                            idx = tc.get("index", 0)
                            tc_entry = tool_calls_map.setdefault(idx, {"id": tc.get("id", ""), "type": "function", "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}})
                            if tc.get("function", {}).get("name"):
                                tc_entry["function"]["name"] = tc["function"]["name"]
                            tc_entry["function"]["arguments"] += tc.get("function", {}).get("arguments", "")

                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

        except Exception as e:
            send_acp_chunk(session_id, f"\n[Connection error: {e}]\n")
            break

        calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None

        if not calls or not is_agent:
            messages.append({"role": "assistant", "content": round_text})
            break

        messages.append({"role": "assistant", "content": round_text or None, "tool_calls": calls})

        for tc in calls:
            fname = tc.get("function", {}).get("name", "")
            raw_args = tc.get("function", {}).get("arguments") or ""
            args = core._heal_tool_args(raw_args)

            send_acp_chunk(session_id, f"\n\n*Running tool: `{fname}`...*\n")
            try:
                result = tools.run_tool(fname, args, workspace)
            except Exception as e:
                result = f"[error] tool execution failed: {e}"

            pruned_result = result if len(result) <= 2000 else result[:1500] + f"\n... [Snipped {len(result) - 1500} chars]"
            messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned_result})

    if is_agent and user_text and accumulated_ans:
        try:
            core.run_mod("ai-agent-sessions", "log-turn", safe_name, user_text, accumulated_ans)
            core.background_tpm_update(user_text, accumulated_ans, safe_name, workspace)
        except Exception:
            pass

    # Speak response out loud via Kokoro / PipeWire if TTS is enabled in .state.json
    if tts.is_tts_enabled() and accumulated_ans:
        try:
            tts.speak_response(accumulated_ans)
        except Exception:
            pass

    send_rpc_response(req_id, result={"stopReason": "end_turn"})


def main():
    default_workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    active_session_id = f"pyagent-{uuid.uuid4().hex[:8]}"

    # Background listener for tablet/phone voice dictation (.voice_pending.txt)
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
                        # Show user voice prompt in PyCode UI
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
                        # Execute prompt and stream answer
                        handle_acp_prompt(None, active_session_id, [{"type": "text", "text": text}], active_cwd)
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

        # 1. ACP Initialize Handshake
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

        # 2. ACP Authenticate Handshake
        elif method == "authenticate":
            send_rpc_response(req_id, result={})

        # 3. ACP Session Creation
        elif method in ("session/new", "createSession", "session/create"):
            active_session_id = params.get("sessionId") or f"pyagent-{uuid.uuid4().hex[:8]}"
            session_cwd = params.get("cwd") or default_workspace
            SESSION_WORKSPACES[active_session_id] = os.path.realpath(session_cwd)
            send_rpc_response(req_id, result={"sessionId": active_session_id})

        # 4. ACP Session List
        elif method in ("session/list", "listSessions"):
            active_cwd = SESSION_WORKSPACES.get(active_session_id, default_workspace)
            send_rpc_response(req_id, result={"sessions": [{"sessionId": active_session_id, "cwd": active_cwd}]})

        # 5. ACP Prompt Turn
        elif method in ("session/prompt", "prompt"):
            req_session_id = params.get("sessionId") or active_session_id
            active_cwd = SESSION_WORKSPACES.get(req_session_id, default_workspace)
            prompt_items = params.get("prompt", [])
            handle_acp_prompt(req_id, req_session_id, prompt_items, active_cwd)

        # 6. ACP Session Cancel
        elif method in ("session/cancel", "cancel"):
            send_rpc_response(req_id, result={})

        # 7. Generic Tools listing fallback
        elif method == "tools/list":
            send_rpc_response(req_id, result={"tools": tools.EDIT_TOOLS})

        elif method == "shutdown":
            send_rpc_response(req_id, result={"status": "ok"})
            break

        else:
            send_rpc_response(req_id, result={})


if __name__ == "__main__":
    main()
