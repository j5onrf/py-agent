#!/usr/bin/env python3
"""Asynchronous uvloop background services for Local-AI Agent TUI [Production Ready]"""

import asyncio
import json
import os
import subprocess
from rich.markup import escape


async def run_async_cmd(cmd: list[str], cwd: str) -> str:
    """Non-blocking async subprocess executor returning both stdout and stderr."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        out, err = await proc.communicate()
        stdout = (out or b"").decode("utf-8", errors="ignore").strip()
        stderr = (err or b"").decode("utf-8", errors="ignore").strip()
        if stdout and stderr:
            return f"{stdout}\n{stderr}"
        return stdout or stderr
    except (OSError, subprocess.SubprocessError) as e:
        return f"Async command error: {e}"


async def watch_workspace_changes(app) -> None:
    """Async background task watching OKF memory directives for additions, edits, and deletions."""
    mem_dir = os.path.join(app.workspace_path, ".agent", "memory")

    def _get_dir_state() -> tuple[float, int]:
        if not os.path.isdir(mem_dir):
            return 0.0, 0
        try:
            files = [f for f in os.listdir(mem_dir) if f.endswith(".md")]
            mtimes = [os.path.getmtime(os.path.join(mem_dir, f)) for f in files]
            max_m = max(mtimes) if mtimes else os.path.getmtime(mem_dir)
            return max_m, len(files)
        except OSError:
            return 0.0, 0

    last_state = _get_dir_state()

    try:
        while True:
            await asyncio.sleep(2.0)
            cur_state = _get_dir_state()
            if cur_state != last_state:
                last_state = cur_state
                await asyncio.to_thread(app.refresh_db_counts)
                if hasattr(app, "lbl_database"):
                    app.lbl_database.update(f"[dim]DB State[/dim]  {app.get_db_status_string()}")
                app.notify("[dim]Project memory directives updated from disk.[/dim]", sys_prefix=False)
    except asyncio.CancelledError:
        raise
    except Exception:
        pass


async def start_subagent_ipc_hub(app) -> None:
    """Unix Domain Socket IPC hub with private runtime directory and probe-verified cleanup."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir or not os.path.isdir(runtime_dir):
        runtime_dir = os.path.join(os.path.expanduser("~/.config/py-agent"), ".run")

    os.makedirs(runtime_dir, exist_ok=True)
    try:
        os.chmod(runtime_dir, 0o700)
    except OSError:
        pass

    sock_path = os.path.join(runtime_dir, f"tui-{app.safe_name}.sock")

    # Probe for active listener before unlinking to prevent clobbering existing sessions
    if os.path.exists(sock_path):
        try:
            _, writer = await asyncio.open_unix_connection(path=sock_path)
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, asyncio.CancelledError):
                pass
            return
        except (OSError, ConnectionRefusedError):
            try:
                os.remove(sock_path)
            except OSError:
                pass

    async def handle_subagent_msg(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            chunks = []
            while chunk := await reader.read(8192):
                chunks.append(chunk)
            data = b"".join(chunks)

            if data:
                p = json.loads(data.decode("utf-8", errors="ignore"))
                if not isinstance(p, dict):
                    return
                params = p.get("params", {}) if isinstance(p.get("params"), dict) else p

                # Escape Rich markup to prevent terminal control injection
                raw_id = str(params.get("sub_id", "Sub-agent"))
                raw_status = str(params.get("status", "Active"))
                safe_id = escape(raw_id)
                safe_status = escape(raw_status)

                app.notify(
                    f"[dim]⚡ [bold cyan]{safe_id}[/bold cyan]: {safe_status}[/dim]",
                    sys_prefix=False,
                )
        except (OSError, json.JSONDecodeError, AttributeError):
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
        try:
            os.chmod(sock_path, 0o600)
        except OSError:
            pass

        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        raise
    except OSError as e:
        app.notify(f"[dim yellow]IPC hub unavailable: {e}[/dim yellow]", sys_prefix=False)
    finally:
        if server is not None:
            server.close()
            try:
                await server.wait_closed()
            except (OSError, asyncio.CancelledError):
                pass
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except OSError:
                pass
