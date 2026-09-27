#!/usr/bin/env python3
"""Tool Format Adapters & Self-Healing Parser [Hardened Production Ready]"""

import ast
import json
import os
import re
import sys
import time
from typing import Any

# ── 1. Compiled Regex Interceptors ────────────────────────────────────────────

RE_HERMES_XML = re.compile(
    r"<tool_call>\s*<function=(?P<name>[^>]+)>\s*(?P<params>[\s\S]*?)\s*</function>\s*</tool_call>",
    re.DOTALL,
)
RE_HERMES_PARAM = re.compile(
    r"<parameter(?:=|\s+name=[\"']?)(?P<key>[^>\"'\s]+)[\"']?>\s*(?P<val>[\s\S]*?)\s*</parameter>",
    re.DOTALL,
)
RE_DSML = re.compile(
    r"<[|｜]DSML[|｜]invoke\s+name=[\"'](?P<name>[^\"']+)[\"']\s+arguments=[\"'](?P<args>[\s\S]*?)[\"']\s*/>",
    re.DOTALL,
)
RE_MISTRAL = re.compile(r"\[TOOL_CALLS\]\s*(?P<calls>\[[\s\S]*?\])", re.DOTALL)
RE_XML_TOOL_CALL = re.compile(r"<tool_call>\s*(?P<payload>[\s\S]*?)\s*</tool_call>", re.DOTALL)

# Markdown wrappers
RE_MD_JSON_WRAPPER = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", re.DOTALL)
RE_MD_CODE_BLOCK = re.compile(r"^\s*```[a-zA-Z0-9_+-]*\s*\n([\s\S]*?)\n```\s*$", re.DOTALL)
RE_MD_PY_WRAPPER = re.compile(r"```(?:python|py)\s*\n([\s\S]*?)\s*```", re.DOTALL)

RE_LING_XML = re.compile(
    r"<tool_call>\s*(?P<name>[a-zA-Z_]\w*)\s*(?P<params><arg_key>[\s\S]*?)\s*</tool_call>",
    re.DOTALL,
)
RE_LING_PARAM = re.compile(
    r"<arg_key>(?P<key>[^<]+)</arg_key>\s*<arg_value>(?P<val>[\s\S]*?)</arg_value>",
    re.DOTALL,
)
RE_XML_TOOL_TAGS = re.compile(
    r"<\|?[a-zA-Z_]+_call_?(?:start|end)?\|?>|</?tool_call>|</?function[^>]*>|</?parameter[^>]*>|</?arg_key>|</?arg_value>|</?function_calls>|</?[|｜]DSML[|｜]?(?:invoke)?>",
    re.DOTALL,
)
RE_PATH_EXTRACT = re.compile(
    r"([a-zA-Z0-9_\-\./]+\.(?:py|json|md|txt|sh|html|css|js|ts|cpp|c|h|rs|go))"
)
RE_ROOT_SANDBOX = re.compile(
    r"^[\"']?(?:/home/(?:user|developer|runner|admin)|/workspace|/app)(?:/(.*))?$",
    re.IGNORECASE,
)
RE_CD_COMMAND = re.compile(
    r"^\s*cd\s+[\"']?(?:/[^;&|\n]*|\~[^;&|\n]*|\.)[\"']?\s*(?:&&|;)\s*",
    re.IGNORECASE,
)

