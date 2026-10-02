#!/usr/bin/env python3
"""Zero-Trust Security & Boundary Enforcement Kernel [Hardened Production Ready]"""

import ast
import os
import re
import shlex
import sys
import urllib.parse
from typing import Any

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
    "/run",
    "/srv",
    "/mnt",
    "/media",
)

# Mutating, destructive, or privileged binaries
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
    "groupadd",
    "groupmod",
    "groupdel",
    "passwd",
    "chroot",
    "dd",
    "mkfs",
    "fdisk",
    "parted",
    "wipefs",
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
    "xargs",
})

# Secondary shell interpreters that accept inline -c script arguments
INTERPRETER_BINARIES: frozenset[str] = frozenset({
    "sh",
    "bash",
    "dash",
    "zsh",
    "ksh",
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

# Dangerous AST operations across modules and instances
DANGEROUS_OS_OPS: frozenset[str] = frozenset({
    "system", "popen", "remove", "unlink", "rmdir", "chmod", "fchmod", "lchmod",
    "chown", "fchown", "lchown", "rename", "replace", "truncate", "ftruncate",
    "kill", "execv", "execve", "execvp", "execl", "execlp", "execvpe",
    "spawnl", "spawnv", "spawnlp", "spawnvp", "posix_spawn", "posix_spawnp",
    "chdir", "fchdir", "open", "fdopen", "write",
})
DANGEROUS_SHUTIL_OPS: frozenset[str] = frozenset({
    "rmtree", "rmdir", "move", "chown", "copytree"
})
DANGEROUS_SUBPROCESS_OPS: frozenset[str] = frozenset({
    "run", "Popen", "call", "check_output", "check_call", "getoutput", "getstatusoutput"
})
DANGEROUS_PATHLIB_OPS: frozenset[str] = frozenset({
    "unlink", "rmdir", "chmod", "lchmod", "rename", "replace", "write_bytes", "write_text", "open"
})
DANGEROUS_IO_OPS: frozenset[str] = frozenset({
    "open", "FileIO"
})
DANGEROUS_BUILTINS: frozenset[str] = frozenset({
    "exec", "eval", "compile", "__import__", "getattr", "setattr", "delattr", "__getattribute__"
})

# Destructive methods forbidden on any object or receiver
DANGEROUS_METHOD_CALLS: frozenset[str] = frozenset({
    "unlink", "rmdir", "rmtree", "chmod", "fchmod", "lchmod", "chown", "fchown", "lchown",
    "write_text", "write_bytes", "rename", "replace", "truncate", "ftruncate",
    "system", "popen", "execv", "execve", "execvp", "execl", "execlp", "execvpe",
    "spawnl", "spawnv", "spawnlp", "spawnvp", "posix_spawn", "posix_spawnp",
})

RE_ROOT_SANDBOX: re.Pattern = re.compile(
    r"^/(?:workspace|app|home/(?:user|developer|runner|admin))(?:/(.*))?$",
    re.IGNORECASE,
)
RE_ENV_VAR_PREFIX: re.Pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*")
RE_CMD_SUBSTITUTION: re.Pattern = re.compile(r"[\$<>]\(([\s\S]*?)\)|`([^`]+)`")

_ui_instance: Any = None
_ui_checked: bool = False


def _get_ui() -> Any:
    global _ui_instance, _ui_checked
    if not _ui_checked:
        _ui_checked = True
        try:
            import agent_ui
            _ui_instance = agent_ui
        except Exception:
            _ui_instance = None
    return _ui_instance


def _is_interactive() -> bool:
    """Verifies that both stdin and stdout are attached to an interactive terminal."""
    stdin_tty = False
    stdout_tty = False
    try:
        if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            stdin_tty = True
    except Exception:
        stdin_tty = False

    try:
        for stream in (getattr(sys, "__stdout__", None), sys.stdout):
            if stream is not None and hasattr(stream, "isatty") and stream.isatty():
                stdout_tty = True
                break
    except Exception:
        stdout_tty = False

    return stdin_tty and stdout_tty


def is_in_system_dir(path: str) -> bool:
    """Checks whether a normalized path is located inside any forbidden system directory."""
    if not path or not str(path).strip():
        return False
    norm = os.path.realpath(os.path.expanduser(os.path.expandvars(str(path))))
    if norm in SYSTEM_DEVICES:
        return False
    for sys_dir in FORBIDDEN_SYS_DIRS:
        real_sys = os.path.realpath(sys_dir)
        try:
            if os.path.commonpath([real_sys, norm]) == real_sys:
                return True
        except ValueError:
            continue
    return False


def is_outside(workspace: str, full_path: str) -> bool:
    """Determines whether full_path breaks outside the workspace root boundary. Fails closed."""
    if not full_path or not str(full_path).strip():
        return True

    root = os.path.realpath(workspace)
    norm_path = os.path.realpath(os.path.expanduser(os.path.expandvars(str(full_path))))

    if norm_path in SYSTEM_DEVICES:
        return False

    try:
        return os.path.commonpath([root, norm_path]) != root
    except ValueError:
        return True


def resolve_path(workspace: str, target: str) -> str:
    """Normalizes paths, expanding user directories and healing container sandbox prefixes.

    Protected system directories (/etc, /var, etc.) are never remapped to workspace relative paths.
    """
    if not target or not str(target).strip():
        return os.path.realpath(workspace)

    clean = os.path.expanduser(urllib.parse.unquote(str(target).strip().strip('\'"`\\\n\r\t ')))
    ws_real = os.path.realpath(workspace)

    if clean.startswith("/") and is_outside(ws_real, clean):
        if m := RE_ROOT_SANDBOX.match(clean):
            remainder = m.group(1) or "."
            norm_rem = os.path.normpath(remainder)
            if not norm_rem.startswith("..") and not os.path.isabs(norm_rem):
                clean = norm_rem
        else:
            rel_candidate = clean.lstrip("/")
            if rel_candidate:
                norm_rel = os.path.normpath(rel_candidate)
                if not norm_rel.startswith("..") and not os.path.isabs(norm_rel):
                    first_comp = "/" + norm_rel.split("/", 1)[0]
                    if not is_in_system_dir(first_comp) and first_comp not in ("/tmp", "/opt", "/home"):
                        clean = norm_rel

    return os.path.realpath(clean if os.path.isabs(clean) else os.path.join(ws_real, clean))


def _extract_commands(cmd_str: str) -> list[list[str]]:
    """Recursively parses pipelines, sequential lists, and command substitutions into token arrays."""
    extracted: list[str] = []

    for m in RE_CMD_SUBSTITUTION.finditer(cmd_str):
        sub_body = m.group(1) or m.group(2)
        if sub_body and sub_body.strip():
            extracted.append(sub_body.strip())

    cleaned_parent = RE_CMD_SUBSTITUTION.sub(" ", cmd_str)
    extracted.insert(0, cleaned_parent)

    parsed_cmds: list[list[str]] = []
    for expr in extracted:
        # Pre-split on newlines and carriage returns so multiline commands are never collapsed
        for segment in re.split(r"[\r\n]+", expr):
            seg = segment.strip()
            if not seg:
                continue
            try:
                lexer = shlex.shlex(seg, posix=True, punctuation_chars=True)
                lexer.whitespace_split = True
                tokens = list(lexer)
            except ValueError:
                tokens = seg.split()

            cur_cmd: list[str] = []
            for t in tokens:
                if t in (";", "&&", "||", "|", "&"):
                    if cur_cmd:
                        parsed_cmds.append(cur_cmd)
                        cur_cmd = []
                else:
                    cur_cmd.append(t)
            if cur_cmd:
                parsed_cmds.append(cur_cmd)

    return parsed_cmds


def check_command(workspace: str, cmd: str) -> str | None:
    """Inspects shell commands for privilege escalation, package mutations, or system path escapes."""
    if not cmd or not cmd.strip():
        return "Empty command"

    root_ws = os.path.realpath(workspace)
    command_groups = _extract_commands(cmd.strip())

    for tokens in command_groups:
        if not tokens:
            continue

        # Iteratively peel environment variable assignments and execution wrappers to a fixed point
        unwrapping = True
        while tokens and unwrapping:
            unwrapping = False

            while tokens and RE_ENV_VAR_PREFIX.match(tokens[0]):
                var_token = tokens.pop(0)
                unwrapping = True
                if "=" in var_token:
                    _, val = var_token.split("=", 1)
                    clean_val = val.strip("'\"`")
                    if clean_val and (clean_val.startswith(("/", "~")) or ".." in clean_val):
                        norm_val = os.path.realpath(os.path.expanduser(clean_val))
                        if is_in_system_dir(norm_val):
                            return f"System directory reference in environment variable: '{var_token}'"
                        if is_outside(root_ws, norm_val):
                            return f"Path outside workspace in environment variable: '{var_token}'"

            if tokens and os.path.basename(tokens[0]).lower() in EXEC_WRAPPERS:
                wrapper = os.path.basename(tokens.pop(0)).lower()
                unwrapping = True
                while tokens and (tokens[0].startswith("-") or tokens[0] == "--"):
                    opt = tokens.pop(0)
                    if opt in ("--", "-i", "-0"):
                        continue
                    if opt in ("-u", "-k", "-s", "-n", "-I") and tokens:
                        tokens.pop(0)
                    elif (opt in ("-S", "--split-string") and tokens) or opt.startswith(("-S", "--split-string=")):
                        if opt.startswith("--split-string="):
                            split_val = opt.split("=", 1)[1]
                        elif opt.startswith("-S") and len(opt) > 2:
                            split_val = opt[2:]
                        elif tokens:
                            split_val = tokens.pop(0)
                        else:
                            split_val = ""

                        if split_val:
                            try:
                                sub_lex = shlex.shlex(split_val, posix=True, punctuation_chars=True)
                                sub_lex.whitespace_split = True
                                tokens = list(sub_lex) + tokens
                            except ValueError:
                                tokens = split_val.split() + tokens

                if wrapper in ("timeout", "nice", "ionice") and tokens:
                    if re.match(r"^\d+(\.\d+)?[smhd]?$", tokens[0]):
                        tokens.pop(0)

        if not tokens:
            continue

        binary = os.path.basename(tokens[0]).lower()

        if binary == "systemctl":
            sub_actions = [t.lower() for t in tokens[1:] if not t.startswith("-")]
            if not (sub_actions and sub_actions[0] in READONLY_INSPECTION_SUBCOMMANDS["systemctl"]):
                return f"Privileged or mutating systemctl action: '{' '.join(tokens[:2])}'"

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

        elif binary == "journalctl":
            if any(t.startswith(("--vacuum", "--rotate")) for t in tokens):
                return f"Journal maintenance command: '{' '.join(tokens)}'"

        elif binary in FORBIDDEN_GLOBAL_COMMANDS:
            return f"Global system/package binary: '{binary}'"

        # Intercept shell interpreters with inline scripts
        if binary in INTERPRETER_BINARIES:
            for idx, tok in enumerate(tokens[1:], start=1):
                shell_code = None
                if tok == "-c" and idx + 1 < len(tokens):
                    shell_code = tokens[idx + 1]
                elif tok.startswith("-c") and len(tok) > 2:
                    shell_code = tok[2:]

                if shell_code is not None:
                    if err := check_command(workspace, shell_code):
                        return f"Nested shell -c execution blocked: {err}"

        # Intercept Python module and code invocations
        if binary in ("python", "python3") or binary.startswith("python3."):
            for idx, tok in enumerate(tokens[1:], start=1):
                mod = None
                if tok == "-m" and idx + 1 < len(tokens):
                    mod = tokens[idx + 1].lower()
                elif tok.startswith("-m") and len(tok) > 2:
                    mod = tok[2:].lower()

                if mod in ("pip", "pip3", "pipx", "ensurepip", "venv"):
                    return f"Privileged Python module execution blocked: '-m {mod}'"

                py_code = None
                if tok == "-c" and idx + 1 < len(tokens):
                    py_code = tokens[idx + 1]
                elif tok.startswith("-c") and len(tok) > 2:
                    py_code = tok[2:]

                if py_code is not None:
                    if ast_err := check_ast(py_code):
                        return f"Python -c payload execution blocked: {ast_err}"

            pos_args = [t for t in tokens[1:] if not t.startswith("-")]
            if pos_args:
                script_token = pos_args[0]
                if script_token != "-" and (script_token.startswith(("/", "~")) or ".." in script_token):
                    norm_script = os.path.realpath(os.path.expanduser(script_token))
                    if is_outside(root_ws, norm_script):
                        return f"Python script path outside workspace: '{script_token}'"

        for raw_t in tokens:
            targets_to_check: list[str] = []
            if raw_t.startswith("--") and "=" in raw_t:
                _, val = raw_t.split("=", 1)
                targets_to_check.append(val)
            elif raw_t.startswith("-") and len(raw_t) > 2 and raw_t[1] in ("o", "f", "I", "L", "d", "e"):
                targets_to_check.append(raw_t[2:])
            elif not raw_t.startswith("-"):
                targets_to_check.append(raw_t)

            split_targets: list[str] = []
            for target in targets_to_check:
                split_targets.extend([p for p in re.split(r"[><]+", target) if p])

            for part in split_targets:
                clean_t = re.sub(r"/+", "/", part.strip("'\"`"))
                expanded_t = os.path.expandvars(clean_t)

                norm_path = os.path.realpath(os.path.expanduser(expanded_t))
                if norm_path in SYSTEM_DEVICES:
                    continue

                if expanded_t in ("/", "//") or (norm_path == "/" and clean_t not in (".", "")):
                    if norm_path != root_ws:
                        return f"Path outside workspace: '{raw_t}'"

                if is_in_system_dir(norm_path):
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
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    val = node.value
                    if isinstance(val, ast.Name):
                        aliases[target.id] = aliases.get(val.id, val.id)
                    elif isinstance(val, ast.Attribute):
                        base = aliases.get(val.value.id, val.value.id) if isinstance(val.value, ast.Name) else ""
                        aliases[target.id] = f"{base}.{val.attr}" if base else val.attr
                    elif isinstance(val, ast.Call):
                        fn_name = ""
                        if isinstance(val.func, ast.Name):
                            fn_name = aliases.get(val.func.id, val.func.id)
                        elif isinstance(val.func, ast.Attribute):
                            fn_name = val.func.attr
                        if fn_name in ("Path", "pathlib.Path"):
                            aliases[target.id] = "pathlib"

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            val = node.value
            while isinstance(val, ast.Subscript):
                val = val.value
            if isinstance(val, ast.Name) and val.id in ("__builtins__", "globals", "locals"):
                if isinstance(node.slice, ast.Constant) and str(node.slice.value) in DANGEROUS_BUILTINS:
                    return f"PYTHON DANGEROUS OP: {val.id}['{node.slice.value}'] dynamic execution"

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Subscript):
                return "PYTHON DANGEROUS OP: subscripted callable execution"

            elif isinstance(node.func, ast.Name):
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

                if attr_name in DANGEROUS_METHOD_CALLS:
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: .{attr_name}() dangerous call or mutation"
                if attr_name in DANGEROUS_BUILTINS:
                    return f"PYTHON DANGEROUS OP: .{attr_name}() reflection"
                if (mod_name == "os" and attr_name in DANGEROUS_OS_OPS) or \
                   (mod_name == "shutil" and attr_name in DANGEROUS_SHUTIL_OPS) or \
                   (mod_name == "subprocess" and attr_name in DANGEROUS_SUBPROCESS_OPS) or \
                   (mod_name == "pathlib" and attr_name in DANGEROUS_PATHLIB_OPS) or \
                   (mod_name in ("io", "_io") and attr_name in DANGEROUS_IO_OPS):
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {mod_name}.{attr_name}()"
                if mod_name in ("importlib", "importlib.machinery") or attr_name == "import_module":
                    return f"PYTHON DANGEROUS OP: dynamic module import"
                if mod_name == "ctypes" or attr_name in ("cdll", "windll"):
                    return "PYTHON DANGEROUS OP: ctypes interface execution"

    return None


def authorize(action_desc: str, is_security_event: bool = False, spinner: Any = None) -> bool:
    """Centralized Invariant Authorization Gate. Fails closed."""
    if not is_security_event and os.environ.get("AI_CONFIRM_GATES") == "0":
        return True

    if spinner:
        try:
            spinner.stop(leave_on_screen=False)
        except Exception:
            pass

    if not _is_interactive():
        sys.stderr.write(
            f"\r\033[1;33m[security-gate] Blocked non-interactive execution: {action_desc}\033[0m\r\n"
        )
        sys.stderr.flush()
        return False

    approved = False
    ui = _get_ui()
    if ui and hasattr(ui, "confirm_tool"):
        try:
            approved = bool(ui.confirm_tool(action_desc))
        except Exception:
            approved = False
    else:
        try:
            sys.stdout.write(f"\n\033[1;33m[security-gate] Authorize: {action_desc}? [y/N]: \033[0m")
            sys.stdout.flush()
            ans = sys.stdin.readline().strip().lower()
            approved = ans in ("y", "yes")
        except (EOFError, KeyboardInterrupt, Exception):
            approved = False

    if not approved:
        sys.stderr.write(
            f"\r\033[1;33m[security-gate] Action declined: {action_desc}\033[0m\r\n"
        )
        sys.stderr.flush()
    return approved
