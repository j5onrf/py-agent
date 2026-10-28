#!/usr/bin/env python3
"""
Py-Agent Native OpenBot Multi-Threaded Bridge [Profile Injector]
Runs on http://127.0.0.1:8765/v1 for stock OpenBot integration.
Handles concurrent background title generation and chat requests simultaneously.
"""

import json
import os
import sys
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import requests

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

CFG_DIR = os.path.expanduser("~/.config/py-agent")
MODULES_DIR = os.path.join(CFG_DIR, "modules")
PROFILES_DIR = os.path.join(CFG_DIR, "skills", "profiles")
ENV_PATH = os.path.join(CFG_DIR, ".env")

if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

import agent_cloud as cloud

CORE_TOOLS = {
    "read_file", "write_file", "edit_file", "run_command", "list_dir", "search_code",
    "list_files", "run_shell", "bash", "read", "write", "edit", "glob", "grep"
}

EXPOSED_MODELS = [
    "local-8080",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]


def load_pyagent_profile(model_name: str) -> tuple[str, str]:
    m_lower = (model_name or "").lower()
    selected_path = None
    profile_name = "default"

    # 1. Strict mapping for local models
    if any(k in m_lower for k in ("ling", "local", "8080")):
        target = os.path.join(PROFILES_DIR, "lingtiny.md")
        if os.path.isfile(target):
            selected_path = target
            profile_name = "lingtiny.md"

    # 2. File stem match
    if not selected_path and os.path.isdir(PROFILES_DIR):
        for root, _, files in os.walk(PROFILES_DIR):
            for f in sorted(files):
                if f.endswith(".md"):
                    stem = os.path.splitext(f)[0].lower()
                    if stem in m_lower or m_lower.startswith(stem):
                        selected_path = os.path.join(root, f)
                        profile_name = f
                        break
            if selected_path:
                break

    # 3. Fallbacks
    if not selected_path:
        for fallback in ("lingtiny.md", "gemini.md", "cloud.md", "system_instructions.md"):
            cand = os.path.join(PROFILES_DIR, fallback)
            if not os.path.isfile(cand):
                cand = os.path.join(CFG_DIR, "skills", fallback)
            if os.path.isfile(cand):
                selected_path = cand
                profile_name = fallback
                break

    if selected_path and os.path.isfile(selected_path):
        try:
            with open(selected_path, "r", encoding="utf-8") as pf:
                raw = pf.read()
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip(), profile_name
            return raw.strip(), profile_name
        except Exception:
            pass

    return (
        "ROLE: Autonomous Systems & Software Engineer.\n\n"
        "DIRECTIVES:\n"
        "- Casual greetings: reply in 1 concise sentence without calling tools.\n"
        "- Code & Execution: Clean, robust, standard library code. Call tools directly with zero filler.",
        profile_name,
    )


def scrub_payload(payload: dict) -> tuple[dict, str]:
    messages = payload.get("messages", [])
    requested_model = payload.get("model", "")

    profile_prompt, profile_name = load_pyagent_profile(requested_model)
    clean_messages = [{"role": "system", "content": profile_prompt}]

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            continue

        if isinstance(content, str):
            # Incinerate OpenBot hidden instructions injected into user messages
            import re
            content = re.sub(r"<openbot-[^>]+>.*?</openbot-[^>]+>", "", content, flags=re.DOTALL)
            content = re.sub(r"<opencode-[^>]+>.*?</opencode-[^>]+>", "", content, flags=re.DOTALL)
            content = content.strip()
            if not content and role == "user":
                continue

            if role == "tool" and len(content) > 1200:
                content = content[:600] + "\n...[truncated for prefill economy]...\n" + content[-600:]
            msg = dict(msg)
            msg["content"] = content

        clean_messages.append(msg)

    payload["messages"] = clean_messages

    req_lower = requested_model.lower()
    is_local = any(k in req_lower for k in ("local", "8080", "ling", "flint", "sage"))

    # Local CPU mode: burn tools completely so llama-server doesn't expand 2,000 JSON tokens
    if is_local:
        if "tools" in payload:
            del payload["tools"]
    else:
        if "tools" in payload and payload["tools"]:
            filtered = [
                t for t in payload["tools"]
                if t.get("function", {}).get("name") in CORE_TOOLS
            ]
            if filtered:
                payload["tools"] = filtered
            else:
                del payload["tools"]

    return payload, profile_name


class OpenBotBridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_POST(self):
        if self.path.endswith("/chat/completions"):
            req_start = time.time()
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)

            try:
                incoming_payload = json.loads(raw_body)
                requested_model = incoming_payload.get("model", "local-8080")
                is_streaming = incoming_payload.get("stream", True)

                clean_payload, profile_name = scrub_payload(incoming_payload)
                req_lower = requested_model.lower()
                is_local = any(k in req_lower for k in ("local", "8080", "ling", "flint", "sage"))

                user_snippet = ""
                for m in reversed(clean_payload["messages"]):
                    if m.get("role") == "user":
                        user_snippet = str(m.get("content", ""))[:40].replace("\n", " ")
                        break

                ts = time.strftime("%H:%M:%S")

                # CPU Slot Saver: Fast-path title generation requests only on explicit title prompts
                last_user_content = ""
                for m in reversed(incoming_payload.get("messages", [])):
                    if m.get("role") == "user":
                        last_user_content = str(m.get("content", "")).lower()
                        break

                title_triggers = (
                    "first message of the conversation",
                    "first message of the session",
                    "generate a title",
                    "give this conversation a title",
                    "short title",
                    "title for this chat",
                    "title of this",
                    "session title",
                    "create a title",
                )
                is_title = any(t in last_user_content for t in title_triggers)

                if is_local and is_title:
                    self.send_response(200)
                    self._send_cors()
                    if is_streaming:
                        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "close")
                        self.end_headers()
                        chunk = json.dumps({"choices": [{"delta": {"content": "Chat"}}]})
                        self.wfile.write(f"data: {chunk}\n\ndata: [DONE]\n\n".encode())
                        self.wfile.flush()
                    else:
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        resp_body = {"choices": [{"message": {"role": "assistant", "content": "Chat"}}]}
                        self.wfile.write(json.dumps(resp_body).encode())
                    print(f"[{ts}] ⚡ Instantly resolved title request (saved CPU slot)")
                    return

                tools_count = len(clean_payload.get("tools", []))
                sys_chars = len(clean_payload["messages"][0]["content"])
                print(f"[{ts}] ▶ [{profile_name}] {sys_chars} chars | Tools: {tools_count} | \"{user_snippet}\"")

                if is_local:
                    upstream_url = "http://127.0.0.1:8080/v1/chat/completions"
                    upstream_headers = {"Content-Type": "application/json"}
                    upstream_body = {
                        "model": requested_model,
                        "messages": clean_payload["messages"],
                        "stream": is_streaming,
                    }
                    timeout = 60
                else:
                    active_configs = cloud.get_active_configs(clean_payload["messages"])
                    if not active_configs:
                        self.send_error(500, "agent_cloud found no active API key in .env")
                        return

                    upstream_url, upstream_headers, upstream_body, timeout = active_configs[0]
                    for cfg in active_configs:
                        if "googleapis.com" in cfg[0]:
                            upstream_url, upstream_headers, upstream_body, timeout = cfg
                            break

                    upstream_body["model"] = requested_model
                    upstream_body["messages"] = clean_payload["messages"]
                    upstream_body["stream"] = is_streaming
                    if "tools" in clean_payload:
                        upstream_body["tools"] = clean_payload["tools"]

                resp = requests.post(
                    upstream_url,
                    headers=upstream_headers,
                    json=upstream_body,
                    stream=is_streaming,
                    timeout=max(timeout, 60),
                )

                if resp.status_code != 200:
                    print(f"[{time.strftime('%H:%M:%S')}] ❌ Upstream HTTP {resp.status_code}: {resp.text[:120]}")
                    self.send_response(resp.status_code)
                    self._send_cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(resp.content)
                    return

                self.send_response(200)
                self._send_cors()

                if is_streaming:
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache, no-transform")
                    self.send_header("Connection", "close")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()

                    self.close_connection = True
                    first_token = None
                    chunk_count = 0

                    # Unbuffered raw chunk passthrough (zero buffer delay)
                    for chunk in resp.iter_content(chunk_size=None):
                        if not chunk:
                            continue
                        if first_token is None:
                            first_token = time.time() - req_start
                        chunk_count += 1
                        self.wfile.write(chunk)
                        self.wfile.flush()

                    elapsed = time.time() - req_start
                    ttft_str = f"{first_token:.2f}s" if first_token else "N/A"
                    print(f"[{time.strftime('%H:%M:%S')}] ✔ Finished \"{user_snippet}\": TTFT={ttft_str} | Total={elapsed:.2f}s ({chunk_count} chunks)")
                else:
                    self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                    self.end_headers()
                    self.wfile.write(resp.content)
                    elapsed = time.time() - req_start
                    print(f"[{time.strftime('%H:%M:%S')}] ✔ Finished non-streamed in {elapsed:.2f}s")

            except (ConnectionResetError, BrokenPipeError):
                # Client cancelled/stopped turn (e.g. user clicked Stop button)
                return
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Bridge exception: {e}")
                self.send_response(500)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Bridge error: {str(e)}"}).encode())
        else:
            self.send_response(404)
            self._send_cors()
            self.end_headers()

    def do_GET(self):
        if self.path.endswith("/models"):
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "object": "list",
                "data": [{"id": m, "object": "model"} for m in EXPOSED_MODELS],
            }
            self.wfile.write(json.dumps(data).encode())
        elif self.path in ("/", "/health"):
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self._send_cors()
            self.end_headers()


def main():
    port = 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), OpenBotBridgeHandler)
    print(f"⚡ [py-agent] Multi-Threaded OpenBot Bridge active on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