# Shell mutation interceptors
RE_CAT_EOF_TARGET_END = re.compile(
    r"^cat\s*<<\s*['\"]?(\w+)['\"]?\s*>\s*(\S+)\s*\n([\s\S]*?)\n\1\s*$",
    re.DOTALL,
)
RE_CAT_EOF_TARGET_START = re.compile(
    r"^cat\s*>\s*(\S+)\s*<<\s*['\"]?(\w+)['\"]?\s*\n([\s\S]*?)\n\2\s*$",
    re.DOTALL,
)
RE_TEE_EOF = re.compile(
    r"^cat\s*<<\s*['\"]?(\w+)['\"]?\s*\|\s*(?:sudo\s+)?tee\s+(\S+)\s*\n([\s\S]*?)\n\1\s*$",
    re.DOTALL,
)
RE_ECHO_REDIRECT = re.compile(
    r"^echo\s+['\"]([\s\S]*?)['\"]\s*>\s*(\S+)$",
    re.DOTALL,
)
RE_PRINTF_REDIRECT = re.compile(
    r"^printf\s+(?:['\"][^'\"]*%[a-zA-Z][^'\"]*['\"]\s+)?['\"]([\s\S]*?)['\"]\s*>\s*(\S+)$",
    re.DOTALL,
)
RE_ECHO_TEE = re.compile(
    r"^(?:echo|printf)\s+(?:-e\s+)?['\"]([\s\S]*?)['\"]\s*\|\s*(?:sudo\s+)?tee\s+(\S+)$",
    re.DOTALL,
)

RE_BOGUS_IMPORTS = re.compile(
    r"^\s*(?:from\s+[\w\.]+\s+import\s+(?:final_answer|exec_python)|import\s+(?:final_answer|exec_python))\s*;?\s*",
    re.MULTILINE,
)

RE_GUTTER_LINE = re.compile(r"^\s*\d+[:|│\t ]\s?")

RE_ELLIPSIS_PLACEHOLDER = re.compile(
    r"^[ \t]*(?:#|//|/\*|<!--)[ \t]*\.{3,}[ \t]*(?:existing|rest of|unchanged|previous|remaining|code here|code).*?(?:\*/|-->)?$",
    re.IGNORECASE | re.MULTILINE,
)


def _close_unterminated_quote(cmd_str: str) -> str:
    """State machine quote balancing: only balances quotes genuinely unclosed at the end of a command."""
    in_quote = None
    esc = False
    for ch in cmd_str:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if in_quote:
            if ch == in_quote:
                in_quote = None
        else:
            if ch in ('"', "'"):
                in_quote = ch
    if in_quote:
        return cmd_str + in_quote
    return cmd_str


def _strip_line_number_gutters(text: str) -> str:
    """Strips copied editor line number gutters (e.g. '12: ', '12 | ') from old_str or new_str."""
    if not text:
        return text

    if "\n" not in text:
        if m := re.match(r"^\s*\d+(?:\s*[|│]|\s*:\s{2,}|\t)\s?(.*)$", text):
            return m.group(1)
        return text

    lines = text.splitlines(keepends=True)
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return text

    matches = [bool(RE_GUTTER_LINE.match(l)) for l in non_empty]
    if sum(matches) / len(non_empty) >= 0.6:
        cleaned = []
        for line in lines:
            if RE_GUTTER_LINE.match(line):
                cleaned.append(RE_GUTTER_LINE.sub("", line, count=1))
            else:
                cleaned.append(line)
        return "".join(cleaned)
    return text


def _extract_diff_hunk(diff_text: str) -> tuple[str, str] | None:
    """Extracts (old_str, new_str) from unified diff or git patch hunks."""
    if not diff_text:
        return None

    lines = diff_text.replace("\r\n", "\n").splitlines()
    has_markers = any(l.startswith(("-", "+", "@@")) for l in lines)
    if not has_markers:
        return None

    old_lines: list[str] = []
    new_lines: list[str] = []
    in_hunk = False

    for line in lines:
        if line.startswith("@@"):
            in_hunk = True
            continue
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
        elif line.startswith(" "):
            old_lines.append(line[1:])
            new_lines.append(line[1:])
        elif in_hunk:
            old_lines.append(line)
            new_lines.append(line)

    if old_lines or new_lines:
        return "\n".join(old_lines), "\n".join(new_lines)
    return None


# ── 2. Parameter Aliases & String Normalization ───────────────────────────────

