#!/usr/bin/env python3
"""Zero-Trust Security & Boundary Enforcement Kernel [Production Ready]"""

import ast
import os
import re
import shlex
import sys
import urllib.parse
from typing import Any

try:
    import agent_ui as ui
except ImportError:
    ui = None

# System-level device nodes permitted during cell execution
SYSTEM_DEVICES: frozenset[str] = frozenset({
    "/dev/tty",
    "/dev/null",
    "/dev/urandom",
    "/dev/zero",
    "/dev/random",
})

# Protected host system trees
FORBIDDEN_SYS_DIRS: tuple[str, ...] = (
    "/etc",
    "/usr",
    "/var",
    "/bin",
    "/sbin",
    "/opt",
    "/root",
    "/boot",
    "/sys",
    "/proc",
    "/dev",
)

# Mutating or privileged package/system binaries
FORBIDDEN_GLOBAL_COMMANDS: frozenset[str] = frozenset({
    "sudo",
    "doas",
    "su",
    "pkexec",
    "pip",
    "pip3",
    "pipx",
    "yay",
    "paru",
    "apt",
    "apt-get",
    "dnf",
    "yum",
    "brew",
    "npm",
    "pnpm",
    "yarn",
    "gem",
    "cargo",
    "rustup",
    "go",
    "reboot",
    "shutdown",
    "poweroff",
    "useradd",
    "usermod",
    "userdel",
    "passwd",
})

# Known binary wrappers that prefix commands
EXEC_WRAPPERS: frozenset[str] = frozenset({
    "env",
    "nohup",
    "timeout",
    "nice",
    "ionice",
    "setsid",
    "stdbuf",
})

# Read-only inspection subcommands allowed without elevation
READONLY_INSPECTION_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "systemctl": frozenset({
        "status",
        "is-active",
        "is-enabled",
        "is-failed",
        "list-units",
        "list-unit-files",
        "list-timers",
        "list-sockets",
        "show",
        "cat",
    }),
    "pacman": frozenset({
        "-q",
        "-qi",
        "-ql",
        "-qs",
        "-qk",
        "-qo",
        "-qm",
        "-qu",
        "--query",
    }),
}

RE_ROOT_SANDBOX: re.Pattern = re.compile(
    r"^/(?:workspace|app|home/(?:user|developer|runner|admin))(?:/(.*))?$",
    re.IGNORECASE,
)
RE_ENV_VAR_PREFIX: re.Pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*")
RE_CMD_SUBSTITUTION: re.Pattern = re.compile(r"\$\((.*?)\)|`([^`]+)`", re.DOTALL)


def resolve_path(workspace: str, target: str) -> str:
    """Normalizes paths, expanding user directories and healing container sandbox prefixes."""
    if not target:
        return os.path.realpath(workspace)

    clean = os.path.expanduser(urllib.parse.unquote(str(target).strip().strip('\'"`\\\n\r\t ')))
    ws_real = os.path.realpath(workspace)

    # Heal hallucinated container root mount prefixes (/workspace, /app, etc.)
    if clean.startswith("/") and not clean.startswith(ws_real):
        if m := RE_ROOT_SANDBOX.match(clean):
            clean = m.group(1) or "."
        else:
            rel_candidate = clean.lstrip("/")
            if os.path.exists(os.path.join(ws_real, rel_candidate)) or "/" not in rel_candidate:
                clean = rel_candidate

    return os.path.realpath(clean if os.path.isabs(clean) else os.path.join(ws_real, clean))


def is_outside(workspace: str, full_path: str) -> bool:
    """Determines whether full_path breaks outside the workspace root boundary."""
    if not full_path:
        return False
    if full_path in SYSTEM_DEVICES or full_path.startswith("/dev/pts/"):
        return False

    root = os.path.realpath(workspace)
    return full_path != root and not full_path.startswith(root + os.sep)


