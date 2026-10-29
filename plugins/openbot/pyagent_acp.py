#!/usr/bin/env python3
"""
Py-Agent Native ACP (Agent Client Protocol) Server for OpenBot
- Real-time SSE token streaming (sub-second first token)
- Native OpenBot collapsible thinking drawer (agent_thought_chunk)
- Native OpenBot tool step cards (tool_call & tool_call_update)
- Zero blank screens & zero duplicate text
"""

import sys
import os
import json
import uuid
import re
import subprocess
import requests

REAL_STDIN = sys.stdin
REAL_STDOUT = sys.stdout

REAL_STDIN.reconfigure(encoding='utf-8')
REAL_STDOUT.reconfigure(encoding='utf-8', line_buffering=True)

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_tools as tools
import agent_cloud as cloud

current_workspace = os.getcwd()
sessions = {}


def send_rpc(msg: dict):
    payload = json.dumps(msg) + "\n"
    REAL_STDOUT.write(payload)
    REAL_STDOUT.flush()


def stream_thought(session_id: str, text: str):
    """Triggers OpenBot's native collapsible thinking drawer."""
    if not text:
        return
    send_rpc({
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": "text", "text": text}
            }
        }
    })


def stream_chunk(session_id: str, text: str):
    """Renders directly in OpenBot's main chat window."""
    if not text:
        return
    send_rpc({
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text}
            }
        }
    })


def emit_tool_start(session_id: str, call_id: str, title: str):
    """Creates a native OpenBot tool step card."""
    send_rpc({
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": call_id,
                "title": title,
                "status": "in_progress"
            }
        }
    })


def emit_tool_done(session_id: str, call_id: str, output: str):
    """Marks the OpenBot tool step card as completed."""
    send_rpc({
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": call_id,
                "status": "completed",
                "content": [{"type": "text", "text": output}]
            }
        }
    })


def parse_tool_calls(text: str) -> list[tuple[str, dict]]:
    calls = []
    xml_matches = re.findall(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
    for block in xml_matches:
        fn_m = re.match(r"^\s*([a-zA-Z0-9_\-]+)", block)
        if not fn_m:
            continue
        fn_name = fn_m.group(1).strip()
        args = {}
        for k, v in re.findall(r"<arg_key>(.*?)</arg_key>\s*<arg_value>(.*?)</arg_value>", block, re.DOTALL):
            args[k.strip()] = v.strip()

        if not args:
            val_m = re.search(r"<arg_value>(.*?)</arg_value>", block, re.DOTALL)
            if val_m:
                args["command" if fn_name in ("subprocess", "run_command", "bash") else "path"] = val_m.group(1).strip()

        calls.append((fn_name, args))
    return calls


def execute_tool(fn_name: str, args: dict, cwd: str) -> tuple[str, str]:
    """Executes py-agent native tools directly on the filesystem."""
    fn = fn_name.lower()

    if fn in ("write_file", "write", "create_file"):
        path = args.get("path") or args.get("file") or "output.txt"
        content = args.get("content") or args.get("text") or ""
        target = os.path.join(cwd, path) if not os.path.isabs(path) else path
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return f"write_file `{path}`", f"Successfully wrote {len(content)} chars to {path}."
        except Exception as e:
            return f"write_file `{path}`", f"Error creating file: {e}"

    if fn in ("run_command", "subprocess", "bash", "shell", "exec"):
        cmd = args.get("command") or args.get("cmd") or args.get("arg", "")
        try:
            res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30)
            out = (res.stdout + res.stderr).strip() or "OK (exit 0)"
            return f"run `{cmd}`", out
        except Exception as e:
            return f"run `{cmd}`", f"Execution error: {e}"

    if fn in ("read_file", "read"):
        path = args.get("path") or args.get("file") or ""
        target = os.path.join(cwd, path) if not os.path.isabs(path) else path
        try:
            with open(target, "r", encoding="utf-8") as f:
                return f"read_file `{path}`", f.read()
        except Exception as e:
            return f"read_file `{path}`", f"Error reading file: {e}"

    if fn in ("list_dir", "ls", "list_files", "dir"):
        path = args.get("path") or "."
        target = os.path.join(cwd, path) if not os.path.isabs(path) else path
        try:
            items = os.listdir(target)
            return f"list_dir `{path}`", "\n".join(items) if items else "(empty directory)"
        except Exception as e:
            return f"list_dir `{path}`", f"Error listing directory: {e}"

    cmd = args.get("command") or str(args)
    try:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=15)
        return f"run `{cmd}`", (res.stdout + res.stderr).strip() or "OK"
    except Exception as e:
        return f"run `{cmd}`", f"Execution error: {e}"


