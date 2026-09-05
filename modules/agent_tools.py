#!/usr/bin/env python3
"""Native Tool Engine - Handles file editing, search, commands, & graph intelligence"""

import ast
import difflib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
from collections.abc import Callable
from typing import Any

import agent_ui as ui
from rich.console import Console
from rich.syntax import Syntax

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
_console_err = Console(stderr=True)

BINARY_EXTENSIONS = frozenset({
    ".db", ".sqlite", ".sqlite3", ".bin", ".pyc", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz", ".7z",
    ".pdf", ".docx", ".xlsx", ".db-wal", ".db-shm", ".pyo", ".pyd"
})

EXCLUDED_SEARCH_DIRS = frozenset({
    ".git", ".agent", "__pycache__", ".pytest_cache", "node_modules",
    ".venv", "venv", "env", "dist", "build", ".mypy_cache", ".ruff_cache"
})

FORBIDDEN_GLOBAL_COMMANDS = frozenset({
    "sudo", "doas", "su", "pkexec",
    "pip", "pip3", "pipx", "yay", "paru", "apt", "apt-get", "dnf", "yum", "brew",
    "npm", "pnpm", "yarn", "gem", "cargo", "rustup", "go",
    "reboot", "shutdown", "poweroff",
    "useradd", "usermod", "userdel", "passwd",
})

# Safe read-only inspection subcommands that do not mutate host state
READONLY_INSPECTION_SUBCOMMANDS = {
    "systemctl": frozenset({
        "status", "is-active", "is-enabled", "is-failed",
        "list-units", "list-unit-files", "list-timers", "list-sockets", "show", "cat"
    }),
    "pacman": frozenset({
        "-q", "-qi", "-ql", "-qs", "-qk", "-qo", "-qm", "-qu", "--query"
    }),
}

FORBIDDEN_SYS_DIRS = (
    "/etc", "/usr", "/var", "/bin", "/sbin", "/opt", "/root", "/boot", "/sys", "/proc", "/dev"
)

RE_ABS_PATH = re.compile(r"/(?:[a-zA-Z0-9_\-\.]+/)*[a-zA-Z0-9_\-\.]*")

# In-Memory Session State
_SESSION_READ_FILES: set[str] = set()
_SESSION_MODIFIED_FILES: set[str] = set()


def get_modified_files() -> list[str]:
    """Returns sorted list of relative paths modified in the active session."""
    return sorted(_SESSION_MODIFIED_FILES)


def clear_session_tracking() -> None:
    """Resets session file tracking state."""
    _SESSION_READ_FILES.clear()
    _SESSION_MODIFIED_FILES.clear()


# Complete 12-Tool Suite
EDIT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": n,
            "description": d,
            "parameters": {
                "type": "object",
                "properties": p,
                "required": r,
                "additionalProperties": False
            },
        },
    }
    for n, d, p, r in [
        (
            "delegate_task",
            "Delegate an isolated sub-task or research query to a temporary sandbox sub-agent. Returns only a concise summary report to keep context clean.",
            {"goal": {"type": "string", "description": "Specific isolated sub-task or code research objective."}},
            ["goal"],
        ),
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
            "search_code",
            "Search for text or regex pattern across workspace files. Returns matching files, line numbers, and previews without shell execution.",
            {
                "pattern": {"type": "string", "description": "Text string or regular expression to search for."},
                "path": {"type": "string", "description": "Relative directory or file path to search within. Defaults to '.' (workspace root)."}
            },
            ["pattern"],
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
                "old_str": {"type": "string", "description": "Exact text to find and replace."},
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
                "overwrite": {"type": "boolean", "description": "Set true to confirm overwriting an existing file."},
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

# Lean 7-Tool Set for Compact Models (2B, 7B, 8B, 14B)
LEAN_TOOLS: list[dict[str, Any]] = [
    t for t in EDIT_TOOLS if t["function"]["name"] in ("read_file", "search_code", "edit_file", "write_file", "list_dir", "run_command", "delegate_task")
]

TOOL_VERBS = {
    "delegate_task": "delegating sub-task",
    "read_symbol": "tracing symbol snippet",
    "trace_symbol": "tracing call graph",
    "blast_radius": "calculating impact",
    "find_symbol": "searching graph",
    "architecture_overview": "mapping architecture",
    "search_code": "searching codebase",
    "read_file": "checking",
    "edit_file": "surgically editing",
    "write_file": "updating",
    "list_dir": "checking",
    "run_command": "executing",
    "web_search": "searching Google",
}

WEB_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search live Google Search via Gemini Grounding for current facts, latest documentation, releases, or solutions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Dense keyword search query."}
            },
            "required": ["query"],
        },
    },
}

