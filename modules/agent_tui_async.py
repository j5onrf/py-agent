#!/usr/bin/env python3
"""Asynchronous uvloop background services for Local-AI Agent TUI [Production Ready]"""

import asyncio
import json
import os


async def run_async_cmd(cmd: list[str], cwd: str) -> str:
    """Non-blocking async subprocess executor leveraging libuv C pipes."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        out, err = await proc.communicate()
        return (out or err).decode("utf-8", errors="ignore").strip()
    except (OSError, asyncio.SubprocessError) as e:
        return f"Async command error: {e}"


async def watch_workspace_changes(app) -> None:
    """Async background task watching OKF memory directives via uvloop libuv event loop."""
    mem_dir = os.path.join(app.workspace_path, ".agent", "memory")

    def _get_dir_mtime() -> float:
        if not os.path.isdir(mem_dir):
            return 0.0
        try:
            mtimes = [os.path.getmtime(os.path.join(mem_dir, f)) for f in os.listdir(mem_dir) if f.endswith(".md")]
            return max(mtimes) if mtimes else os.path.getmtime(mem_dir)
        except OSError:
            return 0.0

    last_mtime = _get_dir_mtime()

    try:
        while True:
            await asyncio.sleep(2.0)
            cur_mtime = _get_dir_mtime()
            if cur_mtime > last_mtime:
                last_mtime = cur_mtime
                await asyncio.to_thread(app.refresh_db_counts)
                if hasattr(app, "lbl_database"):
                    app.lbl_database.update(f"[dim]DB State[/dim]  {app.get_db_status_string()}")
                app.notify("[dim]Project memory directives updated from disk.[/dim]", sys_prefix=False)
    except (asyncio.CancelledError, GeneratorExit):
        pass


async def start_subagent_ipc_hub(app) -> None:
    """Unix Domain Socket IPC hub running on uvloop for multi-terminal sub-agent tracking."""
    sock_path = f"/tmp/local-ai-{app.safe_name}.sock"
    if os.path.exists(sock_path):
        try:
            os.remove(sock_path)
        except OSError:
            pass

    async def handle_subagent_msg(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            if data := await reader.read(65536):
                p = json.loads(data.decode("utf-8", errors="ignore"))
                params = p.get("params", {}) if isinstance(p.get("params"), dict) else p
                app.notify(
                    f"[dim]⚡ [bold cyan]{params.get('sub_id', 'Sub-agent')}[/bold cyan]: {params.get('status', 'Active')}[/dim]",
                    sys_prefix=False,
                )
        except (OSError, json.JSONDecodeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, asyncio.CancelledError):
                pass

    server = None
    try:
        server = await asyncio.start_unix_server(handle_subagent_msg, path=sock_path)
        async with server:
            await server.serve_forever()
    except (OSError, asyncio.CancelledError):
        pass
    finally:
        if server is not None:
            server.close()
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except OSError:
                pass
