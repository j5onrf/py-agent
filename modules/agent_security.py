#!/usr/bin/env python3
"""Zero-Trust Security & Boundary Enforcement Kernel [Hardened Production Ready]"""

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

# Unified dangerous operations across direct and aliased AST invocations
DANGEROUS_OS_OPS: frozenset[str] = frozenset({
    "system", "remove", "unlink", "popen", "chmod", "rename", "replace",
    "kill", "execv", "execve", "rmdir", "truncate"
})
DANGEROUS_SHUTIL_OPS: frozenset[str] = frozenset({
    "rmtree", "rmdir", "move", "chown", "copytree"
})
DANGEROUS_SUBPROCESS_OPS: frozenset[str] = frozenset({
    "run", "Popen", "call", "check_output", "check_call", "getoutput", "getstatusoutput"
})
DANGEROUS_PATHLIB_OPS: frozenset[str] = frozenset({
    "unlink", "rmdir", "chmod", "rename", "replace"
})
DANGEROUS_BUILTINS: frozenset[str] = frozenset({
    "exec", "eval", "compile", "__import__"
})

RE_ROOT_SANDBOX: re.Pattern = re.compile(
    r"^/(?:workspace|app|home/(?:user|developer|runner|admin))(?:/(.*))?$",
    re.IGNORECASE,
)
RE_ENV_VAR_PREFIX: re.Pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*")
RE_CMD_SUBSTITUTION: re.Pattern = re.compile(r"\$\((.*?)\)|`([^`]+)`", re.DOTALL)


def resolve_path(workspace: str, target: str) -> str:
    """Normalizes paths, expanding user directories and healing container sandbox prefixes.

    Protected system directories (/etc, /var, etc.) are never remapped to workspace relative paths.
    """
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
            first_comp = "/" + rel_candidate.split("/", 1)[0]
            # Protected system trees must never be remapped into workspace relative paths
            if first_comp not in FORBIDDEN_SYS_DIRS and first_comp not in ("/tmp", "/opt", "/home"):
                if os.path.exists(os.path.join(ws_real, rel_candidate)):
                    clean = rel_candidate

    return os.path.realpath(clean if os.path.isabs(clean) else os.path.join(ws_real, clean))


