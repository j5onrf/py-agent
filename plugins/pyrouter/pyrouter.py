#!/usr/bin/env python3
"""PyRouter - Slim Zero-Dependency Gateway for OpenCode & Py-Agent.
Uses only Python standard library + requests.
Exposes /v1/chat/completions (OpenAI) and /v1/messages (Anthropic Claude).
"""

import http.server
import json
import os
import random
import re
import string
import sys
import time
import uuid
from typing import Any, Dict, List

import requests

PORT = 20128
CFG_DIR = os.path.expanduser("~/.config/py-agent")
ENV_PATH = os.path.join(CFG_DIR, ".env")
CACHE_PATH = os.path.join(CFG_DIR, "var", ".openrouter_cache_v2.json")

_models_cache: Dict[str, Any] = {"ts": 0.0, "data": b""}

GATE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run shell commands",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read file contents",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


def make_canonical_session() -> str:
    ts_hex = f"{int(time.time() * 1000):012x}"
    rand_chars = "".join(random.choices(string.ascii_letters + string.digits, k=14))
    return f"ses_{ts_hex}{rand_chars}"


_STABLE_SESSION = make_canonical_session()


# ── Dynamic Config & Key Resolution ──────────────────────────────────────────

def load_active_env() -> Dict[str, str]:
    """Reads ~/.config/py-agent/.env dynamically on every turn."""
    env: Dict[str, str] = {}
    if os.path.isfile(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#") and "=" in s:
                        k, v = s.replace("export ", "", 1).split("=", 1)
                        clean_v = v.split(" #")[0].strip().strip('"').strip("'")
                        env[k.strip()] = clean_v
        except OSError:
            pass
    return env


def resolve_active_upstream(requested_model: str | None = None) -> Dict[str, Any]:
    """Resolves upstream provider matching py-agent's agent_cloud priority."""
    env = load_active_env()

    for k in sorted(env.keys()):
        if re.match(r"^CUSTOM\d*_(?:API_)?KEY$", k) and env[k]:
            prefix = k.split("_")[0]
            url = env.get(f"{prefix}_URL", "")
            model = requested_model or env.get(f"{prefix}_MODEL", "big-pickle")
            key = env[k]

            # Break recursive self-loop when CUSTOM<N>_URL points to PyRouter (:20128)
            if "20128" in url or "pyrouter" in url:
                return {
                    "type": "openai",
                    "url": "https://opencode.ai/zen/v1/chat/completions",
                    "key": "" if key == "not-needed" else key,
                    "model": model or "big-pickle",
                }

            provider_type = "anthropic" if "anthropic.com" in url else "openai"
            return {
                "type": provider_type,
                "url": url or "http://127.0.0.1:8080/v1/chat/completions",
                "key": "" if key == "not-needed" else key,
                "model": model,
            }

    if env.get("GEMINI_API_KEY"):
        return {
            "type": "openai",
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "key": env["GEMINI_API_KEY"],
            "model": requested_model or env.get("GEMINI_MODEL", "gemini-2.5-flash"),
        }

    if env.get("OPENROUTER_API_KEY"):
        return {
            "type": "openai",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": env["OPENROUTER_API_KEY"],
            "model": requested_model or env.get("OPENROUTER_MODEL", "openrouter/free"),
        }

    if env.get("DEEPSEEK_API_KEY"):
        return {
            "type": "openai",
            "url": "https://api.deepseek.com/chat/completions",
            "key": env["DEEPSEEK_API_KEY"],
            "model": requested_model or env.get("DEEPSEEK_MODEL", "deepseek-chat"),
        }

    return {
        "type": "openai",
        "url": "http://127.0.0.1:8080/v1/chat/completions",
        "key": "",
        "model": requested_model or "local-model",
    }


# ── Protocol Adapters: Anthropic -> OpenAI ───────────────────────────────────

def anthropic_to_openai(body: Dict[str, Any], default_model: str) -> Dict[str, Any]:
    """Translates Claude Messages request to OpenAI Chat Completions payload."""
    messages: List[Dict[str, Any]] = []

    if "system" in body:
        sys_val = body["system"]
        if isinstance(sys_val, list):
            sys_text = "".join(b.get("text", "") for b in sys_val if b.get("type") == "text")
        else:
            sys_text = str(sys_val)
        messages.append({"role": "system", "content": sys_text})

    for msg in body.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_acc = []
            tool_calls = []
            for block in content:
                b_type = block.get("type")
                if b_type == "text":
                    text_acc.append(block.get("text", ""))
                elif b_type == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    })
                elif b_type == "tool_result":
                    res_val = block.get("content", "")
                    if isinstance(res_val, list):
                        res_val = "".join(b.get("text", "") for b in res_val if b.get("type") == "text")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": str(res_val),
                    })

            if text_acc or tool_calls:
                m_obj: Dict[str, Any] = {"role": role, "content": "\n".join(text_acc)}
                if tool_calls:
                    m_obj["tool_calls"] = tool_calls
                messages.append(m_obj)

    openai_tools = []
    for t in body.get("tools", []):
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t.get("name"),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })

    payload: Dict[str, Any] = {
        "model": body.get("model") or default_model,
        "messages": messages,
        "stream": body.get("stream", False),
        "temperature": body.get("temperature", 0.7),
    }
    if "max_tokens" in body:
        payload["max_tokens"] = body["max_tokens"]
    if openai_tools:
        payload["tools"] = openai_tools

    return payload


