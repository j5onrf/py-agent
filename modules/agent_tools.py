#!/usr/bin/env python3
"""Native Tool Engine - Handles file editing, commands, & graph intelligence [High-Performance In-Memory Edition]"""

import ast
import difflib
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.syntax import Syntax

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
_console_err = Console(stderr=True)
BINARY_EXTENSIONS = frozenset(
    {
        ".db",
        ".sqlite",
        ".sqlite3",
        ".bin",
        ".pyc",
        ".so",
        ".dll",
        ".exe",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".pdf",
        ".docx",
        ".xlsx",
        ".db-wal",
        ".db-shm",
    }
)
RE_ABS_PATH = re.compile(r"/(?:[a-zA-Z0-9_\-\.]+/)*[a-zA-Z0-9_\-\.]*")

_SESSION_READ_FILES: set[str] = set()

EDIT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": n,
            "description": d,
            "parameters": {"type": "object", "properties": p, "required": r},
        },
    }
    for n, d, p, r in [
        (
            "read_symbol",
            "Extract source code snippet for a function/class symbol from index graph without reading full file.",
            {"symbol": {"type": "string"}},
            ["symbol"],
        ),
        (
            "trace_symbol",
            "Trace callers (who invokes) and callees (who is called by) a function/class symbol in index graph.",
            {"symbol": {"type": "string"}},
            ["symbol"],
        ),
        (
            "blast_radius",
            "Calculate upstream structural impact map to see what will break if a symbol is modified.",
            {"symbol": {"type": "string"}},
            ["symbol"],
        ),
        (
            "find_symbol",
            "Search codebase graph for symbols, functions, classes, or file paths matching a pattern.",
            {"pattern": {"type": "string"}},
            ["pattern"],
        ),
        (
            "architecture_overview",
            "Get high-level summary of active files, classes, functions, and call connection counts.",
            {},
            [],
        ),
        (
            "read_file",
            "Read a text file from the project. Optionally specify line_start and line_end.",
            {
                "path": {"type": "string"},
                "line_start": {"type": "integer"},
                "line_end": {"type": "integer"},
            },
            ["path"],
        ),
        (
            "edit_file",
            "Surgically replace exact text (old_str) with new_str in a file without rewriting the whole file.",
            {
                "path": {"type": "string"},
                "old_str": {
                    "type": "string",
                    "description": "Exact text to find and replace.",
                },
                "new_str": {"type": "string", "description": "New replacement text."},
            },
            ["path", "old_str", "new_str"],
        ),
        (
            "write_file",
            "Create a new file or completely overwrite an existing file. If file exists, pass overwrite=true.",
            {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "overwrite": {
                    "type": "boolean",
                    "description": "Set true to confirm overwriting an existing file.",
                },
            },
            ["path", "content"],
        ),
        (
            "list_dir",
            "List directory contents in the project.",
            {"path": {"type": "string"}},
            [],
        ),
        (
            "run_command",
            "Run a shell command in project root.",
            {"command": {"type": "string"}},
            ["command"],
        ),
    ]
]

TOOL_VERBS = {
    "read_symbol": "tracing symbol snippet",
    "trace_symbol": "tracing call graph",
    "blast_radius": "calculating impact",
    "find_symbol": "searching graph",
    "architecture_overview": "mapping architecture",
    "read_file": "checking",
    "edit_file": "surgically editing",
    "write_file": "updating",
    "list_dir": "checking",
    "run_command": "executing",
}

_graph_module = None