def check_command(workspace: str, cmd: str) -> str | None:
    """Inspects shell commands for privilege escalation, package mutations, or system path escapes."""
    if not cmd or not cmd.strip():
        return "Empty command"

    clean_cmd = cmd.strip()
    root_ws = os.path.realpath(workspace)

    # 1. Extract command substitutions ($(...), `...`) for recursive inspection
    commands_to_inspect = re.split(r"[\r\n;&|]+", clean_cmd)
    for m in RE_CMD_SUBSTITUTION.finditer(clean_cmd):
        sub_expr = m.group(1) or m.group(2)
        if sub_expr and sub_expr.strip():
            commands_to_inspect.extend(re.split(r"[\r\n;&|]+", sub_expr.strip()))

    for sub in commands_to_inspect:
        sub_strip = sub.strip()
        if not sub_strip:
            continue
        try:
            tokens = shlex.split(sub_strip)
        except ValueError:
            tokens = sub_strip.split()
        if not tokens:
            continue

        # Skip leading environment variable assignments (e.g. FOO=1 BAR=2 cmd)
        while tokens and RE_ENV_VAR_PREFIX.match(tokens[0]):
            tokens.pop(0)

        # Skip standard command wrappers (e.g. env, nohup, timeout 5)
        while tokens and os.path.basename(tokens[0]).lower() in EXEC_WRAPPERS:
            wrapper = os.path.basename(tokens.pop(0)).lower()
            if wrapper == "timeout" and tokens and tokens[0].replace(".", "", 1).isdigit():
                tokens.pop(0)

        if not tokens:
            continue

        binary = os.path.basename(tokens[0]).lower()

        # systemctl read-only vs mutating commands
        if binary == "systemctl":
            sub_actions = [t.lower() for t in tokens[1:] if not t.startswith("-")]
            if not (sub_actions and sub_actions[0] in READONLY_INSPECTION_SUBCOMMANDS["systemctl"]):
                return f"Privileged or mutating systemctl action: '{' '.join(tokens[:2])}'"

        # pacman query vs package install/removal
        elif binary == "pacman":
            action_flags = [t.lower() for t in tokens[1:] if t.startswith("-")]
            if not (action_flags and any(any(f.startswith(rf) for rf in READONLY_INSPECTION_SUBCOMMANDS["pacman"]) for f in action_flags)):
                return f"Package manager modification: '{' '.join(tokens[:2])}'"

        # journalctl (read-only unless vacuuming or rotating)
        elif binary == "journalctl":
            if any(t.startswith(("--vacuum", "--rotate")) for t in tokens):
                return f"Journal maintenance command: '{' '.join(tokens)}'"

        elif binary in FORBIDDEN_GLOBAL_COMMANDS:
            return f"Global system/package binary: '{binary}'"

        # Inspect inline Python commands (-c payload validation)
        if binary in ("python", "python3") or binary.startswith("python3."):
            if "-c" in tokens:
                try:
                    c_idx = tokens.index("-c")
                    if c_idx + 1 < len(tokens):
                        py_payload = tokens[c_idx + 1]
                        if ast_err := check_ast(py_payload):
                            return f"Python -c payload execution blocked: {ast_err}"
                except ValueError:
                    pass

        # Check for system directory references (skipping allowlisted system devices)
        for t in tokens:
            if t in SYSTEM_DEVICES or t.startswith("/dev/pts/"):
                continue
            for sys_dir in FORBIDDEN_SYS_DIRS:
                if t == sys_dir or t.startswith(f"{sys_dir}/"):
                    return f"System directory reference: '{t}'"

        # Path boundary checks (independent of whether path currently exists on disk)
        for t in tokens:
            if t in ("/", ".") or len(t) <= 1:
                continue
            if t in SYSTEM_DEVICES or t.startswith("/dev/pts/"):
                continue
            if ".." in t or t.startswith("~/") or (t.startswith("/") and not t.startswith("//")):
                exp = os.path.realpath(os.path.expanduser(t))
                if is_outside(root_ws, exp):
                    return f"Path outside workspace: '{t}'"

    return None


def check_ast(code: str) -> str | None:
    """Validates in-kernel Python code against shell escapes, alias bypasses, and dangerous syscalls."""
    clean = code.strip()
    if clean.startswith("!"):
        return f"PYTHON SHELL ESCAPE: {clean[:40]}"

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"[error] Python syntax error in code cell: {e}"

    # 1. Resolve import aliases (import os as o, from subprocess import run as r)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = f"{mod}.{alias.name}" if mod else alias.name

    # 2. Inspect calls against resolved module/attribute pairs
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Standalone dangerous calls: exec(), eval(), system()
            if isinstance(node.func, ast.Name):
                func_id = node.func.id
                resolved = aliases.get(func_id, func_id)

                if func_id in ("exec", "eval", "system"):
                    return f"PYTHON DANGEROUS OP: {func_id}() cell execution"
                if resolved.startswith("os.") and resolved.split(".", 1)[1] in (
                    "system", "remove", "unlink", "popen", "chmod", "rename", "kill", "execv", "rmdir"
                ):
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {resolved}()"
                if resolved.startswith("subprocess."):
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {resolved}()"
                if resolved.startswith("shutil.") and resolved.split(".", 1)[1] in ("rmtree", "rmdir", "move"):
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {resolved}()"

            # Attribute calls: os.system(), shutil.rmtree(), subprocess execution
            elif isinstance(node.func, ast.Attribute):
                raw_mod = getattr(node.func.value, "id", "")
                mod_name = aliases.get(raw_mod, raw_mod)
                attr_name = node.func.attr

                if (mod_name == "os" and attr_name in ("system", "remove", "unlink", "popen", "chmod", "rename", "replace", "kill", "execv", "rmdir")) or \
                   (mod_name == "shutil" and attr_name in ("rmtree", "rmdir", "move", "chown")) or \
                   (mod_name == "subprocess" and attr_name in ("run", "Popen", "call", "check_output", "check_call", "getoutput", "getstatusoutput")) or \
                   (mod_name == "pathlib" and attr_name in ("unlink", "rmdir")):
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {mod_name}.{attr_name}()"

    return None


def authorize(action_desc: str, is_security_event: bool = False, spinner: Any = None) -> bool:
    """
    Centralized Invariant Authorization Gate:
    1. Zero-Trust security events (out-of-bounds, sudo, package mutation, dangerous AST calls):
       Confirmation bypass is strictly ignored. Mandatory interactive [y/N] prompt.
    2. Safe in-bounds operations:
       Auto-approved when confirmation gates are disabled via AI_CONFIRM_GATES == "0" (0ms overhead);
       prompts for confirmation when AI_CONFIRM_GATES is "1" or unset.
    """
    if not is_security_event and os.environ.get("AI_CONFIRM_GATES") == "0":
        return True

    if spinner:
        try:
            spinner.stop(leave_on_screen=False)
        except Exception:
            pass

    is_tty = (hasattr(sys, "__stdout__") and sys.__stdout__ and sys.__stdout__.isatty()) or sys.stdout.isatty()
    if not is_tty:
        return False

    return bool(ui and ui.confirm_tool(action_desc))
