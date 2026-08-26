#!/usr/bin/env python3
"""Py-Agent Official WebUI Gateway [j5onrf]
Streams 100% official llama.cpp WebUI with full agent tool execution,
dynamic cloud/local cascading, 0s KV cache reuse, and live reasoning controls.
"""

import gzip
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import urllib.parse
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
SKILLS_DIR = os.path.join(CFG_DIR, "skills")

if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_cloud
import agent_core as core
import agent_memories as memories
import agent_sessions as sessions
import agent_skills as skills
import agent_tools as tools
import agent_tts as tts
import requests

PORT = int(os.environ.get("PY_AGENT_WEB_PORT", 3000))
LLAMA_BASE_URL = os.environ.get("AI_LLAMA_BASE_URL", "http://127.0.0.1:8080")

_session = requests.Session()
_cached_system_prompt: str | None = None

BASE_PROMPT_CHAT = "Active, natural conversational assistant."
BASE_PROMPT_AGENT = "Active local workspace developer agent."

REASONING_EFFORT_MAP = {
    "off": 0,
    "none": 0,
    "low": 250,
    "medium": 500,
    "high": 1000,
    "max": 2000
}


def log_cli(msg: str) -> None:
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except OSError:
        pass


def detect_workspace_mode(workspace: str) -> tuple[bool, str, bool]:
    home = os.path.realpath(os.path.expanduser("~"))
    ws_real = os.path.realpath(workspace)
    cfg_file = os.path.join(workspace, ".agent", "config.json")
    inherited_skill = os.environ.get("AI_ACTIVE_SKILL")
    is_agent_env = os.environ.get("AI_IS_AGENT") == "1"

    if not is_agent_env and (ws_real == home or not os.path.exists(os.path.join(workspace, ".agent"))):
        return False, (inherited_skill or "chat"), False

    selected_profile, is_yolo = inherited_skill or "default", True
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                selected_profile = inherited_skill or data.get("profile", "default")
                is_yolo = data.get("yolo", True)
        except Exception:
            pass

    return True, selected_profile, is_yolo


def assemble_system_prompt(workspace: str, is_agent: bool, profile_name: str) -> str:
    global _cached_system_prompt
    if _cached_system_prompt:
        return _cached_system_prompt

    if not is_agent:
        clean_name = profile_name if (profile_name and profile_name != "default") else "chat"
        skill_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
        _cached_system_prompt = skill_content or BASE_PROMPT_CHAT
        return _cached_system_prompt

    clean_name = profile_name if profile_name not in ("default", "init") else "init"
    profile_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
    
    if profile_content:
        profile_content = profile_content.replace('Reply ONLY with: "Workspace loaded. Awaiting instructions."', "Execute the requested action immediately.")

    base_prompt = profile_content or BASE_PROMPT_AGENT

    agent_dir = os.path.join(workspace, ".agent")
    map_content = ""
    if os.path.exists(agent_dir):
        for f in os.listdir(agent_dir):
            if f.startswith("index-map-") and f.endswith(".txt"):
                try:
                    with open(os.path.join(agent_dir, f), "r", encoding="utf-8", errors="ignore") as mf:
                        map_content = mf.read().strip()
                        break
                except OSError:
                    pass

    if map_content:
        base_prompt += f"\n\n### CODESPACE MAP:\n{map_content}"

    # In-memory TPM fact retrieval if memory is enabled
    safe_name = core.workspace_safe_name(workspace)
    if core.get_state("memory_active", False):
        try:
            tpm_facts = memories.tpm_get(safe_name)
            if tpm_facts:
                base_prompt += f"\n\n{tpm_facts}"
        except Exception:
            pass

    tools_header = (
        f"### ACTIVE DEVELOPER AGENT MODE:\n"
        f"Workspace Root: {workspace}\n"
        f"CRITICAL DIRECTIVE: Do NOT output conversational chatter or explain what you will do. "
        f"You MUST immediately execute actions by calling available tools (run_command, read_file, write_file, list_dir, read_symbol).\n\n"
    )

    _cached_system_prompt = tools_header + base_prompt
    return _cached_system_prompt


class OfficialWebUIProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        target_url = f"{LLAMA_BASE_URL}{self.path}"
        try:
            resp = requests.get(target_url, timeout=8)
            body = resp.content

            if body.startswith(b"\x1f\x8b"):
                try:
                    body = gzip.decompress(body)
                except Exception:
                    pass

            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "content-encoding", "connection", "content-length"):
                    self.send_header(k, v)

            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self.send_error(502, f"Could not connect to llama-server at {LLAMA_BASE_URL}.")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/v1/chat/completions", "/chat/completions"):
            target_url = f"{LLAMA_BASE_URL}{self.path}"
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                resp = requests.post(target_url, data=post_data, headers={"Content-Type": self.headers.get("Content-Type", "application/json")}, timeout=30)
                body = resp.content
                if body.startswith(b"\x1f\x8b"):
                    try:
                        body = gzip.decompress(body)
                    except Exception:
                        pass
                self.send_response(resp.status_code)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "content-encoding", "connection", "content-length"):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(502, str(e))
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(post_data.decode("utf-8"))
        except Exception:
            body = {}

        workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
        is_agent, profile_name, _ = detect_workspace_mode(workspace)
        messages = body.get("messages", [])

        user_text = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
        raw_query = user_text.strip() if isinstance(user_text, str) else ""

        # Chat slash command handler for /t and /thinking in WebUI
        if raw_query.startswith(("/t", "/thinking")):
            parts = raw_query.split()
            st = core.get_state()
            curr_active = st.get("reasoning_active", False)
            curr_budget = st.get("reasoning_budget", 500)

            if len(parts) > 1:
                sub = parts[1].lower()
                if sub in ("off", "hide", "mute", "disable", "0"):
                    core.save_state("reasoning_active", False)
                    core.save_state("reasoning_budget", 0)
                    resp_msg = "✔ Deep reasoning **disabled**."
                elif sub in ("on", "enable", "show"):
                    core.save_state("reasoning_active", True)
                    b_val = curr_budget if curr_budget > 0 else 500
                    core.save_state("reasoning_budget", b_val)
                    resp_msg = f"✔ Deep reasoning **enabled** (budget: {b_val} tokens)."
                elif sub.isdigit():
                    b_val = max(0, int(sub))
                    core.save_state("reasoning_active", b_val > 0)
                    core.save_state("reasoning_budget", b_val)
                    resp_msg = f"✔ Deep reasoning set to **{b_val} tokens**." if b_val > 0 else "✔ Deep reasoning **disabled**."
                else:
                    new_state = not curr_active
                    core.save_state("reasoning_active", new_state)
                    resp_msg = f"✔ Deep reasoning **{'enabled' if new_state else 'disabled'}** (budget: {curr_budget} tokens)."
            else:
                new_state = not curr_active
                core.save_state("reasoning_active", new_state)
                b_val = curr_budget if curr_budget > 0 else 500
                core.save_state("reasoning_budget", b_val)
                resp_msg = f"✔ Deep reasoning **{'enabled' if new_state else 'disabled'}** (budget: {b_val} tokens)."

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            chunk = {"choices": [{"delta": {"content": resp_msg}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            log_cli(f"\033[1;36m[webui]\033[0m \033[1;33m{resp_msg}\033[0m")
            return

        sys_context = assemble_system_prompt(workspace, is_agent, profile_name)
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": sys_context})
        else:
            messages[0]["content"] = sys_context

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        safe_name = core.workspace_safe_name(workspace)
        accumulated_ans = ""

        if user_text:
            log_cli(f"\033[1;36m[webui]\033[0m \033[1;32m❯\033[0m \"\033[37m{str(user_text)[:60]}\033[0m\"")

        # Map WebUI dropdown options or inherit CLI state
        web_effort = body.get("reasoning_effort") or (body.get("chat_template_kwargs", {}) or {}).get("reasoning_effort")
        st = core.get_state()

        if web_effort and str(web_effort).lower() in REASONING_EFFORT_MAP:
            reasoning_budget = REASONING_EFFORT_MAP[str(web_effort).lower()]
            reasoning_active = reasoning_budget > 0
        else:
            reasoning_active = st.get("reasoning_active", False)
            reasoning_budget = st.get("reasoning_budget", 500) if reasoning_active else 0

        enable_think = reasoning_active and reasoning_budget > 0
        think_kwargs = {
            "thinking_budget_tokens": reasoning_budget if enable_think else 0,
            "reasoning_budget": reasoning_budget if enable_think else 0,
            "chat_template_kwargs": {"enable_thinking": enable_think}
        }

        configs = agent_cloud.get_active_configs(messages) if hasattr(agent_cloud, "get_active_configs") else []
        if not configs:
            configs = [(f"{LLAMA_BASE_URL}/v1/chat/completions", {}, {"model": "local-model", **think_kwargs}, 180)]

        url, headers, base_body, timeout = configs[0]
        is_local = "localhost" in url or "127.0.0.1" in url or base_body.get("model") == "local-model"
        os.environ["AI_CONFIRM_GATES"] = "0"

        try:
            for _round in range(10 if is_agent else 1):
                req_body = {
                    **body,
                    **base_body,
                    "messages": messages,
                    "stream": True
                }
                if is_local:
                    req_body.update(think_kwargs)
                if "stream_options" not in req_body:
                    req_body["stream_options"] = {"include_usage": True}
                if is_agent:
                    req_body["tools"] = tools.EDIT_TOOLS

                res = _session.post(url, json=req_body, headers={"Content-Type": "application/json", **headers}, timeout=timeout, stream=True)
                if res.status_code != 200:
                    err_chunk = {"choices": [{"delta": {"content": f"\n[error] LLM Server HTTP {res.status_code}\n"}}]}
                    self.wfile.write(f"data: {json.dumps(err_chunk)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    break

                tool_calls_map = {}
                acc_content = []

                for line in res.iter_lines(chunk_size=1):
                    if not line:
                        continue
                    line_str = line.decode("utf-8", errors="ignore").strip()

                    if not line_str.startswith("data:"):
                        continue
                    data_str = line_str[5:].strip()
                    if data_str == "[DONE]":
                        break

                    self.wfile.write(line + b"\n\n")
                    self.wfile.flush()

                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [{}])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "") or ""
                            if content:
                                acc_content.append(content)

                            for tc in delta.get("tool_calls", []):
                                idx = tc.get("index", 0)
                                call_id = tc.get("id") or f"call_{_round}_{idx}"
                                tc_entry = tool_calls_map.setdefault(idx, {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}
                                })
                                if tc.get("id"):
                                    tc_entry["id"] = tc["id"]
                                if tc.get("function", {}).get("name"):
                                    tc_entry["function"]["name"] = tc["function"]["name"]
                                tc_entry["function"]["arguments"] += tc.get("function", {}).get("arguments", "")
                    except Exception:
                        pass

                calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None
                ans_text = "".join(acc_content)

                if not calls or not is_agent:
                    accumulated_ans = ans_text
                    break

                for idx, tc in enumerate(calls):
                    if not tc.get("id"):
                        tc["id"] = f"call_{_round}_{idx}"

                messages.append({"role": "assistant", "content": ans_text or None, "tool_calls": calls})

                for tc in calls:
                    fname = tc.get("function", {}).get("name", "")
                    raw_args = tc.get("function", {}).get("arguments", "")
                    args = core._heal_tool_args(raw_args)
                    verb = tools.TOOL_VERBS.get(fname, "working")
                    brief = str(args.get("path") or args.get("symbol") or args.get("command") or "")[:40]
                    cid = tc.get("id") or f"call_{_round}_0"

                    start_msg = f"\n\n> ⚙️ **{verb.title()}** • `{fname}`...\n"
                    self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': start_msg}}]})}\n\n".encode("utf-8"))
                    self.wfile.flush()

                    log_cli(f"  \033[2m∗ {verb.title()} • \033[1;36m{fname}\033[0m \033[3m{brief}\033[0m")

                    try:
                        result = tools.run_tool(fname, args, workspace, confirm_gate_fn=lambda r: True)
                    except Exception as e:
                        result = f"[tool error] {e}"

                    pruned = result if len(result) <= 2000 else result[:1500] + f"\n... [Snipped {len(result) - 1500} chars]"
                    messages.append({"role": "tool", "tool_call_id": cid, "name": fname, "content": pruned})

            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

            if is_agent and user_text and accumulated_ans:
                try:
                    sessions.log_turn(safe_name, str(user_text), accumulated_ans)
                    if st.get("memory_active", False):
                        threading.Thread(target=core.background_tpm_update, args=(str(user_text), accumulated_ans, safe_name, workspace), daemon=True).start()
                except Exception:
                    pass

            if tts.is_tts_enabled() and accumulated_ans:
                try:
                    tts.speak_response(accumulated_ans)
                except Exception:
                    pass

        except Exception as e:
            err_msg = f"\n\n[Gateway error: {e}]\n"
            try:
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': err_msg}}]})}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
        finally:
            pass

    def log_message(self, format, *args):
        return


class ThreadedProxyServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    ws = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    print(f"\033[1;32m[py-agent] Official llama.cpp WebUI Gateway active at http://127.0.0.1:{PORT}\033[0m")
    server = ThreadedProxyServer(("127.0.0.1", PORT), OfficialWebUIProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
