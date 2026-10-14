#!/usr/bin/env python3
"""Zero-Trust Security & Boundary Enforcement Kernel [OCR 0.01]"""

import ast
import os
import re
import shlex
import sys
import urllib.parse
from typing import Any

# System-level device nodes permitted during cell execution
SYSTEM_DEVICES: frozenset[str] = frozenset(
    {
        "/dev/tty",
        "/dev/null",
        "/dev/urandom",
        "/dev/zero",
        "/dev/random",
    }
)

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
FORBIDDEN_GLOBAL_COMMANDS: frozenset[str] = frozenset(
    {
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
    }
)

# Known binary wrappers that prefix commands
EXEC_WRAPPERS: frozenset[str] = frozenset(
    {
        "env",
        "nohup",
        "timeout",
        "nice",
        "ionice",
        "setsid",
        "stdbuf",
        "xargs",
    }
)

# Flags consuming following arguments across wrappers
WRAPPER_VALUE_FLAGS: dict[str, frozenset[str]] = {
    "timeout": frozenset({"-k", "-s"}),
    "nice": frozenset({"-n"}),
    "ionice": frozenset({"-c", "-n", "-p"}),
    "xargs": frozenset({"-P", "-n", "-L", "-d", "-E", "-I", "-s"}),
    "env": frozenset({"-C", "-S", "-u"}),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
}

# Shell reserved words and grouping operators that precede command binaries
SHELL_RESERVED_WORDS: frozenset[str] = frozenset(
    {
        "if",
        "then",
        "else",
        "elif",
        "fi",
        "do",
        "done",
        "while",
        "until",
        "for",
        "in",
        "time",
        "!",
        "{",
        "}",
        "(",
        ")",
        "function",
    }
)

# Secondary shell interpreters that accept inline -c script arguments
INTERPRETER_BINARIES: frozenset[str] = frozenset(
    {
        "sh",
        "bash",
        "dash",
        "zsh",
        "ksh",
    }
)

# Read-only inspection subcommands allowed without elevation
READONLY_INSPECTION_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "systemctl": frozenset(
        {
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
        }
    ),
    "pacman": frozenset(
        {
            "-q",
            "-qi",
            "-ql",
            "-qs",
            "-qk",
            "-qo",
            "-qm",
            "-qu",
            "--query",
        }
    ),
}

# Dangerous AST operations across modules and instances
DANGEROUS_OS_OPS: frozenset[str] = frozenset(
    {
        "system",
        "popen",
        "remove",
        "unlink",
        "rmdir",
        "chmod",
        "fchmod",
        "lchmod",
        "chown",
        "fchown",
        "lchown",
        "rename",
        "replace",
        "truncate",
        "ftruncate",
        "kill",
        "execv",
        "execve",
        "execvp",
        "execl",
        "execlp",
        "execvpe",
        "spawnl",
        "spawnv",
        "spawnlp",
        "spawnvp",
        "posix_spawn",
        "posix_spawnp",
        "chdir",
        "fchdir",
        "open",
        "fdopen",
        "write",
    }
)
DANGEROUS_SHUTIL_OPS: frozenset[str] = frozenset({"rmtree", "rmdir", "move", "chown", "copytree"})
DANGEROUS_SUBPROCESS_OPS: frozenset[str] = frozenset(
    {"run", "Popen", "call", "check_output", "check_call", "getoutput", "getstatusoutput"}
)
DANGEROUS_PATHLIB_OPS: frozenset[str] = frozenset(
    {"unlink", "rmdir", "chmod", "lchmod", "rename", "replace", "write_bytes", "write_text", "open"}
)
DANGEROUS_IO_OPS: frozenset[str] = frozenset({"open", "FileIO", "open_code"})
DANGEROUS_BUILTINS: frozenset[str] = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "__getattribute__",
    }
)

# Destructive methods forbidden on any object or receiver
DANGEROUS_METHOD_CALLS: frozenset[str] = frozenset(
    {
        "unlink",
        "rmdir",
        "rmtree",
        "chmod",
        "fchmod",
        "lchmod",
        "chown",
        "fchown",
        "lchown",
        "write_text",
        "write_bytes",
        "rename",
        "replace",
        "truncate",
        "ftruncate",
        "system",
        "popen",
        "execv",
        "execve",
        "execvp",
        "execl",
        "execlp",
        "execvpe",
        "spawnl",
        "spawnv",
        "spawnlp",
        "spawnvp",
        "posix_spawn",
        "posix_spawnp",
    }
)