_graph_module = None


def _get_graph_engine():
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
    if not p:
        return os.path.realpath(workspace)
    clean_p = os.path.expanduser(urllib.parse.unquote(str(p).strip().strip('\'"`\\\n\r\t ')))
    ws_real = os.path.realpath(workspace)
    if clean_p.startswith("/") and not clean_p.startswith(ws_real):
        rel_candidate = clean_p.lstrip("/")
        if os.path.exists(os.path.join(ws_real, rel_candidate)) or "/" not in rel_candidate:
            clean_p = rel_candidate
    return os.path.realpath(clean_p if os.path.isabs(clean_p) else os.path.join(ws_real, clean_p))


def _is_outside_workspace(workspace: str, full_path: str) -> bool:
    if not full_path:
        return False
    root = os.path.realpath(workspace)
    return full_path != root and not full_path.startswith(root + os.sep)


def _check_command_security(cmd: str, workspace: str) -> str | None:
    """Detects if a shell command targets system packages or paths outside workspace."""
    if not cmd or not cmd.strip():
        return "Empty command"
    clean_cmd = cmd.strip()
    root_ws = os.path.realpath(workspace)

    sub_cmds = re.split(r"[;&|]+", clean_cmd)
    for sub in sub_cmds:
        sub_strip = sub.strip()
        if not sub_strip:
            continue
        try:
            tokens = shlex.split(sub_strip)
        except ValueError:
            tokens = sub_strip.split()
        if not tokens:
            continue

        binary = os.path.basename(tokens[0]).lower()

        # Handle systemctl read-only vs mutating commands
        if binary == "systemctl":
            sub_actions = [t.lower() for t in tokens[1:] if not t.startswith("-")]
            if sub_actions and sub_actions[0] in READONLY_INSPECTION_SUBCOMMANDS["systemctl"]:
                pass  # Read-only inspection allowed
            else:
                return f"Privileged or mutating systemctl action: '{' '.join(tokens[:2])}'"

        # Handle pacman read-only queries vs package install/removal
        elif binary == "pacman":
            action_flags = [t.lower() for t in tokens[1:] if t.startswith("-")]
            if action_flags and any(any(f.startswith(rf) for rf in READONLY_INSPECTION_SUBCOMMANDS["pacman"]) for f in action_flags):
                pass  # Read-only package query allowed
            else:
                return f"Package manager modification: '{' '.join(tokens[:2])}'"

        # Handle journalctl (read-only unless vacuuming/rotating)
        elif binary == "journalctl":
            if any(t.startswith(("--vacuum", "--rotate")) for t in tokens):
                return f"Journal maintenance command: '{' '.join(tokens)}'"
            pass  # Standard journal log inspection allowed

        elif binary in FORBIDDEN_GLOBAL_COMMANDS:
            return f"Global system/package binary: '{binary}'"

        for t in tokens:
            for sys_dir in FORBIDDEN_SYS_DIRS:
                if t == sys_dir or t.startswith(f"{sys_dir}/"):
                    return f"System directory reference: '{t}'"

        for t in tokens:
            if ".." in t or t.startswith("~/") or t.startswith("/"):
                exp = os.path.realpath(os.path.expanduser(t))
                if (os.path.exists(exp) or t.startswith("/home/")) and _is_outside_workspace(root_ws, exp):
                    return f"Path outside workspace: '{t}'"

    return None