def normalize_params(args: dict[str, Any]) -> dict[str, Any]:
    """Auto-heals parameter alias discrepancies, wrapped quotes, and escaped command syntax."""
    if not isinstance(args, dict):
        return {}

    cleaned: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str):
            clean_v = v.strip()
            if len(clean_v) >= 2:
                if (clean_v.startswith('"') and clean_v.endswith('"')) or (clean_v.startswith("'") and clean_v.endswith("'")):
                    if clean_v.count(clean_v[0]) == 2:
                        clean_v = clean_v[1:-1].strip()

            if k in ("pattern", "query", "regex") and "\n" in clean_v:
                clean_v = " ".join(clean_v.split())

            if k in ("old_str", "new_str", "content", "code", "command"):
                if m := RE_MD_CODE_BLOCK.match(clean_v):
                    clean_v = m.group(1).rstrip()

            if k in ("old_str", "new_str"):
                clean_v = _strip_line_number_gutters(clean_v)

            cleaned[k] = clean_v
        else:
            cleaned[k] = v

    # 1. Path Aliases
    if "path" not in cleaned:
        for alt in ("file", "filename", "filepath", "target", "file_path", "target_file"):
            if alt in cleaned:
                cleaned["path"] = cleaned.pop(alt)
                break

    if "path" in cleaned and isinstance(cleaned["path"], str):
        raw_p = cleaned["path"].strip()
        if "\n" in raw_p or "def " in raw_p or len(raw_p) > 100:
            if m := RE_PATH_EXTRACT.search(raw_p):
                cleaned["path"] = m.group(1)
        else:
            cleaned["path"] = raw_p.strip('\'"`\\\n\r\t ').strip()

        # Heal hallucinated sandbox root prefixes
        if m := RE_ROOT_SANDBOX.match(cleaned["path"]):
            if m.group(1):
                cleaned["path"] = m.group(1).strip('\'"')

        # Strip search/grep line and column suffixes (e.g. "mod_a.py:1" -> "mod_a.py")
        cleaned["path"] = re.sub(r":\d+(?::\d+)?$", "", cleaned["path"]).strip()

    # 2. Command Aliases
    if "command" not in cleaned:
        for alt in ("cmd", "exec", "shell_command", "bash"):
            if alt in cleaned:
                cleaned["command"] = cleaned.pop(alt)
                break

    if "command" in cleaned and isinstance(cleaned["command"], str):
        c = cleaned["command"].strip()
        c = RE_CD_COMMAND.sub("", c).strip()
        cleaned["command"] = _close_unterminated_quote(c)

    # 3. Search Pattern Aliases
    if "pattern" not in cleaned:
        for alt in ("query", "regex", "search_term", "match"):
            if alt in cleaned:
                cleaned["pattern"] = cleaned.pop(alt)
                break

    # 4. Content / Code Aliases
    if "content" not in cleaned:
        for alt in ("text", "body", "data", "source"):
            if alt in cleaned:
                cleaned["content"] = cleaned.pop(alt)
                break
        if "content" not in cleaned and "code" in cleaned:
            cleaned["content"] = cleaned["code"]

    # 5. Symbol Aliases
    if "symbol" not in cleaned:
        for alt in ("func", "function", "method", "class_name", "target_symbol"):
            if alt in cleaned:
                cleaned["symbol"] = cleaned.pop(alt)
                break

    # 6. Surgical Edit String Aliases
    if "old_str" not in cleaned:
        for alt in ("old", "old_string", "old_text", "search", "search_str", "target_str", "find", "before", "original"):
            if alt in cleaned and not isinstance(cleaned[alt], bool):
                cleaned["old_str"] = _strip_line_number_gutters(str(cleaned.pop(alt)))
                break

    if "new_str" not in cleaned:
        for alt in ("new", "new_string", "new_text", "replace", "replace_str", "replacement", "after", "update"):
            if alt in cleaned and not isinstance(cleaned[alt], bool) and str(cleaned[alt]).lower() not in ("true", "1", "yes", "on"):
                cleaned["new_str"] = _strip_line_number_gutters(str(cleaned.pop(alt)))
                break

    # 7. Line Range Aliases (read_file)
    if "line_start" not in cleaned:
        for alt in ("start_line", "start", "from_line", "begin"):
            if alt in cleaned:
                try:
                    cleaned["line_start"] = int(cleaned.pop(alt))
                    break
                except (ValueError, TypeError):
                    pass

    if "line_end" not in cleaned:
        for alt in ("end_line", "end", "to_line", "stop"):
            if alt in cleaned:
                try:
                    cleaned["line_end"] = int(cleaned.pop(alt))
                    break
                except (ValueError, TypeError):
                    pass

    # 8. Overwrite Aliases & Booleans
    for alt in ("force", "overwrite_file", "clobber"):
        if alt in cleaned:
            val = cleaned.pop(alt)
            cleaned["overwrite"] = str(val).lower() in ("true", "1", "yes", "on") if not isinstance(val, bool) else val
            break

    if "replace" in cleaned:
        rep_val = cleaned.pop("replace")
        if isinstance(rep_val, bool):
            cleaned["overwrite"] = rep_val
        elif str(rep_val).lower() in ("true", "1", "yes", "on"):
            cleaned["overwrite"] = True
        elif str(rep_val).lower() in ("false", "0", "no", "off"):
            cleaned["overwrite"] = False

    if "overwrite" in cleaned:
        ov = cleaned["overwrite"]
        cleaned["overwrite"] = ov.lower() in ("true", "1", "yes", "on") if isinstance(ov, str) else bool(ov)

    return cleaned