def is_outside(workspace: str, full_path: str) -> bool:
    """Determines whether full_path breaks outside the workspace root boundary."""
    if not full_path:
        return False

    root = os.path.realpath(workspace)
    norm_path = os.path.realpath(os.path.expanduser(full_path))

    if norm_path in SYSTEM_DEVICES:
        return False

    try:
        return os.path.commonpath([root, norm_path]) != root
    except ValueError:
        return True


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

        # Inspect and pop leading environment variable assignments (e.g. FOO=/etc/passwd cmd)
        while tokens and RE_ENV_VAR_PREFIX.match(tokens[0]):
            var_token = tokens.pop(0)
            if "=" in var_token:
                _, val = var_token.split("=", 1)
                clean_val = val.strip("'\"`")
                if clean_val and (clean_val.startswith("/") or clean_val.startswith("~") or ".." in clean_val):
                    norm_val = os.path.realpath(os.path.expanduser(clean_val))
                    for sys_dir in FORBIDDEN_SYS_DIRS:
                        real_sys = os.path.realpath(sys_dir)
                        if norm_val == real_sys or norm_val.startswith(real_sys + os.sep):
                            return f"System directory reference in environment variable: '{var_token}'"
                    if is_outside(root_ws, norm_val):
                        return f"Path outside workspace in environment variable: '{var_token}'"

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

        # pacman query vs package install/removal (deny-by-default for mutating operations)
        elif binary == "pacman":
            action_flags = [t.lower() for t in tokens[1:] if t.startswith("-")]
            mutating = False
            for f in action_flags:
                if f.startswith("--"):
                    if f in ("--sync", "--remove", "--upgrade", "--database", "--refresh"):
                        mutating = True
                        break
                elif any(c in f for c in ("s", "r", "u", "d", "f")):
                    if f not in ("-ss", "-si", "-qs", "-qi", "-ql", "-qk", "-qo", "-qm", "-qu"):
                        mutating = True
                        break
            if mutating or not action_flags:
                return f"Package manager modification: '{' '.join(tokens[:2])}'"

        # journalctl (read-only unless vacuuming or rotating)
        elif binary == "journalctl":
            if any(t.startswith(("--vacuum", "--rotate")) for t in tokens):
                return f"Journal maintenance command: '{' '.join(tokens)}'"

        elif binary in FORBIDDEN_GLOBAL_COMMANDS:
            return f"Global system/package binary: '{binary}'"

        # Inspect Python invocations (-c payloads, -m package escalation, script target path)
        if binary in ("python", "python3") or binary.startswith("python3."):
            if "-m" in tokens:
                m_idx = tokens.index("-m")
                if m_idx + 1 < len(tokens):
                    mod = tokens[m_idx + 1].lower()
                    if mod in ("pip", "pip3", "ensurepip", "venv"):
                        return f"Privileged Python module execution blocked: '-m {mod}'"

            if "-c" in tokens:
                try:
                    c_idx = tokens.index("-c")
                    if c_idx + 1 < len(tokens):
                        py_payload = tokens[c_idx + 1]
                        if ast_err := check_ast(py_payload):
                            return f"Python -c payload execution blocked: {ast_err}"
                except ValueError:
                    pass
            else:
                pos_args = [t for t in tokens[1:] if not t.startswith("-")]
                if pos_args:
                    script_token = pos_args[0]
                    if script_token != "-" and (script_token.startswith("/") or script_token.startswith("~") or ".." in script_token):
                        norm_script = os.path.realpath(os.path.expanduser(script_token))
                        if is_outside(root_ws, norm_script):
                            return f"Python script path outside workspace: '{script_token}'"

        # Token path scanning (System directories and workspace boundaries)
        for raw_t in tokens:
            if raw_t.startswith("-") and not raw_t.startswith("--/"):
                continue

            # Unquote and collapse redundant slashes (//etc -> /etc)
            clean_t = re.sub(r"/+", "/", raw_t.strip("'\"`"))
            expanded_t = os.path.expandvars(clean_t)

            if expanded_t in SYSTEM_DEVICES:
                continue

            norm_path = os.path.realpath(os.path.expanduser(expanded_t))

            # Explicit root filesystem ban
            if expanded_t in ("/", "//") or (norm_path == "/" and clean_t not in (".", "")):
                if norm_path != root_ws:
                    return f"Path outside workspace: '{raw_t}'"

            for sys_dir in FORBIDDEN_SYS_DIRS:
                real_sys = os.path.realpath(sys_dir)
                if norm_path == real_sys or norm_path.startswith(real_sys + os.sep):
                    return f"System directory reference: '{raw_t}'"

            if ".." in clean_t or clean_t.startswith("~/") or clean_t.startswith("/") or expanded_t.startswith("/"):
                if is_outside(root_ws, norm_path):
                    return f"Path outside workspace: '{raw_t}'"

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
            # Standalone dangerous calls: exec(), eval(), compile(), __import__()
            if isinstance(node.func, ast.Name):
                func_id = node.func.id
                resolved = aliases.get(func_id, func_id)

                if func_id in DANGEROUS_BUILTINS:
                    return f"PYTHON DANGEROUS OP: {func_id}() cell execution"
                if resolved.startswith("os.") and resolved.split(".", 1)[1] in DANGEROUS_OS_OPS:
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {resolved}()"
                if resolved.startswith("shutil.") and resolved.split(".", 1)[1] in DANGEROUS_SHUTIL_OPS:
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {resolved}()"
                if resolved.startswith("subprocess.") and resolved.split(".", 1)[1] in DANGEROUS_SUBPROCESS_OPS:
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {resolved}()"
                if resolved.startswith("pathlib.") and resolved.split(".", 1)[1] in DANGEROUS_PATHLIB_OPS:
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {resolved}()"

            # Attribute calls: os.system(), shutil.rmtree(), __import__(...).system()
            elif isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                val_node = node.func.value

                mod_name = ""
                if isinstance(val_node, ast.Name):
                    mod_name = aliases.get(val_node.id, val_node.id)
                elif isinstance(val_node, ast.Call):
                    if isinstance(val_node.func, ast.Name) and val_node.func.id == "__import__":
                        if val_node.args and isinstance(val_node.args[0], ast.Constant) and isinstance(val_node.args[0].value, str):
                            mod_name = val_node.args[0].value
                        else:
                            return "PYTHON DANGEROUS OP: dynamic __import__() execution"

                if (mod_name == "os" and attr_name in DANGEROUS_OS_OPS) or \
                   (mod_name == "shutil" and attr_name in DANGEROUS_SHUTIL_OPS) or \
                   (mod_name == "subprocess" and attr_name in DANGEROUS_SUBPROCESS_OPS) or \
                   (mod_name == "pathlib" and attr_name in DANGEROUS_PATHLIB_OPS):
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {mod_name}.{attr_name}()"

                # Guard dynamic reflection calls on sensitive modules
                if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                    return "PYTHON DANGEROUS OP: getattr() dynamic reflection"

    return None


def authorize(action_desc: str, is_security_event: bool = False, spinner: Any = None) -> bool:
    """Centralized Invariant Authorization Gate.

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

    is_tty = False
    try:
        if hasattr(sys, "__stdout__") and sys.__stdout__ and sys.__stdout__.isatty():
            is_tty = True
        elif sys.stdout and sys.stdout.isatty():
            is_tty = True
    except Exception:
        is_tty = False

    if not is_tty:
        sys.stderr.write(
            f"\r\033[1;33m[security-gate] Blocked non-interactive execution: {action_desc}\033[0m\r\n"
        )
        sys.stderr.flush()
        return False

    approved = bool(ui and ui.confirm_tool(action_desc))
    if not approved:
        sys.stderr.write(
            f"\r\033[1;33m[security-gate] Action declined by user: {action_desc}\033[0m\r\n"
        )
        sys.stderr.flush()
    return approved