def _search_codebase(pattern: str, search_root: str, workspace: str, max_results: int = 30) -> str:
    """Fast, sandboxed regex and string search across workspace text files."""
    if not pattern or not pattern.strip():
        return "[error] Parameter 'pattern' cannot be empty."

    target_path = _safe_path(workspace, search_root)
    if _is_outside_workspace(workspace, target_path):
        return f"[denied] Search path '{search_root}' is outside workspace."

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    matches = []
    files_searched = 0

    if os.path.isfile(target_path):
        scan_files = [target_path]
    else:
        scan_files = []
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_SEARCH_DIRS and not d.startswith(".")]
            for f in files:
                if os.path.splitext(f)[1].lower() not in BINARY_EXTENSIONS and not f.startswith("."):
                    scan_files.append(os.path.join(root, f))

    for fpath in scan_files:
        files_searched += 1
        rel_path = os.path.relpath(fpath, workspace)
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, start=1):
                    if regex.search(line):
                        clean_line = line.rstrip("\r\n")
                        preview = clean_line[:120] + ("..." if len(clean_line) > 120 else "")
                        matches.append(f"{rel_path}:{line_idx}: {preview}")
                        if len(matches) >= max_results:
                            break
        except OSError:
            continue
        if len(matches) >= max_results:
            break

    if not matches:
        return f"[search_code] No matches found for pattern '{pattern}' across {files_searched} files."

    res = f"### Code Search: '{pattern}' ({len(matches)} matches in {files_searched} files):\n" + "\n".join(matches)
    if len(matches) >= max_results:
        res += f"\n\n... [Showing first {max_results} matches. Narrow pattern or search specific subdirectories for more]"
    return res