# ── 3. Balanced JSON Object Extractor (Linear Bail-out) ───────────────────────

def _extract_balanced_json(text: str) -> list[dict[str, Any]]:
    """Extracts top-level JSON objects safely by balancing braces, ignoring string contents with linear bail-out."""
    results = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            if text.find("}", i) == -1:
                break
            start = i
            depth, in_str, esc, valid = 0, False, False, False
            for j in range(i, n):
                ch = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            raw_chunk = text[start : j + 1]
                            try:
                                parsed = json.loads(raw_chunk, strict=False)
                                if isinstance(parsed, dict) and ("name" in parsed or "commands" in parsed or "function" in parsed):
                                    results.append(parsed)
                                    valid = True
                            except Exception as e:
                                if os.environ.get("AI_DEBUG") == "1":
                                    sys.stderr.write(f"\r\n[debug] _extract_balanced_json dict parse error: {e}\r\n")
                            break
            if valid:
                i = j + 1
            else:
                i += 1
        elif text[i] == "[":
            if text.find("]", i) == -1:
                break
            start = i
            depth, in_str, esc, valid_list = 0, False, False, False
            for j in range(i, n):
                ch = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                        if depth == 0:
                            raw_chunk = text[start : j + 1]
                            try:
                                parsed = json.loads(raw_chunk, strict=False)
                                if isinstance(parsed, list):
                                    for item in parsed:
                                        if isinstance(item, dict) and "name" in item:
                                            results.append(item)
                                            valid_list = True
                            except Exception as e:
                                if os.environ.get("AI_DEBUG") == "1":
                                    sys.stderr.write(f"\r\n[debug] _extract_balanced_json list parse error: {e}\r\n")
                            break
            if valid_list:
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return results


# ── 4. Self-Healing JSON Argument Parser ──────────────────────────────────────

