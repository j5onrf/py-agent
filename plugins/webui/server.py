#!/usr/bin/env python3
"""Py-Agent Official WebUI Gateway [Hardened Production Ready]
Streams official llama.cpp WebUI with dynamic CLI-state sync (Reasoning, Vision, Grounding, OKF Memory, Adapters).
"""

import gzip
import http.server
import json
import os
import re
import socketserver
import sys
import urllib.parse

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
SKILLS_DIR = os.path.join(CFG_DIR, "skills")

if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_adapters as adapters
import agent_core as core
import agent_ipython as ipython
import agent_memories as memories
import agent_sessions as sessions
import agent_skills as skills
import agent_tools as tools
import agent_tts as tts
import requests

try:
    PORT = int(os.environ.get("PY_AGENT_WEB_PORT", "3000"))
except ValueError:
    PORT = 3000

LLAMA_BASE_URL = os.environ.get("AI_LLAMA_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
LLAMA_SERVER_URL = f"{LLAMA_BASE_URL}/v1/chat/completions"
WEB_TOKEN = os.environ.get("PY_AGENT_WEB_TOKEN", "").strip()

BASE_PROMPT_CHAT = "Active, natural conversational assistant."
BASE_PROMPT_AGENT = "Active local workspace developer agent."
RE_THINK_BLOCK = re.compile(
    r"<think(?:ing)?>[\s\S]*?(?:</think(?:ing)?>|$)|<thought>[\s\S]*?(?:</thought>|$)",
    re.DOTALL | re.IGNORECASE,
)
MAX_PAYLOAD_BYTES = 50 * 1024 * 1024  # 50 MB cap


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
            sys.stderr.write(f"[webui] warning: failed reading config {cfg_file}: {e}\n")

    return True, selected_profile, is_yolo


def make_confirm_gate(workspace: str, is_yolo: bool):
    """Scoped confirmation gate for non-interactive WebUI requests."""
    def confirm_gate(prompt_or_reason: str) -> bool:
        if not is_yolo:
            sys.stderr.write(
                f"[webui security] Blocked tool execution (workspace yolo=False): {prompt_or_reason}\n"
            )
            return False

        # In YOLO mode, standard edits within workspace boundaries are auto-approved by agent_tools.
        # If this gate is triggered, it is an out-of-bounds path or destructive command (sudo, pacman, etc.).
        sys.stderr.write(
            f"[webui security] Blocked zero-trust security boundary violation: {prompt_or_reason}\n"
        )
        return False

    return confirm_gate


def assemble_system_prompt(workspace: str, is_agent: bool, profile_name: str) -> str:
    use_gnd = core.get_state("grounding_active", False)

    if not is_agent:
        clean_name = profile_name if profile_name else "chat"
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

    tools_header = (
        f"### ACTIVE DEVELOPER AGENT MODE:\n"
        f"Workspace Root: {workspace}\n"
        f"CRITICAL DIRECTIVES:\n"
        f"1. Immediately execute actions using available tools.\n"
        f"2. Use relative paths from Workspace Root. Avoid repeating identical queries.\n\n"
    )

    sys_prompt = tools_header + (profile_content or BASE_PROMPT_AGENT)
    sys_prompt += f"\n\n### ACTIVE PROJECT WORKSPACE:\nYour active project root directory is: {workspace}\n"

    agent_dir = os.path.join(workspace, ".agent")
    use_map = "-map" in profile_name.lower()
    cfg_path = os.path.join(agent_dir, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as cf:
                use_map = json.load(cf).get("map", use_map)
        except Exception as e:
            sys.stderr.write(f"[webui] warning: failed reading map config {cfg_path}: {e}\n")

    if use_map and os.path.isdir(agent_dir):
        try:
            for f in os.listdir(agent_dir):
                if f.startswith("index-map-") and f.endswith(".txt"):
                    try:
                        with open(os.path.join(agent_dir, f), "r", encoding="utf-8", errors="ignore") as mf:
                            sys_prompt += f"### CODESPACE MAP:\n{mf.read().strip()}\n\n"
                            break
                    except OSError:
                        pass
        except OSError as e:
            sys.stderr.write(f"[webui] warning: unable to list {agent_dir}: {e}\n")

    # Open Knowledge Format (OKF) Git-native memory injection
    if core.get_state("memory_active", False):
        try:
            mem_ctx = memories.get_memory_context(workspace)
            if mem_ctx:
                sys_prompt += f"\n{mem_ctx}\n"
        except Exception as e:
            sys.stderr.write(f"[webui] warning: memory injection error: {e}\n")

    if use_gnd:
        sys_prompt += "\n\nCRITICAL GROUNDING DIRECTIVE: When tool results from 'web_search' are returned, you MUST base your final answer strictly on the verified live tool data."

    return sys_prompt


class OfficialWebUIProxyHandler(http.server.BaseHTTPRequestHandler):
    def _is_origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urllib.parse.urlparse(origin)
        return parsed.hostname in ("127.0.0.1", "localhost", "::1")

    def _is_host_allowed(self) -> bool:
        if os.environ.get("PY_AGENT_ALLOW_REMOTE") == "1":
            return True
        host_header = self.headers.get("Host", "")
        if not host_header:
            return True
        host = host_header.split(":")[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1")

    def _check_auth(self) -> bool:
        if not WEB_TOKEN:
            return True
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and auth_header[7:].strip() == WEB_TOKEN:
            return True
        parsed = urllib.parse.urlparse(self.path)
        q_params = urllib.parse.parse_qs(parsed.query)
        if q_params.get("token", [""])[0] == WEB_TOKEN:
            return True
        return False

    def _set_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and self._is_origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
        elif not origin:
            self.send_header("Access-Control-Allow-Origin", "*")

    def do_OPTIONS(self):
        if not self._is_host_allowed() or not self._is_origin_allowed():
            self.send_error(403, "Forbidden Origin/Host")
            return
        self.send_response(204)
        self._set_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if not self._is_host_allowed() or not self._is_origin_allowed():
            self.send_error(403, "Forbidden: Cross-origin or invalid host request rejected.")
            return

        if not self._check_auth():
            self.send_error(401, "Unauthorized: Valid access token required.")
            return

        target_url = f"{LLAMA_BASE_URL}{self.path}"
        try:
            with requests.get(target_url, timeout=15) as resp:
                body = resp.content

                if body.startswith(b"\x1f\x8b"):
                    try:
                        body = gzip.decompress(body)
                    except Exception:
                        pass

                # Sync dynamic properties (Reasoning on/off + dynamic Vision support)
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path.rstrip("/") in ("/props", "/v1/props"):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        has_clip = bool(data.get("has_clip_model") or os.environ.get("GEMINI_API_KEY"))
                        data["has_clip_model"] = has_clip
                        modalities = data.get("modalities", {})
                        if isinstance(modalities, dict):
                            modalities["vision"] = has_clip
                            modalities["audio"] = False
                            data["modalities"] = modalities
                        data["chat_template_kwargs"] = data.get("chat_template_kwargs", {})
                        data["chat_template_kwargs"]["supports_vision"] = has_clip
                        data["chat_template_kwargs"]["enable_thinking"] = core.get_state("reasoning_active", False)
                        body = json.dumps(data).encode("utf-8")
                    except Exception as e:
                        sys.stderr.write(f"[webui] warning: props sync error: {e}\n")

                self.send_response(resp.status_code)
                hop_by_hop = {
                    "transfer-encoding",
                    "content-encoding",
                    "connection",
                    "content-length",
                    "keep-alive",
                    "proxy-authenticate",
                    "proxy-authorization",
                    "te",
                    "trailers",
                    "upgrade",
                }
                for k, v in resp.headers.items():
                    if k.lower() not in hop_by_hop:
                        self.send_header(k, v)

                self.send_header("Content-Length", str(len(body)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self.send_error(502, f"Could not connect to llama-server at {LLAMA_BASE_URL}: {e}")

    def do_POST(self):
        if not self._is_host_allowed() or not self._is_origin_allowed():
            self.send_error(403, "Forbidden: Cross-origin or invalid host request rejected.")
            return

        if not self._check_auth():
            self.send_error(401, "Unauthorized: Valid access token required.")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self.send_error(400, "Invalid Content-Length.")
            return

        if content_length < 0:
            self.send_error(400, "Invalid Content-Length.")
            return
        if content_length > MAX_PAYLOAD_BYTES:
            self.send_error(413, f"Payload Too Large (Max: {MAX_PAYLOAD_BYTES} bytes).")
            return

        parsed = urllib.parse.urlparse(self.path)
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        if parsed.path not in ("/v1/chat/completions", "/chat/completions"):
            target_url = f"{LLAMA_BASE_URL}{self.path}"
            try:
                with requests.post(
                    target_url,
                    data=post_data,
                    headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
                    timeout=30,
                ) as resp:
                    body = resp.content
                    if body.startswith(b"\x1f\x8b"):
                        try:
                            body = gzip.decompress(body)
                        except Exception:
                            pass
                    self.send_response(resp.status_code)
                    hop_by_hop = {
                        "transfer-encoding",
                        "content-encoding",
                        "connection",
                        "content-length",
                        "keep-alive",
                        "proxy-authenticate",
                        "proxy-authorization",
                        "te",
                        "trailers",
                        "upgrade",
                    }
                    for k, v in resp.headers.items():
                        if k.lower() not in hop_by_hop:
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(body)))
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as e:
                self.send_error(502, f"Gateway upstream POST failure: {e}")
            return

        try:
            body = json.loads(post_data.decode("utf-8"))
        except Exception:
            body = {}

        workspace = os.path.realpath(os.environ.get("AI_WORKSPACE_PATH", os.getcwd()))
        is_agent, profile_name, is_yolo = detect_workspace_mode(workspace)
        st = core.get_state()
        use_gnd = st.get("grounding_active", False)
        adapters_on = st.get("adapters_active", False)
        reasoning_active = st.get("reasoning_active", False)

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            messages = []

        # Preprocess multimodal image payloads via Gemini Flash Lite if enabled
        messages = core.preprocess_multimodal_messages(messages)

        # Inject Py-Agent system prompt
        sys_context = assemble_system_prompt(workspace, is_agent, profile_name)
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": sys_context})
        else:
            messages[0]["content"] = sys_context

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._set_cors_headers()
        self.end_headers()

        session = requests.Session()
        safe_name = core.workspace_safe_name(workspace)

        raw_user_content = next(
            (m.get("content") for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "user"),
            "",
        )
        if isinstance(raw_user_content, list):
            user_text = " ".join(
                p.get("text", "") for p in raw_user_content if isinstance(p, dict) and p.get("type") == "text"
            )
        else:
            user_text = str(raw_user_content or "")

        accumulated_ans = ""
        confirm_gate = make_confirm_gate(workspace, is_yolo)

        try:
            for _round in range(10 if (is_agent or use_gnd) else 1):
                req_body = {**body, "messages": messages, "stream": True}
                if "stream_options" not in req_body:
                    req_body["stream_options"] = {"include_usage": True}

                req_body.setdefault("chat_template_kwargs", {})["enable_thinking"] = reasoning_active

                active_tools = []
                if is_agent:
                    is_py = (
                        "-py" in profile_name.lower()
                        or "py-" in profile_name.lower()
                        or st.get("ipython_mode", False)
                    )
                    active_tools = list(ipython.IPYTHON_TOOL) if (is_py and ipython) else list(tools.EDIT_TOOLS)
                if use_gnd and hasattr(tools, "WEB_TOOL"):
                    active_tools.append(tools.WEB_TOOL)

                if active_tools:
                    req_body["tools"] = active_tools
                else:
                    req_body.pop("tools", None)

                with session.post(
                    LLAMA_SERVER_URL,
                    json=req_body,
                    headers={"Content-Type": "application/json"},
                    timeout=180,
                    stream=True,
                ) as res:
                    if res.status_code != 200:
                        err_chunk = {
                            "choices": [{"delta": {"content": f"\n[error] LLM Server HTTP {res.status_code}\n"}}]
                        }
                        self.wfile.write(f"data: {json.dumps(err_chunk)}\n\n".encode())
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

                        # When reasoning is disabled, strip reasoning_content deltas
                        if not reasoning_active:
                            try:
                                parsed_data = json.loads(data_str)
                                choices = parsed_data.get("choices", [])
                                if choices and isinstance(choices[0], dict):
                                    delta = choices[0].get("delta", {})
                                    if "reasoning_content" in delta:
                                        if not delta.get("content"):
                                            continue
                                        delta.pop("reasoning_content", None)
                                        line = f"data: {json.dumps(parsed_data)}".encode("utf-8")
                            except Exception as e:
                                sys.stderr.write(f"[webui] warning: reasoning delta parse error: {e}\n")

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
                                        fn_name = tc.get("function", {}).get("name")
                                        if fn_name:
                                            tc_entry["function"]["name"] = fn_name
                                        tc_entry["function"]["arguments"] += (
                                            tc.get("function", {}).get("arguments") or ""
                                        )
                        except Exception as e:
                            sys.stderr.write(f"[webui] warning: SSE tool delta parse error: {e}\n")

                calls = [val for _, val in sorted(tool_calls_map.items())] if tool_calls_map else None
                ans_text = "".join(acc_content)
                accumulated_ans = ans_text

                # Self-healing fallback tool extraction for small models in WebUI
                if not calls and ans_text and is_agent and adapters_on:
                    try:
                        calls = adapters.extract_fallback_tool_calls(ans_text) or None
                    except Exception as e:
                        sys.stderr.write(f"[webui] warning: fallback adapter extraction error: {e}\n")

                has_web_call = use_gnd and any(
                    c.get("function", {}).get("name") == "web_search" for c in (calls or [])
                )

                if not calls or (not is_agent and not has_web_call):
                    break

                for idx, tc in enumerate(calls):
                    if not tc.get("id"):
                        tc["id"] = f"call_{_round}_{idx}"

                messages.append({"role": "assistant", "content": ans_text or None, "tool_calls": calls})

                for tc in calls:
                    fname = tc.get("function", {}).get("name", "")
                    raw_args = tc.get("function", {}).get("arguments", "")
                    cid = tc.get("id") or f"call_{_round}_0"

                    if adapters_on:
                        try:
                            fname, args = adapters.heal_tool_call(fname, raw_args)
                        except Exception as e:
                            sys.stderr.write(f"[webui] warning: adapter heal error: {e}\n")
                            try:
                                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                            except Exception:
                                args = {}
                    else:
                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                        except Exception:
                            args = {}

                    if fname == "web_search":
                        query_term = str(args.get("query", "")).strip()
                        start_msg = f"\n\n> 🔍 **Searching Google** • `{query_term}`...\n"
                        self.wfile.write(
                            f"data: {json.dumps({'choices': [{'delta': {'content': start_msg}}]})}\n\n".encode()
                        )
                        self.wfile.flush()
                        try:
                            result = tools.run_tool(fname, args, workspace)
                        except Exception as e:
                            result = f"[tool error] {e}"
                    else:
                        verb = tools.TOOL_VERBS.get(fname, "working")
                        start_msg = f"\n\n> ⚙️ **{verb.title()}** • `{fname}`...\n"
                        self.wfile.write(
                            f"data: {json.dumps({'choices': [{'delta': {'content': start_msg}}]})}\n\n".encode()
                        )
                        self.wfile.flush()
                        try:
                            result = tools.run_tool(fname, args, workspace, confirm_gate_fn=confirm_gate)
                        except Exception as e:
                            result = f"[tool error] {e}"

                    result_str = str(result) if result is not None else ""
                    pruned = (
                        result_str
                        if len(result_str) <= 2000
                        else result_str[:1500] + f"\n... [Snipped {len(result_str) - 1500} chars]"
                    )
                    messages.append({"role": "tool", "tool_call_id": cid, "name": fname, "content": pruned})

            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

            clean_final_ans = RE_THINK_BLOCK.sub("", accumulated_ans).strip()

            if is_agent and user_text and clean_final_ans:
                try:
                    sessions.log_turn(safe_name, str(user_text), clean_final_ans)
                except Exception as e:
                    sys.stderr.write(f"[webui] warning: failed logging session turn: {e}\n")

            if tts.is_tts_enabled() and clean_final_ans:
                try:
                    tts.speak_response(clean_final_ans)
                except Exception as e:
                    sys.stderr.write(f"[webui] warning: TTS playback error: {e}\n")

        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            err_msg = f"\n\n[Gateway error: {e}]\n"
            try:
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': err_msg}}]})}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass
        finally:
            session.close()

    def log_message(self, format, *args):
        if os.environ.get("AI_DEBUG") == "1":
            sys.stderr.write(f"[webui] {self.address_string()} - {format % args}\n")


class ThreadedProxyServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    print(f"\033[1;32m[py-agent] Official llama.cpp WebUI Gateway active at http://127.0.0.1:{PORT}\033[0m")
    server = ThreadedProxyServer(("127.0.0.1", PORT), OfficialWebUIProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[1;33m[py-agent] Shutting down WebUI Gateway...\033[0m")
        server.shutdown()
        server.server_close()