def _generate_ast_skeleton(code: str, file_path: str) -> str:
    lines = code.splitlines()
    total_lines = len(lines)

    if file_path.endswith(".py"):
        try:
            tree = ast.parse(code)
            skeleton = []

            imports = []
            for node in tree.body:
                if isinstance(node, ast.Import):
                    names = ", ".join(a.name for a in node.names)
                    imports.append(f"import {names}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    names = ", ".join(a.name for a in node.names)
                    imports.append(f"from {mod} import {names}")

            if imports:
                skeleton.append("# --- Imports ---")
                skeleton.extend(imports[:15])
                if len(imports) > 15:
                    skeleton.append(f"# ... ({len(imports) - 15} more imports)")
                skeleton.append("")

            skeleton.append("# --- Structure & Line Spans ---")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                    doc = ast.get_docstring(node)
                    doc_preview = f"  # {doc.splitlines()[0][:60]}" if doc else ""
                    skeleton.append(f"{prefix} {node.name}(...):  # Lines {node.lineno}-{node.end_lineno}{doc_preview}")
                elif isinstance(node, ast.ClassDef):
                    bases = ", ".join(ast.unparse(b) for b in node.bases) if hasattr(ast, "unparse") and node.bases else ""
                    base_str = f"({bases})" if bases else ""
                    skeleton.append(f"class {node.name}{base_str}:  # Lines {node.lineno}-{node.end_lineno}")
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            sub_prefix = "async def" if isinstance(sub, ast.AsyncFunctionDef) else "def"
                            sub_doc = ast.get_docstring(sub)
                            sub_doc_preview = f"  # {sub_doc.splitlines()[0][:50]}" if sub_doc else ""
                            skeleton.append(f"    {sub_prefix} {sub.name}(...):  # Lines {sub.lineno}-{sub.end_lineno}{sub_doc_preview}")

            body = "\n".join(skeleton)
            return (
                f"### File Skeleton: {file_path} ({total_lines} lines)\n"
                f"{body}\n\n"
                f"... [File is {total_lines} lines long. Use read_file('{file_path}', line_start=X, line_end=Y) to inspect specific blocks or read_symbol('name')]"
            )
        except Exception:
            pass

    preview = "\n".join(lines[:100])
    return (
        f"### File Preview: {file_path} (Showing lines 1-100 of {total_lines})\n"
        f"{preview}\n\n"
        f"... [File is {total_lines} lines long. Use read_file('{file_path}', line_start=X, line_end=Y) to inspect target lines]"
    )


def _resilient_replace(original: str, old_str: str, new_str: str) -> tuple[str | None, str | None]:
    """3-Stage resilient file replacement: Exact match -> Whitespace normalized -> SequenceMatcher fuzzy fallback."""
    if old_str in original:
        if original.count(old_str) > 1:
            return None, "Target old_str matched multiple times in file. Include more surrounding context lines to make it unique."
        return original.replace(old_str, new_str, 1), None

    orig_text = original.replace("\r\n", "\n")
    clean_old = old_str.replace("\r\n", "\n").strip("\n")
    clean_new = new_str.replace("\r\n", "\n")

    orig_lines = orig_text.splitlines(keepends=True)
    old_lines = clean_old.splitlines()
    if not old_lines:
        return None, "Parameter 'old_str' cannot be empty."

    norm_old = [re.sub(r"\s+", " ", l.strip()) for l in old_lines if l.strip()]
    old_len = len(norm_old)
    if old_len == 0:
        return None, "Parameter 'old_str' contains no non-whitespace content."

    matches = []
    for i in range(len(orig_lines)):
        window_lines = []
        window_raw_indices = []
        for j in range(i, len(orig_lines)):
            line_str = orig_lines[j]
            if line_str.strip():
                window_lines.append(re.sub(r"\s+", " ", line_str.strip()))
                window_raw_indices.append(j)
                if len(window_lines) == old_len:
                    break
        if window_lines == norm_old:
            start_idx = window_raw_indices[0]
            end_idx = window_raw_indices[-1] + 1
            matches.append((start_idx, end_idx))

    if len(matches) == 1:
        start_idx, end_idx = matches[0]
        orig_first_line = orig_lines[start_idx]
        orig_indent_len = len(orig_first_line) - len(orig_first_line.lstrip(" "))
        old_first_line = old_lines[0]
        old_indent_len = len(old_first_line) - len(old_first_line.lstrip(" "))
        indent_delta = orig_indent_len - old_indent_len

        new_lines_raw = clean_new.splitlines()
        adjusted_new_lines = []
        for nl in new_lines_raw:
            if not nl.strip():
                adjusted_new_lines.append("\n")
            elif indent_delta > 0:
                adjusted_new_lines.append(" " * indent_delta + nl + "\n")
            elif indent_delta < 0 and nl.startswith(" " * abs(indent_delta)):
                adjusted_new_lines.append(nl[abs(indent_delta):] + "\n")
            else:
                adjusted_new_lines.append(nl + "\n")

        reconstructed = "".join(orig_lines[:start_idx]) + "".join(adjusted_new_lines) + "".join(orig_lines[end_idx:])
        return reconstructed, None
    elif len(matches) > 1:
        return None, f"Whitespace-normalized old_str matched {len(matches)} locations. Include more surrounding lines to make it unique."

    best_ratio = 0.0
    best_window = None
    old_block_str = "\n".join(norm_old)

    for i in range(len(orig_lines) - old_len + 1):
        cand_lines = [re.sub(r"\s+", " ", orig_lines[k].strip()) for k in range(i, i + old_len) if orig_lines[k].strip()]
        cand_block_str = "\n".join(cand_lines)
        ratio = difflib.SequenceMatcher(None, old_block_str, cand_block_str).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_window = (i, i + old_len)

    if best_ratio >= 0.88 and best_window is not None:
        start_idx, end_idx = best_window
        reconstructed = "".join(orig_lines[:start_idx]) + clean_new + ("\n" if not clean_new.endswith("\n") else "") + "".join(orig_lines[end_idx:])
        return reconstructed, None

    return None, "Target old_str not found in file (even with whitespace tolerance and fuzzy matching). Use read_file to inspect exact lines."


def run_graph_cmd(cmd: str, arg: str, workspace: str) -> str:
    """Executes graph query commands against index-map SQLite graph."""
    script = os.path.join(CFG_DIR, "tools", "index-map", "index-map")
    if not os.path.exists(script):
        return "[error] index-map script not found."
    cmd_args = [sys.executable, script, cmd]
    if arg:
        cmd_args.append(arg)
    cmd_args.append(workspace)
    try:
        res = subprocess.run(cmd_args, cwd=workspace, capture_output=True, text=True, timeout=15)
        out = (res.stdout or res.stderr or "").strip()
        return out or "(No graph data available)"
    except Exception as e:
        return f"[error] Graph command '{cmd}' failed: {e}"


# ── Core Tool Dispatcher ──────────────────────────────────────────────────────
def run_tool(
    name: str,
    args: dict[str, Any],
    workspace: str,
    confirm_gate_fn: Callable[[str], bool] | None = None,
    print_output_fn: Callable[[str], None] | None = None,
) -> str:
    if isinstance(args, dict):
        for k in ("path", "command", "pattern", "symbol", "goal"):
            if k in args and isinstance(args[k], str):
                args[k] = args[k].strip().strip('\'"`\\\n\r\t ').strip()

        if "path" not in args:
            for alt in ("file", "filename", "filepath", "target", "file_path"):
                if alt in args:
                    args["path"] = args[alt]
                    break
        if "command" not in args:
            for alt in ("cmd", "exec", "shell_command", "script"):
                if alt in args:
                    args["command"] = args[alt]
                    break
        if "content" not in args:
            for alt in ("text", "code", "body", "data"):
                if alt in args:
                    args["content"] = args[alt]
                    break
        if "pattern" not in args:
            for alt in ("query", "regex", "search_term", "find"):
                if alt in args:
                    args["pattern"] = args[alt]
                    break

    gates_active = os.environ.get("AI_CONFIRM_GATES", "1") == "1"
    raw_path = args.get("path", "")
    full = _safe_path(workspace, raw_path)

    def _in_bounds_gate(reason: str) -> bool:
        if confirm_gate_fn and gates_active:
            return confirm_gate_fn(reason)
        return True

    def _security_gate(reason: str) -> bool:
        if confirm_gate_fn:
            return confirm_gate_fn(reason)
        return ui.confirm_tool(reason)

    # 1. Isolated Sandbox Sub-Agent Delegation with Recursion Guard
    if name == "delegate_task":
        goal = args.get("goal", "").strip()
        if not goal:
            return "[error] Parameter 'goal' cannot be empty."
        if not _in_bounds_gate(f"delegate sub-task: '{goal[:80]}'"):
            return "[denied] User declined sub-agent delegation."

        current_depth = int(os.environ.get("AI_SUBAGENT_DEPTH", "0"))
        if current_depth >= 1:
            return "[error] Sub-agents cannot recursively delegate tasks. Execute the tools directly."

        try:
            os.environ["AI_SUBAGENT_DEPTH"] = str(current_depth + 1)
            import agent_core as core
            sub_history = [
                {
                    "role": "system",
                    "content": (
                        f"You are an isolated sub-agent worker in workspace '{workspace}'.\n"
                        f"Goal: {goal}\n"
                        "Execute direct tools (read_file, search_code, list_dir, run_command) to complete the goal. "
                        "When finished, output ONLY a concise final summary report."
                    ),
                },
                {"role": "user", "content": f"Execute sub-task: {goal}"},
            ]
            ans = core.stream_response(sub_history, prefix="SubAgent:", show_stats=False, thinking_budget=0, is_agent=True)
            return (ans or "Sub-agent completed task with no output.").strip()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            return f"[error] Sub-agent delegation failed: {e}"
        finally:
            os.environ["AI_SUBAGENT_DEPTH"] = str(current_depth)

    # 2. IPython Kernel Execution
    if name == "exec_python":
        try:
            import agent_ipython as ipython
            code_str = args.get("code") or args.get("content") or args.get("cell") or args.get("script") or ""
            out = ipython.run_cell(code_str, workspace, confirm_gate_fn)
            if print_output_fn:
                print_output_fn(out)
            return out
        except Exception as e:
            return f"[error] Python kernel execution failed: {e}"

    # 3. Graph Intelligence Tools
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

    # 4. Codebase Search
    if name == "search_code":
        pattern = args.get("pattern", "")
        search_root = args.get("path", ".")
        out = _search_codebase(pattern, search_root, workspace)
        if print_output_fn:
            print_output_fn(out)
        return out

    # 5. File System Tools
    if name == "read_file":
        if os.path.isdir(full):
            return f"[error] '{raw_path or '.'}' is a directory, not a file. Use list_dir('{raw_path or '.'}') to view files, or pass a file path."
        if os.path.splitext(full)[1].lower() in BINARY_EXTENSIONS:
            return f"[error] Refused to read binary file '{raw_path}'."
        if not os.path.isfile(full):
            return f"[error] File not found: {raw_path}"

        if _is_outside_workspace(workspace, full):
            if not _security_gate(f"OUT-OF-BOUNDS READ: {full}"):
                return f"[denied] User declined read of '{raw_path}' outside workspace."
        elif not _in_bounds_gate(f"read file {raw_path}"):
            return f"[denied] User declined read of '{raw_path}'."

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
                res_out = _generate_ast_skeleton("".join(lines), raw_path)
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

        if _is_outside_workspace(workspace, full):
            if not _security_gate(f"OUT-OF-BOUNDS EDIT: {full}"):
                return f"[denied] User declined edit of '{raw_path}' outside workspace."
        elif not _in_bounds_gate(f"surgically edit {raw_path}"):
            return f"[denied] User declined edit of '{raw_path}'."

        old_str = args.get("old_str", "")
        new_str = args.get("new_str", "")
        if not old_str:
            return "[error] Parameter 'old_str' cannot be empty."

        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()

            new_content, err_msg = _resilient_replace(original, old_str, new_str)
            if err_msg or new_content is None:
                return f"[error] {err_msg}"

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
                        Syntax(diff, "diff", theme="ansi_dark", background_color="default"),
                        "\n",
                    )

            with open(full, "w", encoding="utf-8") as f:
                f.write(new_content)

            rel_f = os.path.relpath(full, workspace)
            _SESSION_MODIFIED_FILES.add(rel_f)

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
                        Syntax(diff, "diff", theme="ansi_dark", background_color="default"),
                        "\n",
                    )
            except OSError:
                pass

        if _is_outside_workspace(workspace, full):
            if not _security_gate(f"OUT-OF-BOUNDS WRITE: {full}"):
                return f"[denied] User declined write to '{raw_path}' outside workspace."
        elif not _in_bounds_gate(f"{'overwrite' if os.path.exists(full) else 'create'} {raw_path}"):
            return f"[denied] User declined write to '{raw_path}'."

        try:
            os.makedirs(os.path.dirname(full) or workspace, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            _SESSION_READ_FILES.add(full)
            rel_f = os.path.relpath(full, workspace)
            _SESSION_MODIFIED_FILES.add(rel_f)
            return f"wrote {len(content)} chars to {raw_path}"
        except OSError as e:
            return f"[error] failed to write file: {e}"

    if name == "list_dir":
        if _is_outside_workspace(workspace, full):
            if not _security_gate(f"OUT-OF-BOUNDS LIST DIR: {full}"):
                return f"[denied] User declined list_dir of '{raw_path}' outside workspace."
        elif not _in_bounds_gate(f"list directory {raw_path or '.'}"):
            return f"[denied] User declined list_dir of '{raw_path}'."

        try:
            entries = sorted(os.listdir(full))
            res_str = "\n".join((e + "/" if os.path.isdir(os.path.join(full, e)) else e) for e in entries) or "(empty)"
            if print_output_fn:
                print_output_fn(res_str)
            return res_str
        except OSError as e:
            return f"[error] failed to list files: {e}"

    if name == "web_search":
        q = args.get("query", "").strip()
        if not q:
            return "[error] Parameter 'query' cannot be empty."
        if not _in_bounds_gate(f"search Google for: '{q}'"):
            return "[denied] User declined web search."
        try:
            import agent_core
            configs = agent_core.agent_cloud.get_active_configs([])
            gem_key = next((c[1].get("x-goog-api-key") or "" for c in configs if "generativelanguage" in c[0]), "")
            if not gem_key:
                gem_key = os.environ.get("GEM_API_KEY", "")
            if not gem_key:
                return "[error] Google search requires GEM_API_KEY."
            payload = {"contents": [{"parts": [{"text": f"Search the web and provide concise facts for: {q}"}]}], "tools": [{"googleSearch": {}}]}
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gem_key}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            res = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            out = res.strip() or "(No search results found)"
            if print_output_fn:
                print_output_fn(out)
            return out
        except Exception as e:
            return f"[error] Web search failed: {e}"

    if name == "run_command":
        cmd = args.get("command", "")

        if sec_reason := _check_command_security(cmd, workspace):
            if not _security_gate(f"OUT-OF-BOUNDS EXECUTION: $ {cmd} ({sec_reason})"):
                return f"[denied] User declined command execution: {cmd}"
        elif not _in_bounds_gate(f"execute: $ {cmd}"):
            return f"[denied] User declined command execution: {cmd}"

        shell = os.environ.get("SHELL") or "/bin/sh"
        try:
            res = subprocess.run([shell, "-lc", cmd], cwd=workspace, capture_output=True, text=True, timeout=300)
            out = ((res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")).strip()[:10000]
            if print_output_fn:
                print_output_fn(out)
            return f"(exit {res.returncode})\n{out}" if res.returncode != 0 else (out or "(exit 0, no output)")
        except subprocess.TimeoutExpired:
            return "[error] command timed out after 300 seconds"
        except OSError as e:
            return f"[error] failed to run command: {e}"

    return f"[error] unknown tool {name}"