def heal_tool_call(fname: str, raw_args: str | dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Universal tool adapter for small models: heals parameters, aliases, and misdirected shell calls."""
    healed_dict = heal_json_args(raw_args)

    # 1. Scoped resolution for 'script' / 'cell' aliases based on target tool
    if fname == "exec_python":
        if "script" in healed_dict and "code" not in healed_dict:
            healed_dict["code"] = healed_dict.pop("script")
        if "cell" in healed_dict and "code" not in healed_dict:
            healed_dict["code"] = healed_dict.pop("cell")
        if "code" in healed_dict:
            healed_dict["code"] = RE_BOGUS_IMPORTS.sub("", str(healed_dict["code"])).strip()

    elif fname == "run_command":
        if "script" in healed_dict and "command" not in healed_dict:
            healed_dict["command"] = healed_dict.pop("script")

    # 2. Unified Diff Hunk Recovery for edit_file
    if fname == "edit_file":
        new_val = str(healed_dict.get("new_str", ""))
        old_val = str(healed_dict.get("old_str", ""))
        if ("\n-" in new_val or "\n+" in new_val or new_val.startswith("@@")) and (not old_val or old_val in ("...", "diff")):
            if extracted := _extract_diff_hunk(new_val):
                healed_dict["old_str"], healed_dict["new_str"] = extracted

    # 3. Intercept and heal shell file mutations into native tools
    if fname == "run_command" and "command" in healed_dict:
        cmd_raw = str(healed_dict["command"]).strip()

        # Inline python -c -> exec_python (bail out if trailing shell redirection/pipes exist)
        if cmd_raw.startswith(("python3 -c", "python -c")):
            rest = re.sub(r"^python3?\s+-c\s+", "", cmd_raw).strip()
            py_code = ""
            has_trailing_shell = False
            if rest and rest[0] in ("'", '"'):
                q = rest[0]
                closing_idx = -1
                esc = False
                for idx in range(1, len(rest)):
                    if esc:
                        esc = False
                    elif rest[idx] == "\\":
                        esc = True
                    elif rest[idx] == q:
                        closing_idx = idx
                        break
                if closing_idx != -1:
                    after_quote = rest[closing_idx + 1:].strip()
                    if any(c in after_quote for c in (">", "|", ";", "&")):
                        has_trailing_shell = True
                    py_code = rest[1:closing_idx]
                else:
                    py_code = rest[1:]
            else:
                if any(c in rest for c in (">", "|", ";")):
                    has_trailing_shell = True
                py_code = re.sub(r"\s*(2>&1|\|\|[^|]*|&&[^&]*)$", "", rest).strip()

            if not has_trailing_shell:
                py_code = py_code.replace(r"'\''", "'").replace(r'\"', '"').strip()
                py_code = RE_BOGUS_IMPORTS.sub("", py_code).strip()
                if py_code:
                    return "exec_python", {"code": py_code}

        # Helper to safely move shell output into write_file
        def _safe_shell_write(raw_content: str, path: str, append_nl: bool = False) -> tuple[str, dict[str, Any]] | None:
            if any(exp in raw_content for exp in ("$(", "${", "`")):
                return None
            unescaped = raw_content.replace(r'\"', '"').replace(r"\'", "'").replace(r"\n", "\n").replace(r"\t", "\t")
            if append_nl and not unescaped.endswith("\n"):
                unescaped += "\n"
            return "write_file", {"path": path.strip(), "content": unescaped}

        # Shell cat << 'EOF' > file -> write_file
        if cat_m := RE_CAT_EOF_TARGET_END.match(cmd_raw):
            _, target_path, file_content = cat_m.groups()
            return "write_file", {"path": target_path.strip(), "content": file_content}

        # Shell cat > file << 'EOF' -> write_file
        if cat_start_m := RE_CAT_EOF_TARGET_START.match(cmd_raw):
            target_path, _, file_content = cat_start_m.groups()
            return "write_file", {"path": target_path.strip(), "content": file_content}

        # Shell cat << 'EOF' | tee file -> write_file
        if tee_eof_m := RE_TEE_EOF.match(cmd_raw):
            _, target_path, file_content = tee_eof_m.groups()
            return "write_file", {"path": target_path.strip(), "content": file_content}

        # Shell echo "..." > file -> write_file
        if echo_m := RE_ECHO_REDIRECT.match(cmd_raw):
            file_content, target_path = echo_m.groups()
            if res := _safe_shell_write(file_content, target_path, append_nl=True):
                return res

        # Shell printf "..." > file -> write_file
        if printf_m := RE_PRINTF_REDIRECT.match(cmd_raw):
            file_content, target_path = printf_m.groups()
            if res := _safe_shell_write(file_content, target_path, append_nl=False):
                return res

        # Shell echo "..." | tee file -> write_file
        if tee_echo_m := RE_ECHO_TEE.match(cmd_raw):
            file_content, target_path = tee_echo_m.groups()
            if res := _safe_shell_write(file_content, target_path, append_nl=True):
                return res

    return fname, healed_dict


def heal_json_args(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Self-healing JSON tool argument parser for small quantized models (2B–8B)."""
    if isinstance(raw, dict):
        return normalize_params(raw)
    if not raw or not isinstance(raw, str) or not raw.strip():
        return {}

    cleaned = raw.strip()
    if m := RE_MD_JSON_WRAPPER.search(cleaned):
        cleaned = m.group(1).strip()
    cleaned = RE_XML_TOOL_TAGS.sub("", cleaned).strip()

    # Pass 1: Standard non-strict JSON parse
    try:
        parsed = json.loads(cleaned, strict=False)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except Exception as e:
        if os.environ.get("AI_DEBUG") == "1":
            sys.stderr.write(f"[debug] heal_json_args Pass 1 failed: {e}\n")

    # Pass 2: Stack-based bracket closure tracking true nesting order
    stack = []
    _in_str, _esc = False, False
    for _ch in cleaned:
        if _in_str:
            if _esc:
                _esc = False
            elif _ch == "\\":
                _esc = True
            elif _ch == '"':
                _in_str = False
        elif _ch == '"':
            _in_str = True
        elif _ch in "{[":
            stack.append(_ch)
        elif _ch in "}]" and stack and {"}": "{", "]": "["}[_ch] == stack[-1]:
            stack.pop()

    if _in_str:
        healed = cleaned + '"'
        if stack and stack[-1] == "{":
            stack.pop()
    else:
        healed = cleaned

    healed += "".join("}" if o == "{" else "]" for o in reversed(stack))

    try:
        parsed = json.loads(healed, strict=False)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except Exception as e:
        if os.environ.get("AI_DEBUG") == "1":
            sys.stderr.write(f"[debug] heal_json_args Pass 2 failed: {e}\n")

    # Pass 3: Python ast.literal_eval fallback
    try:
        parsed = ast.literal_eval(cleaned)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except Exception as e:
        if os.environ.get("AI_DEBUG") == "1":
            sys.stderr.write(f"[debug] heal_json_args Pass 3 failed: {e}\n")

    # Pass 4: Multi-line regex field extractor
    extracted: dict[str, Any] = {}
    for match in re.finditer(r'"(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)"\s*:\s*"(?P<val>[\s\S]*?)(?="\s*,\s*"[a-zA-Z_]|\s*"$|\s*\}\s*$)', cleaned):
        extracted[match.group("key")] = match.group("val")

    if not extracted:
        extracted = {
            k: v.strip()
            for k, v in re.findall(
                r'"?([a-zA-Z_][a-zA-Z0-9_]*)"?\s*:\s*["\']?([^,"\']+)["\']?', cleaned
            )
        }
    return normalize_params(extracted)


# ── 5. AST-Based Python Function Call Parser ──────────────────────────────────

def _extract_ast_python_calls(text: str) -> list[dict[str, Any]]:
    calls = []
    tool_names = {
        "read_file",
        "edit_file",
        "write_file",
        "list_dir",
        "run_command",
        "search_code",
        "read_symbol",
        "trace_symbol",
        "blast_radius",
        "find_symbol",
        "architecture_overview",
        "exec_python",
        "final_answer",
    }

    for m in re.finditer(r"\b(?P<name>[a-zA-Z_]\w*)\s*\(", text):
        fname = m.group("name")
        if fname not in tool_names:
            continue
        start_idx = m.start()

        # Prose gating: ignore calls embedded in explanatory text or inline backticks
        line_start = text.rfind("\n", 0, start_idx) + 1
        preceding = text[line_start:start_idx].strip()
        if preceding and not re.match(r"^([a-zA-Z0-9_]+\s*=\s*|print\s*\(?|return\s+)?$", preceding):
            continue
        if start_idx > 0 and text[start_idx - 1] == "`":
            continue

        paren_count = 0
        in_quote = None
        end_idx = None

        for i in range(m.end() - 1, len(text)):
            ch = text[i]
            if in_quote:
                if ch == in_quote:
                    bs_count = 0
                    k = i - 1
                    while k >= start_idx and text[k] == "\\":
                        bs_count += 1
                        k -= 1
                    if bs_count % 2 == 0:
                        in_quote = None
            elif ch in ('"', "'"):
                in_quote = ch
            elif ch == "(":
                paren_count += 1
            elif ch == ")":
                paren_count -= 1
                if paren_count == 0:
                    end_idx = i + 1
                    break

        if end_idx is None:
            continue

        call_expr = text[start_idx:end_idx].strip()
        try:
            tree = ast.parse(call_expr)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    fn = node.func.id
                    args_dict = {}

                    for kw in node.keywords:
                        if isinstance(kw.value, ast.Constant):
                            args_dict[kw.arg] = kw.value.value

                    if fn == "final_answer":
                        raw_call = ast.unparse(node) if hasattr(ast, "unparse") else f"final_answer({ast.dump(node.args[0]) if node.args else ''})"
                        calls.append({
                            "id": f"call_ast_{len(calls)}_{int(time.time())}",
                            "type": "function",
                            "function": {
                                "name": "exec_python",
                                "arguments": json.dumps({"code": raw_call}),
                            },
                        })
                        continue

                    if not args_dict and node.args:
                        arg_keys = (
                            ["path", "old_str", "new_str"]
                            if fn == "edit_file"
                            else (
                                ["command"]
                                if fn == "run_command"
                                else (
                                    ["path", "content", "overwrite"]
                                    if fn == "write_file"
                                    else (
                                        ["pattern", "path"]
                                        if fn in ("search_code", "find_symbol")
                                        else (["code"] if fn == "exec_python" else ["path", "content"])
                                    )
                                )
                            )
                        )
                        for k, val_node in zip(arg_keys, node.args):
                            if isinstance(val_node, ast.Constant):
                                args_dict[k] = val_node.value

                    if args_dict or fn in ("list_dir", "architecture_overview"):
                        calls.append(
                            {
                                "id": f"call_ast_{len(calls)}_{int(time.time())}",
                                "type": "function",
                                "function": {
                                    "name": fn,
                                    "arguments": json.dumps(normalize_params(args_dict)),
                                },
                            }
                        )
        except Exception as e:
            if os.environ.get("AI_DEBUG") == "1":
                sys.stderr.write(f"[debug] _extract_ast_python_calls error: {e}\n")

    return calls


# ── 6. Universal Fallback Tool Extraction Suite ───────────────────────────────

def extract_fallback_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extracts and normalizes tool calls across non-standard model formats."""
    if not text or not text.strip():
        return []

    calls = []

    # Format 1: Hermes 3.x XML Format
    for i, m in enumerate(RE_HERMES_XML.finditer(text)):
        fname = m.group("name").strip()
        raw_params = m.group("params")
        params = {
            pm.group("key").strip(): pm.group("val").strip()
            for pm in RE_HERMES_PARAM.finditer(raw_params)
        }
        calls.append(
            {
                "id": f"call_hermes_{i}_{int(time.time())}",
                "type": "function",
                "function": {
                    "name": fname,
                    "arguments": json.dumps(normalize_params(params)),
                },
            }
        )

    # Format 2: DeepSeek & Liquid DSML Format
    if not calls:
        for i, m in enumerate(RE_DSML.finditer(text)):
            args_val = m.group("args")
            if args_val is not None:
                raw_args = args_val.replace('\\"', '"').replace("\\\\", "\\")
                calls.append(
                    {
                        "id": f"call_dsml_{i}_{int(time.time())}",
                        "type": "function",
                        "function": {
                            "name": m.group("name"),
                            "arguments": json.dumps(heal_json_args(raw_args)),
                        },
                    }
                )

    # Format 3: Mistral Format
    if not calls and (mm := RE_MISTRAL.search(text)):
        try:
            for i, c in enumerate(json.loads(mm.group("calls"), strict=False)):
                calls.append(
                    {
                        "id": f"call_mistral_{i}_{int(time.time())}",
                        "type": "function",
                        "function": {
                            "name": c.get("name"),
                            "arguments": json.dumps(
                                normalize_params(c.get("arguments", {}))
                            ),
                        },
                    }
                )
        except Exception:
            pass

    # Format 3.5: Ling 3.0 / Bailing V3 Tagged Format
    if not calls:
        for i, m in enumerate(RE_LING_XML.finditer(text)):
            fname = m.group("name").strip()
            raw_params = m.group("params")
            params = {
                pm.group("key").strip(): pm.group("val").strip()
                for pm in RE_LING_PARAM.finditer(raw_params)
            }
            if params:
                calls.append(
                    {
                        "id": f"call_ling_{i}_{int(time.time())}",
                        "type": "function",
                        "function": {
                            "name": fname,
                            "arguments": json.dumps(normalize_params(params)),
                        },
                    }
                )

    # Format 4: Standard XML/JSON Format (<tool_call>{...}</tool_call>)
    if not calls:
        for i, m in enumerate(RE_XML_TOOL_CALL.finditer(text)):
            payload = m.group("payload").strip()
            if obj_list := _extract_balanced_json(payload):
                for obj in obj_list:
                    if "name" in obj:
                        raw_args = obj.get("arguments") or obj.get("parameters") or {}
                        calls.append({
                            "id": f"call_xml_{i}_{int(time.time())}",
                            "type": "function",
                            "function": {"name": obj["name"], "arguments": json.dumps(heal_json_args(raw_args))},
                        })

    # Format 5: Balanced Naked JSON Objects ({"name": ..., "arguments": ...})
    if not calls:
        balanced_objs = _extract_balanced_json(text)
        for i, obj in enumerate(balanced_objs):
            has_args = any(k in obj for k in ("arguments", "parameters", "args", "input"))
            fname = obj.get("name", "")
            is_valid_fn = isinstance(fname, str) and bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", fname))

            if is_valid_fn and has_args:
                raw_args = obj.get("arguments") or obj.get("parameters") or obj.get("args") or obj.get("input") or {}
                healed = heal_json_args(raw_args)
                calls.append(
                    {
                        "id": f"call_naked_{i}_{int(time.time())}",
                        "type": "function",
                        "function": {"name": fname, "arguments": json.dumps(healed)},
                    }
                )
            elif "commands" in obj and isinstance(obj["commands"], list):
                for cmd_item in obj["commands"]:
                    if isinstance(cmd_item, dict):
                        cmd_str = (
                            cmd_item.get("command")
                            or cmd_item.get("keystrokes")
                            or cmd_item.get("cmd")
                            or ""
                        ).strip()
                        if cmd_str:
                            calls.append(
                                {
                                    "id": f"call_liquid_plan_{i}_{int(time.time())}",
                                    "type": "function",
                                    "function": {
                                        "name": "run_command",
                                        "arguments": json.dumps({"command": cmd_str}),
                                    },
                                }
                            )

    # Format 6: AST-Parsed Python Function Calls
    if not calls:
        calls = _extract_ast_python_calls(text)

    # Format 7: Standalone Python Markdown Code Block Auto-Execution
    if not calls and ("```python" in text or "```py" in text):
        py_blocks = RE_MD_PY_WRAPPER.findall(text)
        for i, code_block in enumerate(py_blocks):
            clean_block = code_block.strip()
            if any(k in clean_block for k in ("final_answer(", "open(", "read_file(", "os.listdir(", "glob.", "edit_file(", "write_file(")):
                clean_block = RE_BOGUS_IMPORTS.sub("", clean_block).strip()
                calls.append({
                    "id": f"call_py_block_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": "exec_python",
                        "arguments": json.dumps({"code": clean_block}),
                    },
                })
                break

    return calls