def _get_graph_engine():
    """Loads index-map module into memory once for sub-millisecond execution."""
    global _graph_module
    if _graph_module is not None:
        return _graph_module

    mod_path = os.path.join(CFG_DIR, "tools", "index-map", "index-map")
    if os.path.exists(mod_path):
        try:
            spec = importlib.util.spec_from_file_location("index_map_engine", mod_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                _graph_module = mod
                return _graph_module
        except Exception:
            pass
    return None


def _safe_path(workspace: str, p: str) -> str:
    if not p: return os.path.realpath(workspace)
    clean_p = os.path.expanduser(urllib.parse.unquote(str(p).strip().strip('"\'\\')))
    ws_real = os.path.realpath(workspace)
    
    # Path healing: if 2B model wrote "/file.py" instead of "file.py"
    if clean_p.startswith("/") and not clean_p.startswith(ws_real):
        rel_candidate = clean_p.lstrip("/")
        if os.path.exists(os.path.join(ws_real, rel_candidate)) or "/" not in rel_candidate:
            clean_p = rel_candidate

    return os.path.realpath(clean_p if os.path.isabs(clean_p) else os.path.join(ws_real, clean_p))


def _is_outside_workspace(workspace: str, full_path: str) -> bool:
    root = os.path.realpath(workspace)
    return full_path != root and not full_path.startswith(root + os.sep)


def run_graph_cmd(cmd_name: str, arg: str, workspace: str) -> str:
    """High-performance in-memory graph dispatcher with subprocess fallback."""
    engine = _get_graph_engine()

    if engine:
        try:
            if cmd_name == "snippet" and hasattr(engine, "extract_snippet"):
                return engine.extract_snippet(arg, workspace)
            if cmd_name == "trace" and hasattr(engine, "trace_symbol"):
                return engine.trace_symbol(arg, workspace)
            if cmd_name == "blast-radius" and hasattr(engine, "get_blast_radius"):
                return engine.get_blast_radius(arg, workspace)
            if cmd_name == "search" and hasattr(engine, "search_symbols"):
                return engine.search_symbols(arg, workspace)
            if cmd_name == "architecture" and hasattr(engine, "show_architecture"):
                return engine.show_architecture(workspace)
        except Exception as e:
            return f"[error] in-memory graph execution failed: {e}"

    try:
        mod_path = os.path.join(CFG_DIR, "tools", "index-map", "index-map")
        cmd_args = [sys.executable, mod_path, cmd_name] + ([arg] if arg else [])
        res = subprocess.run(
            cmd_args, cwd=workspace, capture_output=True, text=True, timeout=12
        )
        out = (res.stdout or res.stderr or "").strip()
        return out or f"[error] '{cmd_name}' returned no results for '{arg}'."
    except (OSError, subprocess.SubprocessError, TimeoutError) as e:
        return f"[error] failed to run graph command {cmd_name}: {e}"


def run_tool(
    name: str,
    args: dict[str, Any],
    workspace: str,
    confirm_gate_fn: Callable[[str], bool] | None = None,
    print_output_fn: Callable[[str], None] | None = None,
) -> str:
    gates_active = os.environ.get("AI_CONFIRM_GATES", "1") == "1"
    denial = "[denied] User declined tool execution."
    raw_path = args.get("path", "")
    full = _safe_path(workspace, raw_path) if raw_path else ""

    def _gate(reason: str) -> bool:
        if confirm_gate_fn:
            return confirm_gate_fn(reason)
        if "OUT-OF-BOUNDS" in reason:
            return False
        return True

    # 1. IPython Kernel Execution
    if name == "exec_python":
        try:
            import agent_ipython as ipython

            out = ipython.run_cell(args.get("code", ""), workspace, confirm_gate_fn)
            if print_output_fn:
                print_output_fn(out)
            return out
        except Exception as e:
            return f"[error] Python kernel execution failed: {e}"

    # 2. Graph Intelligence Tools
    if name == "read_symbol":
        out = run_graph_cmd("snippet", args.get("symbol", "").strip(), workspace)
        if print_output_fn:
            print_output_fn(out)
        return out

    if name == "trace_symbol":
        out = run_graph_cmd("trace", args.get("symbol", "").strip(), workspace)
        if print_output_fn:
            print_output_fn(out)
        return out

    if name == "blast_radius":
        out = run_graph_cmd("blast-radius", args.get("symbol", "").strip(), workspace)
        if print_output_fn:
            print_output_fn(out)
        return out

    if name == "find_symbol":
        out = run_graph_cmd("search", args.get("pattern", "").strip(), workspace)
        if print_output_fn:
            print_output_fn(out)
        return out

    if name == "architecture_overview":
        out = run_graph_cmd("architecture", "", workspace)
        if print_output_fn:
            print_output_fn(out)
        return out

    # 3. File System Tools
    if name == "read_file":
        if os.path.splitext(full)[1].lower() in BINARY_EXTENSIONS or os.path.isdir(
            full
        ):
            return f"[error] Refused to read binary file or directory '{raw_path}'."
        if not os.path.isfile(full):
            return f"[error] File not found: {raw_path}"
        if _is_outside_workspace(workspace, full) and not _gate(
            f"OUT-OF-BOUNDS READ: {full}"
        ):
            return denial
        if confirm_gate_fn and gates_active and not _gate(f"read file {raw_path}"):
            return denial

        _SESSION_READ_FILES.add(full)

        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            l_start = args.get("line_start")
            l_end = args.get("line_end")
            total_lines = len(lines)

            if l_start is not None or l_end is not None:
                start_idx = max(0, (int(l_start) - 1) if l_start else 0)
                end_idx = min(total_lines, int(l_end) if l_end else total_lines)
                sliced = lines[start_idx:end_idx]
                content = "".join(sliced)
                prefix = f"### File: {raw_path} (Lines {start_idx + 1}-{end_idx} of {total_lines})\n"
                res_out = prefix + content
            elif total_lines > 250:
                content = "".join(lines[:150])
                res_out = (
                    f"### File: {raw_path} (Lines 1-150 of {total_lines})\n"
                    + content
                    + f"\n\n... [Showing lines 1-150 of {total_lines}. Pass line_start and line_end to view more, or read_symbol(symbol) for specific functions]"
                )
            else:
                res_out = "".join(lines)[:15000]

            if print_output_fn:
                print_output_fn(res_out)
            return res_out
        except OSError as e:
            return f"[error] failed to read file: {e}"

    if name == "edit_file":
        if not os.path.isfile(full):
            return f"[error] File '{raw_path}' does not exist. Use write_file to create new files."
        if full not in _SESSION_READ_FILES and not bool(args.get("force", False)):
            return f"[error] You must inspect '{raw_path}' with read_file before calling edit_file to ensure your old_str matches exact lines and indentation."
        if _is_outside_workspace(workspace, full) and not _gate(
            f"OUT-OF-BOUNDS EDIT: {full}"
        ):
            return denial

        old_str = args.get("old_str", "")
        new_str = args.get("new_str", "")
        if not old_str:
            return "[error] Parameter 'old_str' cannot be empty."

        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()

            if old_str not in original:
                return f"[error] Target old_str not found in '{raw_path}'. Make sure you read the file first to match exact lines and indentation."

            if original.count(old_str) > 1:
                return f"[error] Target old_str matched multiple times in '{raw_path}'. Include more surrounding context lines in old_str to make it unique."

            new_content = original.replace(old_str, new_str, 1)

            if full.endswith(".py"):
                try:
                    ast.parse(new_content)
                except SyntaxError as e:
                    return f"[error] Edit blocked. Resulting Python syntax error: {e} on line {getattr(e, 'lineno', '?')}."
            elif full.endswith(".json"):
                try:
                    json.loads(new_content)
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    return f"[error] Edit blocked. Resulting JSON syntax error: {e}."

            if sys.stdout.isatty():
                if diff := "\n".join(
                    difflib.unified_diff(
                        original.splitlines(),
                        new_content.splitlines(),
                        fromfile=f"a/{raw_path}",
                        tofile=f"b/{raw_path}",
                        lineterm="",
                    )
                ):
                    _console_err.print(
                        "\n",
                        Syntax(
                            diff, "diff", theme="ansi_dark", background_color="default"
                        ),
                        "\n",
                    )

            if (
                confirm_gate_fn
                and gates_active
                and not _gate(f"surgically edit {raw_path}")
            ):
                return denial

            with open(full, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully edited {raw_path} (replaced {len(old_str)} chars with {len(new_str)} chars)."
        except OSError as e:
            return f"[error] failed to edit file: {e}"

    if name == "write_file":
        content = args.get("content", "")
        is_overwrite = bool(args.get("overwrite", False) or args.get("force", False))

        if os.path.exists(full) and not is_overwrite:
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    existing_len = len(f.read().splitlines())
                if existing_len > 0:
                    return f"[error] File '{raw_path}' already exists ({existing_len} lines). To make targeted changes, use edit_file(path, old_str, new_str). If you intend to overwrite the entire file, pass overwrite=true."
            except Exception:
                pass

        if full.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                return f"[error] Write blocked. Python syntax error: {e} on line {getattr(e, 'lineno', '?')}."
        elif full.endswith(".json"):
            try:
                json.loads(content)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                return f"[error] Write blocked. JSON syntax error: {e}."

        if sys.stdout.isatty() and os.path.exists(full):
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    old = f.read()
                if diff := "\n".join(
                    difflib.unified_diff(
                        old.splitlines(),
                        content.splitlines(),
                        fromfile=f"a/{raw_path}",
                        tofile=f"b/{raw_path}",
                        lineterm="",
                    )
                ):
                    _console_err.print(
                        "\n",
                        Syntax(
                            diff, "diff", theme="ansi_dark", background_color="default"
                        ),
                        "\n",
                    )
            except OSError:
                pass

        if _is_outside_workspace(workspace, full) and not _gate(
            f"OUT-OF-BOUNDS WRITE: {full}"
        ):
            return denial
        if (
            confirm_gate_fn
            and gates_active
            and not _gate(
                f"{'overwrite' if os.path.exists(full) else 'create'} {raw_path}"
            )
        ):
            return denial

        try:
            os.makedirs(os.path.dirname(full) or workspace, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            _SESSION_READ_FILES.add(full)
            return f"wrote {len(content)} chars to {raw_path}"
        except OSError as e:
            return f"[error] failed to write file: {e}"

    if name == "list_dir":
        if _is_outside_workspace(workspace, full) and not _gate(
            f"OUT-OF-BOUNDS LIST DIR: {full}"
        ):
            return denial
        if (
            confirm_gate_fn
            and gates_active
            and not _gate(f"list directory {raw_path or '.'}")
        ):
            return denial
        try:
            entries = sorted(os.listdir(full))
            res_str = (
                "\n".join(
                    (e + "/" if os.path.isdir(os.path.join(full, e)) else e)
                    for e in entries
                )
                or "(empty)"
            )
            if print_output_fn:
                print_output_fn(res_str)
            return res_str
        except OSError as e:
            return f"[error] failed to list files: {e}"

    # 4. Shell Execution
    if name == "run_command":
        cmd = args.get("command", "")
        expanded = cmd.replace("~", os.path.expanduser("~"))
        abs_paths = RE_ABS_PATH.findall(expanded)
        sys_prefixes = ("/bin/", "/usr/bin/", "/usr/local/bin/", "/sbin/", "/usr/sbin/")
        target_paths = [
            p for p in abs_paths if not any(p.startswith(sp) for sp in sys_prefixes)
        ]
        if (
            ".." in cmd
            or any(
                _is_outside_workspace(workspace, p)
                for p in target_paths
                if os.path.exists(p) or os.path.isabs(p)
            )
        ) and not _gate(f"OUT-OF-BOUNDS EXECUTION: $ {cmd}"):
            return denial

        if confirm_gate_fn and gates_active:
            if not sys.stdout.isatty():
                return "[denied] no terminal available to approve command execution"
            if not _gate(f"execute: $ {cmd}"):
                return denial

        shell = os.environ.get("SHELL") or "/bin/sh"
        try:
            res = subprocess.run(
                [shell, "-lc", cmd],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=300,
            )
            out = (
                (res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")
            ).strip()[:10000]
            if print_output_fn:
                print_output_fn(out)
            return (
                f"(exit {res.returncode})\n{out}"
                if res.returncode != 0
                else (out or "(exit 0, no output)")
            )
        except subprocess.TimeoutExpired:
            return "[error] command timed out after 300 seconds"
        except OSError as e:
            return f"[error] failed to run command: {e}"

    return f"[error] unknown tool {name}"
