#!/usr/bin/env python3
"""Local-AI Standalone IPython Kernel & RLM Harness Module [In-Memory Edition]"""

import ast
import contextlib
import io
import os
import subprocess
import sys
import traceback
from collections.abc import Callable
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
sys.path.append(os.path.join(CFG_DIR, "modules"))

try:
    import agent_core as core
    import agent_memories as memories
    import agent_tools as tools
except ImportError:
    core = None
    memories = None
    tools = None

_shell_globals: dict[str, Any] = {}
_shell_instance = None

try:
    from IPython.core.interactiveshell import InteractiveShell

    _has_ipython = True
except ImportError:
    _has_ipython = False


def is_ipython_enabled() -> bool:
    return core.get_state().get("ipython_mode", False) if core else False


def toggle_ipython_mode(enable: bool | None = None) -> bool:
    new_st = (not is_ipython_enabled()) if enable is None else enable
    if core:
        core.save_state("ipython_mode", new_st)
    return new_st


_orig_open = open
_orig_listdir = os.listdir
_confirm_gate_fn = None


def bounded_repr(val: Any, max_len: int = 1200) -> str:
    """NOOA-inspired bounded preview generator."""
    if val is None:
        return "None"
    if hasattr(val, "shape") and hasattr(val, "head"):
        try:
            return f"<DataFrame shape={val.shape}>\n{val.head(5)}"
        except Exception:
            pass
    if isinstance(val, (list, tuple, set)) and len(val) > 20:
        sample = list(val)[:3]
        if sample and isinstance(sample[0], (list, tuple, set)):
            sample_sub = [list(sub)[:3] for sub in sample]
            return f"<{type(val).__name__} len={len(val)} shape=({len(val)}, {len(sample[0]) if hasattr(sample[0], '__len__') else '?'}) preview={sample_sub} ...>"
        return f"<{type(val).__name__} len={len(val)} preview={sample} ...>"
    if isinstance(val, dict) and len(val) > 20:
        return f"<dict keys_count={len(val)} preview_keys={list(val.keys())[:5]} ...>"

    s = str(val).strip()
    if len(s) > max_len:
        lines = s.splitlines()
        head = "\n".join(lines[:15]) if len(lines) > 15 else s[: max_len // 2]
        return f"{head}\n... [Bounded Preview: Snipped {len(s) - len(head)} chars. Live object remains in kernel RAM]"
    return s


class MemorySDK:
    """Direct in-memory model-callable Harness API for TPM."""

    def __init__(self, workspace: str, safe_name: str):
        self.workspace, self.safe_name = workspace, safe_name

    def search(self, query: str) -> str:
        if memories:
            return (
                memories.search_past_context(self.safe_name, query)
                or "No matching memories found."
            )
        return "Memory module unavailable."

    def get_facts(self) -> str:
        if memories:
            return memories.tpm_get(self.safe_name) or "No facts stored."
        return "Memory module unavailable."

    def add_fact(self, key: str, value: str) -> str:
        if memories:
            memories.tpm_reconcile(
                self.safe_name, {key.strip().lower(): str(value).strip()}
            )
            return f"Fact reconciled: {key} = {value}"
        return "Memory module unavailable."


class GraphSDK:
    """Direct in-memory model-callable Harness API for Codebase Index Graph."""

    def __init__(self, workspace: str):
        self.workspace = workspace

    def snippet(self, symbol: str) -> str:
        return (
            tools.run_graph_cmd("snippet", symbol, self.workspace)
            if tools
            else "Tools module unavailable."
        )

    def trace(self, symbol: str) -> str:
        return (
            tools.run_graph_cmd("trace", symbol, self.workspace)
            if tools
            else "Tools module unavailable."
        )

    def blast_radius(self, symbol: str) -> str:
        return (
            tools.run_graph_cmd("blast-radius", symbol, self.workspace)
            if tools
            else "Tools module unavailable."
        )

    def search(self, pattern: str) -> str:
        return (
            tools.run_graph_cmd("search", pattern, self.workspace)
            if tools
            else "Tools module unavailable."
        )

    def architecture(self) -> str:
        return (
            tools.run_graph_cmd("architecture", "", self.workspace)
            if tools
            else "Tools module unavailable."
        )


def delegate(goal: str, workspace: str = ".") -> str:
    """NOOA-inspired Sub-Agent Delegation."""
    try:
        ws_real = os.path.realpath(workspace)
        sub_history = [
            {
                "role": "system",
                "content": f"You are an isolated sub-agent worker in workspace '{ws_real}'.\nGoal: {goal}\nExecute required tool operations to complete the goal, then output ONLY a concise final summary report.",
            },
            {"role": "user", "content": f"Execute sub-task: {goal}"},
        ]
        ans = (
            core.stream_response(
                sub_history,
                prefix="SubAgent:",
                show_stats=False,
                thinking_budget=0,
                is_agent=True,
            )
            if core
            else None
        )
        return (ans or "Sub-agent completed task.").strip()
    except Exception as e:
        return f"[error] Sub-agent delegation failed: {e}"


def _init_kernel_sdk(
    workspace: str, confirm_gate_fn: Callable[[str], bool] | None = None
) -> None:
    global _shell_globals, _shell_instance, _confirm_gate_fn
    if confirm_gate_fn:
        _confirm_gate_fn = confirm_gate_fn
    ws_real = os.path.realpath(workspace)

    try:
        os.chdir(ws_real)
    except OSError:
        pass

    if ws_real not in sys.path:
        sys.path.insert(0, ws_real)

    if _has_ipython and _shell_instance is None:
        _shell_instance = InteractiveShell.instance()

    def _is_outside(path_str: str) -> bool:
        full = os.path.realpath(
            path_str if os.path.isabs(path_str) else os.path.join(ws_real, path_str)
        )
        return full != ws_real and not full.startswith(ws_real + os.sep)

    def _check_boundary(path_str: str, op_name: str) -> bool:
        full = os.path.realpath(
            path_str if os.path.isabs(path_str) else os.path.join(ws_real, path_str)
        )
        if _is_outside(full):
            if _confirm_gate_fn:
                return _confirm_gate_fn(f"OUT-OF-BOUNDS KERNEL {op_name}: {full}")
            if core:
                return core._confirm_gate(
                    f"OUT-OF-BOUNDS KERNEL {op_name}: {full}", None
                )
        return True

    def safe_open(file, mode="r", *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            if not _check_boundary(str(file), "READ" if "r" in mode else "WRITE"):
                raise PermissionError(f"[denied] Out-of-bounds access blocked: {file}")
        return _orig_open(file, mode, *args, **kwargs)

    def safe_listdir(path="."):
        if not _check_boundary(str(path), "LIST DIR"):
            raise PermissionError(f"[denied] Out-of-bounds list_dir blocked: {path}")
        full = os.path.realpath(
            str(path) if os.path.isabs(str(path)) else os.path.join(ws_real, str(path))
        )
        return _orig_listdir(full)

    def _read_file(path: str) -> str:
        if not _check_boundary(path, "READ"):
            return "[denied] Out-of-bounds read blocked."
        return (
            tools.run_tool(
                "read_file", {"path": path}, ws_real, confirm_gate_fn=_confirm_gate_fn
            )
            if tools
            else ""
        )

    def _edit_file(path: str, old_str: str, new_str: str) -> str:
        if not _check_boundary(path, "EDIT"):
            return "[denied] Out-of-bounds edit blocked."
        return (
            tools.run_tool(
                "edit_file",
                {"path": path, "old_str": old_str, "new_str": new_str},
                ws_real,
                confirm_gate_fn=_confirm_gate_fn,
            )
            if tools
            else ""
        )

    def _write_file(path: str, content: str, overwrite: bool = False) -> str:
        if not _check_boundary(path, "WRITE"):
            return "[denied] Out-of-bounds write blocked."
        return (
            tools.run_tool(
                "write_file",
                {"path": path, "content": content, "overwrite": overwrite},
                ws_real,
                confirm_gate_fn=_confirm_gate_fn,
            )
            if tools
            else ""
        )

    def _list_dir(path: str = ".") -> list[str]:
        if not _check_boundary(path, "LIST DIR"):
            return ["[denied] Out-of-bounds list_dir blocked."]
        full = os.path.realpath(
            path if os.path.isabs(path) else os.path.join(ws_real, path)
        )
        return sorted(_orig_listdir(full))

    def _run_command(cmd: str) -> str:
        res = subprocess.run(
            cmd, shell=True, cwd=ws_real, capture_output=True, text=True, timeout=120
        )
        return ((res.stdout or "") + ("\n" + res.stderr if res.stderr else "")).strip()

    safe_name = os.path.basename(ws_real)
    mem_sdk = MemorySDK(ws_real, safe_name)
    graph_sdk = GraphSDK(ws_real)

    def _delegate(goal: str) -> str:
        return delegate(goal, ws_real)

    sdk = {
        "open": safe_open,
        "read_file": _read_file,
        "edit_file": _edit_file,
        "write_file": _write_file,
        "list_dir": _list_dir,
        "run_command": _run_command,
        "read_symbol": graph_sdk.snippet,
        "trace_symbol": graph_sdk.trace,
        "blast_radius": graph_sdk.blast_radius,
        "find_symbol": graph_sdk.search,
        "architecture_overview": graph_sdk.architecture,
        "preview": bounded_repr,
        "bounded_repr": bounded_repr,
        "memory": mem_sdk,
        "graph": graph_sdk,
        "delegate": _delegate,
        "workspace": ws_real,
    }
    _shell_globals.update(sdk)
    os.listdir = safe_listdir
    if _shell_instance:
        _shell_instance.user_ns.update(sdk)


def inspect_ast_safety(
    code: str, workspace: str, confirm_gate_fn: Callable[[str], bool] | None = None
) -> str | None:
    if not confirm_gate_fn or os.environ.get("AI_CONFIRM_GATES", "1") == "0":
        return None
    clean = code.strip()
    if clean.startswith(("%", "!", "?")):
        if clean.startswith("!"):
            if not confirm_gate_fn(f"PYTHON SHELL ESCAPE: {clean[:40]}"):
                return "[denied] Execution halted by user gate."
        return None

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn_name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
                if fn_name in (
                    "run_command",
                    "system",
                    "Popen",
                    "exec",
                    "eval",
                    "remove",
                    "rmtree",
                ):
                    if not confirm_gate_fn(
                        f"PYTHON KERNEL: {fn_name}() cell execution"
                    ):
                        return "[denied] Execution halted by user gate."
    except SyntaxError as e:
        return f"[error] Python syntax error in code cell: {e}"
    return None


def run_cell(
    code: str, workspace: str, confirm_gate_fn: Callable[[str], bool] | None = None
) -> str:
    _init_kernel_sdk(workspace, confirm_gate_fn)
    if denial := inspect_ast_safety(code, workspace, confirm_gate_fn):
        return denial

    stdout_buf = io.StringIO()
    eval_result = None
    try:
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stdout_buf),
        ):
            if _shell_instance:
                res = _shell_instance.run_cell(code, store_history=True)
                if res.error_in_exec:
                    traceback.print_exception(
                        type(res.error_in_exec),
                        res.error_in_exec,
                        res.error_in_exec.__traceback__,
                    )
                elif hasattr(res, "result") and res.result is not None:
                    eval_result = res.result
            else:
                try:
                    eval_result = eval(code, _shell_globals)
                except SyntaxError:
                    exec(code, _shell_globals)

        out = stdout_buf.getvalue().strip()
        if not out and eval_result is not None:
            out = bounded_repr(eval_result)
        elif out:
            out = bounded_repr(out)
        return out or "(Cell executed successfully with no output)"
    except PermissionError as e:
        return f"[denied] {e}"
    except Exception as e:
        err_msg = str(e).strip().split("\n")[0]
        return f"[error] Cell execution failed: {err_msg}"


IPYTHON_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "exec_python",
            "description": "Execute Python code in the live persistent kernel. Data, variables, and imports stay in memory across cells.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code cell to execute.",
                    }
                },
                "required": ["code"],
            },
        },
    }
]


def get_active_tools() -> list[dict[str, Any]]:
    return IPYTHON_TOOL if is_ipython_enabled() else getattr(core, "EDIT_TOOLS", [])