def run_pyagent_turn(session_id: str, user_prompt: str):
    global current_workspace

    # Read registered launch mode (chat vs agent) from py-agent state
    is_agent = False
    saved_ws = None
    try:
        import agent_core as core
        is_agent = core.get_state("openbot_is_agent", False)
        saved_ws = core.get_state("openbot_workspace", None)
    except Exception:
        pass

    if saved_ws and os.path.isdir(saved_ws):
        current_workspace = saved_ws

    os.makedirs(current_workspace, exist_ok=True)
    os.chdir(current_workspace)
    os.environ["AI_WORKSPACE_PATH"] = current_workspace
    os.environ["AI_CONFIRM_GATES"] = "0"

    # Profile selection: Agent vs Pure Chat
    if is_agent:
        prof_path = os.path.join(CFG_DIR, "skills", "profiles", "lingtiny.md")
        sys_prompt = "ROLE: Autonomous Systems & Software Engineer.\nDIRECTIVES: Use tools directly to solve tasks."
        if os.path.isfile(prof_path):
            try:
                with open(prof_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.startswith("---"):
                    sys_prompt = content.split("---", 2)[2].strip()
            except Exception:
                pass
    else:
        sys_prompt = "ROLE: Helpful AI Assistant.\nDIRECTIVES: Answer conversationally in markdown. Output code directly in markdown code blocks. Do not call tools."

    history = sessions.get(session_id, [])
    if not history:
        history.append({"role": "system", "content": sys_prompt})
    history.append({"role": "user", "content": user_prompt})

    active_cfgs = cloud.get_active_configs(history)
    if active_cfgs:
        url, headers, body, timeout = active_cfgs[0]
    else:
        url = "http://127.0.0.1:8080/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        body = {"model": "local-model", "messages": history, "stream": True}
        timeout = 180

    body["stream"] = True

    max_turns = 4 if is_agent else 1

    for turn_idx in range(max_turns):
        try:
            resp = requests.post(url, headers=headers, json=body, stream=True, timeout=timeout)
            full_reply = ""
            in_thinking = False
            token_buffer = ""

            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_str)
                        choice = chunk_json.get("choices", [{}])[0]
                        delta = choice.get("delta", {})

                        # 1. Native reasoning_content from models (DeepSeek / Qwen / Ling)
                        reasoning = delta.get("reasoning_content", "") or delta.get("thought", "")
                        if reasoning:
                            stream_thought(session_id, reasoning)

                        content = delta.get("content", "")
                        if content:
                            full_reply += content
                            token_buffer += content

                            # 2. Parse <think> tags in the stream
                            if "<think>" in token_buffer:
                                in_thinking = True
                                pre, _, post = token_buffer.partition("<think>")
                                if pre:
                                    stream_chunk(session_id, pre)
                                token_buffer = post

                            if "</think>" in token_buffer:
                                in_thinking = False
                                thought_part, _, post = token_buffer.partition("</think>")
                                if thought_part:
                                    stream_thought(session_id, thought_part)
                                token_buffer = post

                            if in_thinking:
                                stream_thought(session_id, token_buffer)
                                token_buffer = ""
                            else:
                                # Stream regular code and text immediately (suppress raw tool call tags)
                                if "<tool_call>" not in full_reply:
                                    stream_chunk(session_id, token_buffer)
                                    token_buffer = ""

                    except Exception:
                        pass

            # Flush any remaining text in the buffer
            if token_buffer and not in_thinking and "<tool_call>" not in full_reply:
                stream_chunk(session_id, token_buffer)

            history.append({"role": "assistant", "content": full_reply})

            # Handle tools if in agent mode
            if is_agent and "<tool_call>" in full_reply:
                calls = parse_tool_calls(full_reply)
                if calls:
                    tool_results_text = ""
                    for fn_name, args in calls:
                        tool_id = f"tool_{uuid.uuid4().hex[:6]}"
                        label, out = execute_tool(fn_name, args, current_workspace)
                        emit_tool_start(session_id, tool_id, label)
                        emit_tool_done(session_id, tool_id, out)
                        tool_results_text += f"[{fn_name} result]:\n{out}\n\n"

                    # Feed results back to model for Turn 2
                    history.append({
                        "role": "user",
                        "content": f"Tool execution output:\n```\n{tool_results_text.strip()}\n```\nAnalyze the result and complete the task."
                    })
                    body["messages"] = history
                    continue

            break

        except Exception as e:
            stream_chunk(session_id, f"\nExecution error: {e}\n")
            break

    sessions[session_id] = history


def main():
    global current_workspace
    for line in REAL_STDIN:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            send_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": 1,
                    "agentInfo": {"name": "py-agent", "version": "1.0.0"},
                    "agentCapabilities": {
                        "loadSession": False,
                        "promptCapabilities": {"embeddedContext": True}
                    }
                }
            })

        elif method == "session/new":
            params = req.get("params", {})
            cwd = params.get("cwd")
            if cwd and os.path.isdir(cwd):
                current_workspace = cwd
            sess_id = f"sess_{uuid.uuid4().hex[:8]}"
            sessions[sess_id] = []
            send_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"sessionId": sess_id}
            })

        elif method == "session/prompt":
            params = req.get("params", {})
            sess_id = params.get("sessionId")
            prompt_blocks = params.get("prompt", [])
            user_text = ""
            for block in prompt_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    user_text += block.get("text", "")
                elif isinstance(block, str):
                    user_text += block

            run_pyagent_turn(sess_id, user_text)

            send_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"stopReason": "end_turn"}
            })

        elif method == "session/cancel":
            continue

        elif msg_id is not None:
            send_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": "Method not found"}
            })


if __name__ == "__main__":
    main()
