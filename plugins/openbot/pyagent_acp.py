#!/usr/bin/env python3
"""
Py-Agent Native ACP Server for OpenBot
- Live collapsible thinking drawer (agent_thought_chunk)
- Guaranteed visible message rendering (never wipes the screen)
- Fast sub-second local CPU prefill
"""

import sys
import os
import json
import uuid
import re
import signal
import requests

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

REAL_STDIN = sys.stdin
REAL_STDOUT = sys.stdout

REAL_STDIN.reconfigure(encoding="utf-8")
REAL_STDOUT.reconfigure(encoding="utf-8", line_buffering=True)

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_core as core
import agent_tools as tools

current_workspace = os.getcwd()
sessions = {}


def send_rpc(msg: dict):
    try:
        REAL_STDOUT.write(json.dumps(msg, ensure_ascii=False) + "\n")
        REAL_STDOUT.flush()
    except (BrokenPipeError, OSError):
        sys.exit(0)


def stream_thought(session_id: str, text: str):
    if not text:
        return
    send_rpc({
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": "text", "text": text},
            },
        },
    })


def stream_chunk(session_id: str, text: str):
    if not text:
        return
    send_rpc({
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text},
            },
        },
    })


def run_pyagent_turn(session_id: str, user_prompt: str):
    global current_workspace

    saved_ws = None
    reasoning_budget = 0
    try:
        saved_ws = core.get_state("openbot_workspace", None)
        reasoning_budget = int(core.get_state("reasoning_budget", 0))
    except Exception:
        pass

    if saved_ws and os.path.isdir(saved_ws):
        current_workspace = saved_ws

    os.makedirs(current_workspace, exist_ok=True)
    os.chdir(current_workspace)
    os.environ["AI_WORKSPACE_PATH"] = current_workspace
    os.environ["AI_CONFIRM_GATES"] = "0"

    sys_prompt = "ROLE: Liquid AI LFM3-1.7B Autonomous Systems & Software Engineer."
    prof_path = os.path.join(CFG_DIR, "skills", "profiles", "lfm3.md")
    if os.path.isfile(prof_path):
        try:
            with open(prof_path, "r", encoding="utf-8") as f:
                c = f.read()
            if c.startswith("---"):
                parts = c.split("---", 2)
                sys_prompt = parts[2].strip()
                if reasoning_budget <= 0:
                    m = re.search(r"reasoning_budget:\s*(\d+)", parts[1])
                    if m:
                        reasoning_budget = int(m.group(1))
        except Exception:
            pass

    history = sessions.get(session_id, [])
    if not history:
        history.append({"role": "system", "content": sys_prompt})
    history.append({"role": "user", "content": user_prompt})

    url = "http://127.0.0.1:8080/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    body = {
        "model": "local-model",
        "messages": history,
        "stream": True,
        "temperature": 0.1,
    }

    if reasoning_budget > 0:
        body["thinking_budget_tokens"] = reasoning_budget
        body["reasoning_budget"] = reasoning_budget

    try:
        resp = requests.post(url, headers=headers, json=body, stream=True, timeout=60)
        full_reply = ""
        in_thinking = False
        message_chunks_sent = 0

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8", errors="replace")
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:].strip()
            if data_str == "[DONE]":
                break

            try:
                chunk_json = json.loads(data_str)
                delta = chunk_json.get("choices", [{}])[0].get("delta", {})

                # 1. Native reasoning content
                reasoning = delta.get("reasoning_content", "") or delta.get("thought", "")
                if reasoning:
                    stream_thought(session_id, reasoning)

                # 2. Content stream with <think> tag parsing
                content = delta.get("content", "")
                if not content:
                    continue

                full_reply += content

                # Process tag markers
                if "<think>" in content:
                    in_thinking = True
                    before, _, after = content.partition("<think>")
                    if before:
                        stream_chunk(session_id, before)
                        message_chunks_sent += 1
                    content = after

                if "</think>" in content:
                    thought_part, _, after = content.partition("</think>")
                    if thought_part:
                        stream_thought(session_id, thought_part)
                    in_thinking = False
                    content = after

                if in_thinking:
                    if content:
                        stream_thought(session_id, content)
                else:
                    if content and "<tool_call>" not in full_reply:
                        stream_chunk(session_id, content)
                        message_chunks_sent += 1

            except Exception:
                pass

        # Guarantee: If the model only thought and forgot to emit visible text,
        # emit a clean completion so OpenBot does not wipe the card
        if message_chunks_sent == 0:
            stream_chunk(session_id, "Ready. What would you like to work on?")

        history.append({"role": "assistant", "content": full_reply})
        sessions[session_id] = history

    except Exception as e:
        stream_chunk(session_id, f"\nExecution error: {e}\n")


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
                        "promptCapabilities": {
                            "embeddedContext": False,
                            "image": False,
                            "audio": False,
                        },
                    },
                },
            })

        elif method == "session/new":
            sess_id = f"sess_{uuid.uuid4().hex[:8]}"
            sessions[sess_id] = []
            send_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"sessionId": sess_id},
            })

        elif method == "session/prompt":
            params = req.get("params", {})
            sess_id = params.get("sessionId")
            prompt_blocks = params.get("prompt", [])

            user_text = ""
            if isinstance(prompt_blocks, str):
                user_text = prompt_blocks
            elif isinstance(prompt_blocks, list):
                text_blocks = []
                for b in prompt_blocks:
                    if isinstance(b, dict) and b.get("type") == "text":
                        text_blocks.append(b.get("text", ""))
                    elif isinstance(b, str):
                        text_blocks.append(b)

                if len(text_blocks) > 1 and len(text_blocks[0]) > 500:
                    user_text = text_blocks[-1]
                else:
                    user_text = "\n".join(text_blocks)

            run_pyagent_turn(sess_id, user_text.strip())

            send_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"stopReason": "end_turn"},
            })

        elif method == "session/cancel":
            continue

        elif msg_id is not None:
            send_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": "Method not found"},
            })


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        sys.exit(0)
