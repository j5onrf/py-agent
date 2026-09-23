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

        for t in tokens:
            for sys_dir in FORBIDDEN_SYS_DIRS:
                if t == sys_dir or t.startswith(f"{sys_dir}/"):
                    return f"System directory reference: '{t}'"

        # Skip path inspection on inline python code arguments
        if binary in ("python", "python3") and any(a in tokens for a in ("-c", "-m")):
            tokens = [t for t in tokens if not t.startswith(("import ", "def ", "from ", "print("))]

        for t in tokens:
            if t == "/" or len(t) <= 1:
                continue
            if ".." in t or t.startswith("~/") or (t.startswith("/") and not t.startswith("//")):
                exp = os.path.realpath(os.path.expanduser(t))
                if (os.path.exists(exp) or t.startswith("/home/")) and is_outside(root_ws, exp):
                    return f"Path outside workspace: '{t}'"

    return None


def check_ast(code: str) -> str | None:
    """Validates in-kernel Python code against shell escapes and dangerous syscalls."""
    clean = code.strip()
    if clean.startswith("!"):
        return f"PYTHON SHELL ESCAPE: {clean[:40]}"

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Standalone dangerous calls: exec(), eval(), system()
                if isinstance(node.func, ast.Name) and node.func.id in ("exec", "eval", "system"):
                    return f"PYTHON DANGEROUS OP: {node.func.id}() cell execution"
                # Module calls: os.remove(), os.system(), shutil.rmtree(), subprocess execution
                elif isinstance(node.func, ast.Attribute):
                    mod_name = getattr(node.func.value, "id", "")
                    attr_name = node.func.attr
                    if (mod_name == "os" and attr_name in ("system", "remove", "unlink", "popen")) or \
                       (mod_name == "shutil" and attr_name in ("rmtree", "rmdir")) or \
                       (mod_name == "subprocess" and attr_name in ("run", "Popen", "call", "check_output", "check_call", "getoutput", "getstatusoutput")):
                        return f"OUT-OF-BOUNDS KERNEL EXECUTION: {mod_name}.{attr_name}()"
    except SyntaxError as e:
        return f"[error] Python syntax error in code cell: {e}"

    return None


def authorize(action_desc: str, is_security_event: bool = False, spinner: Any = None) -> bool:
    """
    Centralized Invariant Authorization Gate:
    1. Zero-Trust security events (out-of-bounds, sudo, dangerous AST calls):
       YOLO mode is strictly ignored. Mandatory interactive [y/N] prompt.
    2. Safe in-bounds operations:
       Auto-approved when YOLO is active (0ms overhead); prompts only when YOLO is disabled.
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