# ── HTTP Request Handler ─────────────────────────────────────────────────────

class RouterHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        if path in ("/v1/models", "/models"):
            global _models_cache
            now = time.time()
            if now - _models_cache.get("ts", 0.0) < 300.0 and _models_cache.get("data"):
                data = _models_cache["data"]
            else:
                upstream = resolve_active_upstream()
                discovered: List[str] = [upstream["model"]]

                targets = ["https://opencode.ai/inference/v1/models"]
                up_models = re.sub(r"/chat/completions/?$", "/models", upstream["url"])
                if "20128" not in up_models:
                    targets.append(up_models)

                for target_url in targets:
                    try:
                        h = {"User-Agent": "opencode/1.18.31"}
                        if upstream["key"] and upstream["key"] != "not-needed":
                            h["Authorization"] = f"Bearer {upstream['key']}"
                        r = requests.get(target_url, headers=h, timeout=2.5)
                        if r.status_code == 200:
                            m_data = r.json()
                            items = m_data.get("data") or m_data.get("models") or []
                            for it in items:
                                mid = it.get("id") or it.get("name") if isinstance(it, dict) else str(it)
                                if not mid or "test" in mid.lower():
                                    continue
                                if "-free" in mid.lower() or ":free" in mid.lower() or "pickle" in mid.lower():
                                    if mid not in discovered:
                                        discovered.append(mid)
                    except Exception:
                        pass

                discovered = discovered[:10]
                if len(discovered) <= 1:
                    for om in (
                        "big-pickle",
                        "deepseek-v4.1-flash-free",
                        "flint-40b-free",
                        "glm-5.3-flash-free",
                        "mimo-v2.6-flash-free",
                        "nemotron-3.5-lightning-free",
                    ):
                        if om not in discovered:
                            discovered.append(om)

                models = [{"id": mid, "object": "model", "owned_by": "dynamic"} for mid in discovered if mid]
                data = json.dumps({"object": "list", "data": models}).encode("utf-8")
                _models_cache = {"ts": now, "data": data}

            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self._send_cors()
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.close_connection = True
        else:
            self.send_response(404)
            self._send_cors()
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')
            self.close_connection = True

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self._send_cors()
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid JSON body"}')
            self.close_connection = True
            return

        if path in ("/v1/chat/completions", "/chat/completions"):
            self._handle_chat_completions(body)
        elif path in ("/v1/messages", "/messages"):
            self._handle_messages(body)
        else:
            self.send_response(404)
            self._send_cors()
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b'{"error": "Endpoint not found"}')
            self.close_connection = True

    def _handle_chat_completions(self, body: Dict[str, Any]) -> None:
        req_model = body.get("model")
        upstream = resolve_active_upstream(req_model if req_model and req_model != "default" else None)

        incoming_tools = body.get("tools") or []
        if incoming_tools:
            has_gate = any(t.get("function", {}).get("name") in ("bash", "read") for t in incoming_tools)
            clean_tools = incoming_tools if has_gate else (GATE_TOOLS + incoming_tools)
            tool_choice = body.get("tool_choice", "auto")
        else:
            clean_tools = GATE_TOOLS
            tool_choice = "none"

        clean_body: Dict[str, Any] = {
            "model": upstream["model"],
            "messages": body.get("messages", []),
            "stream": True,
            "tools": clean_tools,
            "tool_choice": tool_choice,
        }
        if "temperature" in body:
            clean_body["temperature"] = body["temperature"]
        if "max_tokens" in body:
            clean_body["max_tokens"] = body["max_tokens"]

        key = upstream["key"]
        auth_hdr = f"Bearer {key}" if (key and key != "not-needed") else "Bearer public"
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_hdr,
            "User-Agent": "opencode/1.18.31",
            "x-opencode-client": "cli",
            "x-opencode-project": "global",
            "x-opencode-session": _STABLE_SESSION,
            "x-opencode-request": "_msg",
        }

        try:
            with requests.post(upstream["url"], json=clean_body, headers=headers, stream=True, timeout=(15, 3.5)) as resp:
                self.send_response(resp.status_code)
                self._send_cors()

                if resp.status_code != 200:
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    err_text = resp.text[:300].replace("\n", " ")
                    err_chunk = json.dumps({"choices": [{"delta": {"content": f"\n\n[OpenCode Error {resp.status_code}]: {err_text}\n"}}]})
                    self.wfile.write(f"data: {err_chunk}\n\ndata: [DONE]\n\n".encode("utf-8"))
                    self.wfile.flush()
                    self.close_connection = True
                    return

                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                rolling_tail = b""
                try:
                    for chunk in resp.iter_content(chunk_size=None):
                        if not chunk:
                            continue
                        self.wfile.write(chunk)
                        self.wfile.flush()

                        rolling_tail = (rolling_tail + chunk)[-256:]
                        if b"[DONE]" in rolling_tail or (
                            b'"finish_reason"' in rolling_tail
                            and b'"finish_reason":null' not in rolling_tail
                            and b'"finish_reason": null' not in rolling_tail
                        ):
                            break
                except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                    pass
                except (BrokenPipeError, ConnectionResetError):
                    pass

                try:
                    self.wfile.write(b"\ndata: [DONE]\n\n")
                    self.wfile.flush()
                except Exception:
                    pass
                finally:
                    self.close_connection = True
        except Exception as e:
            self.send_response(502)
            self._send_cors()
            self.send_header("Connection", "close")
            self.end_headers()
            err_msg = json.dumps({"error": f"Upstream connection failed: {e}"}).encode("utf-8")
            self.wfile.write(err_msg)
            self.close_connection = True

    def _handle_messages(self, body: Dict[str, Any]) -> None:
        req_model = body.get("model")
        upstream = resolve_active_upstream(req_model)
        openai_body = anthropic_to_openai(body, default_model=upstream["model"])

        incoming_tools = openai_body.get("tools") or []
        if incoming_tools:
            has_gate = any(t.get("function", {}).get("name") in ("bash", "read") for t in incoming_tools)
            clean_tools = incoming_tools if has_gate else (GATE_TOOLS + incoming_tools)
            tool_choice = openai_body.get("tool_choice", "auto")
        else:
            clean_tools = GATE_TOOLS
            tool_choice = "none"

        clean_body: Dict[str, Any] = {
            "model": upstream["model"],
            "messages": openai_body.get("messages", []),
            "stream": True,
            "tools": clean_tools,
            "tool_choice": tool_choice,
        }
        if "temperature" in openai_body:
            clean_body["temperature"] = openai_body["temperature"]
        if "max_tokens" in openai_body:
            clean_body["max_tokens"] = openai_body["max_tokens"]

        key = upstream["key"]
        auth_hdr = f"Bearer {key}" if (key and key != "not-needed") else "Bearer public"
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_hdr,
            "User-Agent": "opencode/1.18.31",
            "x-opencode-client": "cli",
            "x-opencode-project": "global",
            "x-opencode-session": _STABLE_SESSION,
            "x-opencode-request": "_msg",
        }

        try:
            with requests.post(upstream["url"], json=clean_body, headers=headers, stream=True, timeout=(15, 3.5)) as resp:
                self.send_response(resp.status_code)
                self._send_cors()

                if resp.status_code != 200:
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    err_text = resp.text[:300].replace("\n", " ")
                    err_chunk = json.dumps({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": f"\n\n[OpenCode Error {resp.status_code}]: {err_text}\n"}})
                    self.wfile.write(f"event: content_block_delta\ndata: {err_chunk}\n\nevent: message_stop\ndata: {{\"type\": \"message_stop\"}}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    self.close_connection = True
                    return

                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                self._emit_sse("message_start", {"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "model": upstream["model"], "content": [], "stop_reason": None, "usage": {"input_tokens": 0, "output_tokens": 0}}})
                self._emit_sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})

                active_tool_idx = None
                block_idx = 0

                try:
                    for line in resp.iter_lines(chunk_size=1):
                        if not line:
                            continue
                        line_str = line.decode("utf-8", errors="replace")
                        if not line_str.startswith("data:"):
                            continue
                        raw_data = line_str[5:].strip()
                        if raw_data == "[DONE]" or (
                            '"finish_reason"' in raw_data
                            and '"finish_reason":null' not in raw_data
                            and '"finish_reason": null' not in raw_data
                        ):
                            break

                        try:
                            chunk = json.loads(raw_data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})

                            if content := delta.get("content"):
                                self._emit_sse("content_block_delta", {
                                    "type": "content_block_delta",
                                    "index": 0,
                                    "delta": {"type": "text_delta", "text": content}
                                })

                            if tool_calls := delta.get("tool_calls"):
                                for tc in tool_calls:
                                    t_idx = tc.get("index", 0)
                                    if active_tool_idx != t_idx:
                                        if active_tool_idx is not None:
                                            self._emit_sse("content_block_stop", {"type": "content_block_stop", "index": block_idx})
                                        block_idx += 1
                                        active_tool_idx = t_idx
                                        fn_name = tc.get("function", {}).get("name", "")
                                        cid = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")
                                        self._emit_sse("content_block_start", {
                                            "type": "content_block_start",
                                            "index": block_idx,
                                            "content_block": {"type": "tool_use", "id": cid, "name": fn_name, "input": {}}
                                        })

                                    if arg_chunk := tc.get("function", {}).get("arguments"):
                                        self._emit_sse("content_block_delta", {
                                            "type": "content_block_delta",
                                            "index": block_idx,
                                            "delta": {"type": "input_json_delta", "partial_json": arg_chunk}
                                        })
                        except Exception:
                            continue

                    self._emit_sse("content_block_stop", {"type": "content_block_stop", "index": block_idx})
                    self._emit_sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 0}})
                    self._emit_sse("message_stop", {"type": "message_stop"})
                except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                    pass
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    self.close_connection = True
        except Exception as e:
            self.send_response(502)
            self._send_cors()
            self.send_header("Connection", "close")
            self.end_headers()
            err_msg = json.dumps({"error": f"Upstream translation error: {e}"}).encode("utf-8")
            self.wfile.write(err_msg)
            self.close_connection = True

    def _emit_sse(self, event_type: str, data: Dict[str, Any]) -> None:
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n".encode("utf-8")
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


class SilentServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        exc = sys.exc_info()[0]
        if exc in (BrokenPipeError, ConnectionResetError):
            return
        super().handle_error(request, client_address)


def main() -> None:
    server = SilentServer(("127.0.0.1", PORT), RouterHandler)
    print(f"\033[1;32m✓ PyRouter active on http://127.0.0.1:{PORT}\033[0m")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPyRouter stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