RE_ROOT_SANDBOX: re.Pattern = re.compile(
    r"^/(?:workspace|app|home/(?:user|developer|runner|admin))(?:/(.*))?$",
    re.IGNORECASE,
)
RE_ENV_VAR_PREFIX: re.Pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*")

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
    """Verifies that both stdin and active stdout are genuinely attached to an interactive terminal."""
    try:
        return bool(
            sys.stdin
            and hasattr(sys.stdin, "isatty")
            and sys.stdin.isatty()
            and sys.stdout
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
    except Exception:
        return False


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


PY_AGENT_ROOT: str = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TRUSTED_HARNESS_TREES: tuple[str, ...] = (
    os.path.realpath(os.path.join(PY_AGENT_ROOT, "plugins")),
    os.path.realpath(os.path.join(PY_AGENT_ROOT, "tools")),
)


def is_harness_tool(norm_path: str) -> bool:
    """Permits execution of py-agent's first-party plugins and tools across any clone."""
    for tree in TRUSTED_HARNESS_TREES:
        try:
            if os.path.commonpath([tree, norm_path]) == tree:
                return True
        except ValueError:
            continue
    return False


def is_outside(workspace: str, full_path: str) -> bool:
    """Determines whether full_path breaks outside the workspace root boundary. Fails closed."""
    if not full_path or not str(full_path).strip():
        return True

    root = os.path.realpath(workspace)
    clean_p = os.path.expanduser(os.path.expandvars(str(full_path).strip()))
    # Anchor relative paths explicitly to workspace root, never to ambient process CWD
    norm_path = os.path.realpath(clean_p if os.path.isabs(clean_p) else os.path.join(root, clean_p))

    if norm_path in SYSTEM_DEVICES:
        return False

    try:
        return os.path.commonpath([root, norm_path]) != root
    except ValueError:
        return True


def resolve_path(workspace: str, target: str) -> str:
    """Normalizes paths, expanding user directories and healing container sandbox prefixes."""
    if not target or not str(target).strip():
        return os.path.realpath(workspace)

    clean = os.path.expanduser(urllib.parse.unquote(str(target).strip().strip("'\"`\\\n\r\t ")))
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


def _extract_balanced_substitutions(text: str) -> tuple[str, list[str]]:
    """Extracts command substitutions $(...), <(...), >(...), and `...` with balanced nesting."""
    subs: list[str] = []
    cleaned: list[str] = []
    i, n = 0, len(text)
    in_single = False

    while i < n:
        ch = text[i]
        if ch == "'" and (i == 0 or text[i - 1] != "\\"):
            in_single = not in_single
            cleaned.append(ch)
            i += 1
            continue

        if not in_single:
            if ch in ("$", "<", ">") and i + 1 < n and text[i + 1] == "(":
                i += 2
                depth = 1
                sub_chars = []
                while i < n and depth > 0:
                    c = text[i]
                    if c == "(" and (i == 0 or text[i - 1] != "\\"):
                        depth += 1
                    elif c == ")" and (i == 0 or text[i - 1] != "\\"):
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    sub_chars.append(c)
                    i += 1
                sub_body = "".join(sub_chars)
                if sub_body.strip():
                    subs.append(sub_body.strip())
                cleaned.append(" ")
                continue

            if ch == "`" and (i == 0 or text[i - 1] != "\\"):
                i += 1
                bt_chars = []
                while i < n and not (text[i] == "`" and text[i - 1] != "\\"):
                    bt_chars.append(text[i])
                    i += 1
                if i < n:
                    i += 1
                bt_body = "".join(bt_chars)
                if bt_body.strip():
                    subs.append(bt_body.strip())
                cleaned.append(" ")
                continue

        cleaned.append(ch)
        i += 1

    return "".join(cleaned), subs


def _extract_commands(cmd_str: str) -> tuple[list[list[str]], str | None]:
    """Recursively parses pipelines, lists, and balanced substitutions into token arrays."""
    parent_clean, subs = _extract_balanced_substitutions(cmd_str)
    all_exprs = [parent_clean] + subs
    parsed_cmds: list[list[str]] = []

    for expr in all_exprs:
        for segment in re.split(r"[\r\n]+", expr):
            seg = segment.strip()
            if not seg:
                continue
            try:
                lexer = shlex.shlex(seg, posix=True, punctuation_chars=True)
                lexer.whitespace_split = True
                tokens = list(lexer)
            except ValueError as e:
                return [], f"Unbalanced quotes or shell syntax error in command: {e}"

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

    return parsed_cmds, None


def check_command(workspace: str, cmd: str, current_depth: int = 0) -> str | None:
    """Inspects shell commands for privilege escalation, package mutations, or system path escapes."""
    if current_depth > 8:
        return "Command execution recursion depth limit exceeded (max 8 levels)"
    if not cmd or not cmd.strip():
        return "Empty command"

    root_ws = os.path.realpath(workspace)
    command_groups, parse_err = _extract_commands(cmd.strip())
    if parse_err:
        return parse_err

    local_vars: dict[str, str] = {}

    for tokens in command_groups:
        if not tokens:
            continue

        unwrapping = True
        while tokens and unwrapping:
            unwrapping = False

            while tokens and (tokens[0].lower() in SHELL_RESERVED_WORDS or tokens[0] in ("!", "{", "}", "(", ")")):
                tokens.pop(0)
                unwrapping = True

            while tokens and RE_ENV_VAR_PREFIX.match(tokens[0]):
                var_token = tokens.pop(0)
                unwrapping = True
                if "=" in var_token:
                    k, val = var_token.split("=", 1)
                    clean_val = val.strip("'\"`")
                    local_vars[k] = clean_val
                    if clean_val and (clean_val.startswith(("/", "~")) or ".." in clean_val):
                        norm_val = os.path.realpath(
                            os.path.expanduser(clean_val)
                            if os.path.isabs(os.path.expanduser(clean_val))
                            else os.path.join(root_ws, clean_val)
                        )
                        if is_in_system_dir(norm_val):
                            return f"System directory reference in environment variable: '{var_token}'"
                        if is_outside(root_ws, norm_val):
                            return f"Path outside workspace in environment variable: '{var_token}'"

            if tokens and os.path.basename(tokens[0]).lower() in EXEC_WRAPPERS:
                wrapper = os.path.basename(tokens.pop(0)).lower()
                unwrapping = True
                val_flags = WRAPPER_VALUE_FLAGS.get(wrapper, frozenset())

                while tokens and (tokens[0].startswith("-") or tokens[0] == "--"):
                    opt = tokens.pop(0)
                    if opt == "--":
                        break
                    if opt in val_flags and tokens:
                        tokens.pop(0)
                    elif any(opt.startswith(f"{vf}=") for vf in val_flags):
                        continue
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
                            except ValueError as e:
                                return f"Unbalanced quotes in wrapper split-string: {e}"

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

        if binary in INTERPRETER_BINARIES:
            for idx, tok in enumerate(tokens[1:], start=1):
                shell_code = None
                if tok == "-c" and idx + 1 < len(tokens):
                    shell_code = tokens[idx + 1]
                elif re.match(r"^-[a-zA-Z]*c$", tok) and idx + 1 < len(tokens):
                    shell_code = tokens[idx + 1]
                elif re.match(r"^-[a-zA-Z]*c(.+)$", tok):
                    m = re.match(r"^-[a-zA-Z]*c(.+)$", tok)
                    shell_code = m.group(1) if m else None

                if shell_code is not None:
                    if err := check_command(workspace, shell_code, current_depth + 1):
                        return f"Nested shell -c execution blocked: {err}"

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
                elif re.match(r"^-[a-zA-Z]*c$", tok) and idx + 1 < len(tokens):
                    py_code = tokens[idx + 1]
                elif re.match(r"^-[a-zA-Z]*c(.+)$", tok):
                    m = re.match(r"^-[a-zA-Z]*c(.+)$", tok)
                    py_code = m.group(1) if m else None

                if py_code is not None:
                    if ast_err := check_ast(py_code):
                        return f"Python -c payload execution blocked: {ast_err}"

            pos_args = [t for t in tokens[1:] if not t.startswith("-")]
            if pos_args:
                script_token = pos_args[0]
                if script_token != "-" and (script_token.startswith(("/", "~")) or ".." in script_token):
                    norm_script = os.path.realpath(
                        os.path.expanduser(script_token)
                        if os.path.isabs(os.path.expanduser(script_token))
                        else os.path.join(root_ws, script_token)
                    )
                    if not is_harness_tool(norm_script) and is_outside(root_ws, norm_script):
                        return f"Python script path outside workspace: '{script_token}'"

        # Check path arguments for system directory access and traversal escapes
        for raw_t in tokens[1:]:
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

                if re.search(r"\$[A-Za-z_]|\$\{[A-Za-z_]", clean_t):
                    def _sub_var(m):
                        vname = m.group(1) or m.group(2)
                        return local_vars.get(vname, os.environ.get(vname, ""))

                    clean_t = re.sub(r"\$\{([A-Za-z0-9_]+)\}|\$([A-Za-z0-9_]+)", _sub_var, clean_t)
                    if re.search(r"\$[A-Za-z_]|\$\{[A-Za-z_]", clean_t):
                        return f"Unresolved shell variable in command path: '{raw_t}'"

                expanded_t = os.path.expandvars(clean_t)
                target_resolved = (
                    os.path.expanduser(expanded_t)
                    if os.path.isabs(os.path.expanduser(expanded_t))
                    else os.path.join(root_ws, expanded_t)
                )
                norm_path = os.path.realpath(target_resolved)

                if norm_path in SYSTEM_DEVICES:
                    continue

                if expanded_t in ("/", "//") or (norm_path == "/" and clean_t not in (".", "")):
                    if norm_path != root_ws:
                        return f"Path outside workspace: '{raw_t}'"

                if is_in_system_dir(norm_path):
                    return f"System directory reference: '{raw_t}'"

                if (
                    ".." in clean_t
                    or clean_t.startswith("~")
                    or clean_t.startswith("/")
                    or expanded_t.startswith("/")
                    or (os.path.islink(norm_path) and is_outside(root_ws, norm_path))
                ):
                    if not is_harness_tool(norm_path) and is_outside(root_ws, norm_path):
                        return f"Path outside workspace: '{raw_t}'"

    return None


def check_ast(code: str, workspace: str | None = None) -> str | None:
    """Validates in-kernel Python code against shell escapes, alias bypasses, and dangerous syscalls."""
    ws = os.path.realpath(workspace or os.environ.get("AI_WORKSPACE_PATH", os.getcwd()))
    clean = code.strip()
    if clean.startswith("!"):
        return f"PYTHON SHELL ESCAPE: {clean[:40]}"

    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
        return f"[error] Python AST syntax or structure error in code cell: {e}"

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
                        elif fn_name in ("__import__", "importlib.import_module"):
                            if (
                                val.args
                                and isinstance(val.args[0], ast.Constant)
                                and isinstance(val.args[0].value, str)
                            ):
                                aliases[target.id] = val.args[0].value

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
                if resolved in (
                    "open",
                    "io.open",
                    "_io.open",
                    "codecs.open",
                    "builtins.open",
                    "__builtins__.open",
                    "io.FileIO",
                    "_io.FileIO",
                ):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        target_p = node.args[0].value
                        if is_in_system_dir(target_p) or is_outside(ws, target_p):
                            return f"OUT-OF-BOUNDS FILE ACCESS: open('{target_p}')"
                    elif not node.args:
                        return f"PYTHON DANGEROUS OP: {resolved}() missing target argument"
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
                    if isinstance(val_node.func, ast.Name) and val_node.func.id in ("__import__", "importlib.import_module"):
                        if (
                            val_node.args
                            and isinstance(val_node.args[0], ast.Constant)
                            and isinstance(val_node.args[0].value, str)
                        ):
                            mod_name = val_node.args[0].value
                        else:
                            return "PYTHON DANGEROUS OP: dynamic module import"

                if (
                    mod_name in ("io", "_io", "codecs", "builtins", "__builtins__")
                    and attr_name in ("open", "FileIO", "open_code")
                ):
                    return f"PYTHON DANGEROUS OP: {mod_name}.{attr_name}() file access"
                if attr_name in DANGEROUS_METHOD_CALLS:
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: .{attr_name}() dangerous call or mutation"
                if attr_name in DANGEROUS_BUILTINS:
                    return f"PYTHON DANGEROUS OP: .{attr_name}() reflection"
                if (
                    (mod_name == "os" and attr_name in DANGEROUS_OS_OPS)
                    or (mod_name == "shutil" and attr_name in DANGEROUS_SHUTIL_OPS)
                    or (mod_name == "subprocess" and attr_name in DANGEROUS_SUBPROCESS_OPS)
                    or (mod_name == "pathlib" and attr_name in DANGEROUS_PATHLIB_OPS)
                    or (mod_name in ("io", "_io") and attr_name in DANGEROUS_IO_OPS)
                ):
                    return f"OUT-OF-BOUNDS KERNEL EXECUTION: {mod_name}.{attr_name}()"
                if mod_name in ("importlib", "importlib.machinery") or attr_name == "import_module":
                    return "PYTHON DANGEROUS OP: dynamic module import"
                if mod_name == "ctypes" or attr_name in ("cdll", "windll"):
                    return "PYTHON DANGEROUS OP: ctypes interface execution"

    return None


def authorize(action_desc: str, is_security_event: bool = False, spinner: Any = None) -> bool:
    """Centralized Invariant Authorization Gate. Fails closed."""
    if not is_security_event and os.environ.get("AI_CONFIRM_GATES") == "0":
        return True

    # Safely stop spinner across both InlineSpinner and CalmBoatSpinner implementations
    if spinner:
        try:
            spinner.stop()
        except TypeError:
            try:
                spinner.stop(leave_on_screen=False)
            except Exception:
                pass
        except Exception:
            pass
        try:
            # Wipe spinner residue and reveal the hardware cursor
            sys.stderr.write("\r\x1b[2K\r\033[?25h")
            sys.stderr.flush()
        except Exception:
            pass

    if not _is_interactive():
        sys.stderr.write(f"\r\033[1;33m[security-gate] Blocked non-interactive execution: {action_desc}\033[0m\r\n")
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
        sys.stderr.write(f"\r\033[1;33m[security-gate] Action declined: {action_desc}\033[0m\r\n")
        sys.stderr.flush()
    return approved
