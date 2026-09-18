#!/usr/bin/env python3
"""Standalone Standard-Library Model Context Protocol (MCP) Client [Env-Aware / On-Demand / MIT]"""

import json
import os
import sqlite3
import subprocess
import sys
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "servers.json")


def load_dotenv() -> None:
    """Auto-loads keys from ~/.config/py-agent/.env into os.environ (zero external dependencies)."""
    env_paths = [
        os.path.expanduser("~/.config/py-agent/.env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for p in env_paths:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


# Initialize environment on load
load_dotenv()


def load_servers_config() -> dict[str, Any]:
    if not os.path.isfile(CONFIG_FILE):
        return {"servers": {}}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("servers", {})
    except Exception as e:
        sys.stderr.write(f"[mcp error] Failed to read {CONFIG_FILE}: {e}\n")
        return {}


def _ensure_sqlite_target(cmd_list: list[str]) -> None:
    for i, arg in enumerate(cmd_list):
        if arg == "--db-path" and i + 1 < len(cmd_list):
            db_path = os.path.expanduser(os.path.expandvars(cmd_list[i + 1]))
            if not os.path.isfile(db_path):
                try:
                    os.makedirs(os.path.dirname(db_path), exist_ok=True)
                    with sqlite3.connect(db_path) as conn:
                        conn.execute(
                            "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT);"
                        )
                except Exception as e:
                    sys.stderr.write(f"[mcp warn] Failed to auto-init sqlite db: {e}\n")
            break


class MCPSession:
    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        clean_cmd = os.path.expanduser(os.path.expandvars(command))
        clean_args = [os.path.expanduser(os.path.expandvars(str(a))) for a in (args or [])]
        self.cmd = [clean_cmd] + clean_args

        if any("mcp-server-sqlite" in str(token) for token in self.cmd):
            _ensure_sqlite_target(self.cmd)

        expanded_env = {k: os.path.expanduser(os.path.expandvars(str(v))) for k, v in (env or {}).items()}
        self.env = {**os.environ, **expanded_env}
        self.proc: subprocess.Popen | None = None
        self._req_id = 0

    def __enter__(self):
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=self.env,
        )
        self._initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        return False

    def _send_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.proc or self.proc.poll() is not None:
            return None

        self._req_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params or {},
        }
        try:
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()

            while True:
                line = self.proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("id") == self._req_id:
                        return data.get("result")
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            sys.stderr.write(f"[mcp error] RPC error ({method}): {e}\n")
        return None

    def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        if not self.proc or self.proc.poll() is not None:
            return
        notif = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        try:
            self.proc.stdin.write(json.dumps(notif) + "\n")
            self.proc.stdin.flush()
        except Exception:
            pass

    def _initialize(self) -> None:
        init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "py-agent-mcp", "version": "1.0"},
        }
        self._send_rpc("initialize", init_params)
        self._send_notification("notifications/initialized")

    def list_tools(self) -> list[dict[str, Any]]:
        res = self._send_rpc("tools/list")
        return res.get("tools", []) if res else []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        res = self._send_rpc("tools/call", {"name": name, "arguments": arguments})
        if not res:
            return "[error: No response from MCP server]"

        if res.get("isError"):
            err_content = res.get("content", [{}])
            return f"[tool error] {err_content[0].get('text', 'Execution failed')}"

        content_list = res.get("content", [])
        return "\n".join(item.get("text", "") for item in content_list if item.get("type") == "text").strip()


def run_call(server_name: str, tool_name: str, args_json: str) -> None:
    servers = load_servers_config()
    if server_name not in servers:
        sys.stderr.write(f"[error] Unknown server '{server_name}'. Configured: {list(servers.keys())}\n")
        sys.exit(1)

    try:
        args = json.loads(args_json) if args_json else {}
    except Exception as e:
        sys.stderr.write(f"[error] Invalid JSON arguments: {e}\n")
        sys.exit(1)

    cfg = servers[server_name]
    with MCPSession(cfg["command"], cfg.get("args", []), cfg.get("env", {})) as session:
        output = session.call_tool(tool_name, args)
        print(output)


def run_list(target_server: str | None = None) -> None:
    servers = load_servers_config()
    targets = [target_server] if target_server and target_server in servers else list(servers.keys())

    for s_name in targets:
        cfg = servers[s_name]
        try:
            with MCPSession(cfg["command"], cfg.get("args", []), cfg.get("env", {})) as session:
                tools = session.list_tools()
                print(f"\nServer: {s_name} ({len(tools)} tools)")
                for t in tools:
                    desc = (t.get("description") or "").splitlines()[0] if t.get("description") else ""
                    print(f"  - {t.get('name')}: {desc}")
        except Exception as e:
            print(f"\nServer: {s_name} [offline/error: {e}]")


def export_schemas() -> None:
    servers = load_servers_config()
    all_schemas = []

    for s_name, cfg in servers.items():
        try:
            with MCPSession(cfg["command"], cfg.get("args", []), cfg.get("env", {})) as session:
                for t in session.list_tools():
                    schema = {
                        "type": "function",
                        "function": {
                            "name": f"mcp_{s_name}_{t.get('name')}",
                            "description": f"[{s_name}] {t.get('description', '')}",
                            "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                        },
                    }
                    all_schemas.append(schema)
        except Exception:
            continue

    print(json.dumps(all_schemas, indent=2))


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage:")
        print("  mcp_client.py list [<server>]")
        print("  mcp_client.py call <server> <tool> '<json_args>'")
        print("  mcp_client.py docs <library> <query>")
        print("  mcp_client.py scrape <url>")
        print("  mcp_client.py search <query>")
        print("  mcp_client.py fetch <url>")
        print("  mcp_client.py schemas")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "list":
        run_list(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "call":
        if len(sys.argv) < 4:
            sys.stderr.write("[error] Usage: mcp_client.py call <server> <tool> '<json_args>'\n")
            sys.exit(1)
        run_call(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "{}")
    elif cmd == "docs":
        lib = sys.argv[2] if len(sys.argv) > 2 else ""
        query = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        payload = json.dumps({"libraryId": lib, "query": query})
        run_call("context7", "query-docs", payload)
    elif cmd == "scrape":
        # Firecrawl JS-rendering web scraper
        url = sys.argv[2] if len(sys.argv) > 2 else ""
        payload = json.dumps({"url": url})
        run_call("firecrawl", "firecrawl_scrape", payload)
    elif cmd == "search":
        # Firecrawl web search with markdown extraction
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        payload = json.dumps({"query": query})
        run_call("firecrawl", "firecrawl_search", payload)
    elif cmd == "fetch":
        url = sys.argv[2] if len(sys.argv) > 2 else ""
        payload = json.dumps({"url": url})
        run_call("fetch", "fetch", payload)
    elif cmd in ("schemas", "schema"):
        export_schemas()
    else:
        sys.stderr.write(f"[error] Unknown command: {cmd}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
