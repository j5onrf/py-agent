#!/usr/bin/env python3
"""Py-Agent Official WebUI Gateway [j5onrf]
Streams 100% official llama.cpp WebUI with full TPS speed and token timing metrics.
"""

import gzip
import http.server
import json
import os
import socketserver
import sys
import urllib.parse
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
SKILLS_DIR = os.path.join(CFG_DIR, "skills")

if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_core as core
import agent_skills as skills
import agent_tools as tools
import requests

PORT = int(os.environ.get("PY_AGENT_WEB_PORT", 3000))
LLAMA_BASE_URL = os.environ.get("AI_LLAMA_BASE_URL", "http://127.0.0.1:8080")
LLAMA_SERVER_URL = f"{LLAMA_BASE_URL}/v1/chat/completions"

BASE_PROMPT_CHAT = "### Conversational Guidelines:\n- Role: Active, natural, and highly articulate conversational assistant.\n- Tone: Professional, warm, objective, and intellectually engaging.\n\n"
BASE_PROMPT_AGENT = "Active local project workspace developer agent.\nIf <context> is provided, answer directly using only its facts. Otherwise, answer normally.\n\n"


def detect_workspace_mode(workspace: str) -> tuple[bool, str, bool]:
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
    skill_target = profile_name if (is_agent and profile_name not in ("default", "init")) else "chat"
    profile_content = skills.load_skill_content(skill_target, SKILLS_DIR, CFG_DIR)

    if not is_agent:
        return profile_content or BASE_PROMPT_CHAT

    if profile_content:
        profile_content = profile_content.replace('Reply ONLY with: "Workspace loaded. Awaiting instructions."', "Execute the requested action immediately.")

    sys_prompt = profile_content or BASE_PROMPT_AGENT
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

    return sys_prompt


class OfficialWebUIProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Proxies official llama.cpp assets and explicitly decompresses gzip payloads."""
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

        # Intercept chat completions for py-agent skills & tools
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(post_data.decode("utf-8"))
        except Exception:
            body = {}

        workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
        is_agent, profile_name, _ = detect_workspace_mode(workspace)
        messages = body.get("messages", [])

        # Inject Py-Agent system prompt (Skill + Index Map)
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

        session = requests.Session()

        try:
            for _round in range(10 if is_agent else 1):
                # Preserve all original WebUI options (stream_options, timings, samplers)
                req_body = {
                    **body,
                    "messages": messages,
                    "stream": True
                }
                # Ensure timings & usage are requested so WebUI can render the metrics badge
                if "stream_options" not in req_body:
                    req_body["stream_options"] = {"include_usage": True}
                if is_agent:
                    req_body["tools"] = tools.EDIT_TOOLS

                res = session.post(LLAMA_SERVER_URL, json=req_body, headers={"Content-Type": "application/json"}, timeout=180, stream=True)
                if res.status_code != 200:
                    err_chunk = {"choices": [{"delta": {"content": f"\n[error] LLM Server HTTP {res.status_code}\n"}}]}
                    self.wfile.write(f"data: {json.dumps(err_chunk)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    break

                tool_calls_map = {}
                acc_content = []

                for line in res.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode("utf-8", errors="ignore").strip()

                    if not line_str.startswith("data:"):
                        continue
                    data_str = line_str[5:].strip()
                    if data_str == "[DONE]":
                        break

                    # Forward chunk directly to WebUI (do not send [DONE] prematurely)
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
                                tc_entry = tool_calls_map.setdefault(idx, {
                                    "id": tc.get("id", f"call_{idx}"),
                                    "type": "function",
                                    "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}
                                })
                                if tc.get("function", {}).get("name"):
                                    tc_entry["function"]["name"] = tc["function"]["name"]
                                tc_entry["function"]["arguments"] += tc.get("function", {}).get("arguments", "")
                    except Exception:
                        pass

                calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None
                ans_text = "".join(acc_content)

                if not calls or not is_agent:
                    break

                messages.append({"role": "assistant", "content": ans_text or None, "tool_calls": calls})

                for tc in calls:
                    fname = tc.get("function", {}).get("name", "")
                    raw_args = tc.get("function", {}).get("arguments", "")
                    args = core._heal_tool_args(raw_args)
                    verb = tools.TOOL_VERBS.get(fname, "working")

                    start_msg = f"\n\n> ⚙️ **{verb.title()}** • `{fname}`...\n"
                    self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': start_msg}}]})}\n\n".encode("utf-8"))
                    self.wfile.flush()

                    try:
                        result = tools.run_tool(fname, args, workspace)
                    except Exception as e:
                        result = f"[tool error] {e}"

                    pruned = result if len(result) <= 1500 else result[:1200] + "\n... [Pruned]"
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fname, "content": pruned})

            # Send final [DONE] after all tool rounds are complete
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

        except Exception as e:
            err_msg = f"\n\n[Gateway error: {e}]\n"
            try:
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': err_msg}}]})}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
        finally:
            session.close()

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
