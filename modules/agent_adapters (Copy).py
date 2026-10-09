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
RE_MD_JSON_WRAPPER = re.compile(r"^\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*$", re.DOTALL)
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

RE_ECHO_REDIRECT = re.compile(
    r"^(?P<cmd>echo|printf)\s+(?P<flags>-[a-zA-Z]+\s+)?(?P<quote>['\"])(?P<content>[\s\S]*?)(?P=quote)\s*>\s*(?P<target>\S+)$",
    re.DOTALL,
)
RE_ECHO_TEE = re.compile(
    r"^(?P<cmd>echo|printf)\s+(?P<flags>-[a-zA-Z]+\s+)?(?P<quote>['\"])(?P<content>[\s\S]*?)(?P=quote)\s*\|\s*(?:sudo\s+)?tee\s+(?P<target>\S+)$",
    re.DOTALL,
)

RE_BOGUS_IMPORTS = re.compile(
    r"^\s*(?:from\s+[\w\.]+\s+import\s+(?:final_answer|exec_python)\b|import\s+(?:final_answer|exec_python)\b)\s*;?\s*",
    re.MULTILINE,
)

RE_GUTTER_LINE = re.compile(r"^\s*\d+[:|│\t ]\s?")


def _close_unterminated_quote(cmd_str: str) -> str:
    """State machine quote balancing: balances quotes genuinely unclosed at the end of a command."""
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
    """Strips copied editor line number gutters from old_str or new_str only when monotonic numbering is detected."""
    if not text:
        return text

    if "\n" not in text:
        if m := re.match(r"^\s*\d+(?:\s*[|│]|\s*:\s{2,}|\t)\s?(.*)$", text):
            return m.group(1)
        return text

    lines = text.splitlines(keepends=True)
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) < 2:
        return text

    gutter_nums = []
    for l in non_empty:
        if m := re.match(r"^\s*(\d+)[:|│\t ]", l):
            gutter_nums.append(int(m.group(1)))

    if len(gutter_nums) >= 2 and len(gutter_nums) / len(non_empty) >= 0.6:
        is_monotonic = all(b - a in (1, 2) for a, b in zip(gutter_nums, gutter_nums[1:]))
        if is_monotonic:
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
    has_hunk_header = any(re.match(r"^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@", l) for l in lines)
    if not has_hunk_header and not any(l.startswith(("--- ", "+++ ")) for l in lines):
        return None

    old_lines: list[str] = []
    new_lines: list[str] = []
    in_hunk = False

    for line in lines:
        if line.startswith("@@"):
            if in_hunk:
                break
            in_hunk = True
            continue
        if line.startswith(("---", "+++")):
            continue
        if in_hunk:
            if line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])
            elif line.startswith(" "):
                old_lines.append(line[1:])
                new_lines.append(line[1:])
            else:
                old_lines.append(line)
                new_lines.append(line)

    if old_lines or new_lines:
        return "\n".join(old_lines), "\n".join(new_lines)
    return None


def deduplicate_tool_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prunes duplicate parallel tool calls emitted within a single assistant turn."""
    if not calls or len(calls) <= 1:
        return calls
    seen = set()
    unique = []
    for idx, call in enumerate(calls):
        fn = call.get("function", {})
        name = fn.get("name", "")
        raw_args = fn.get("arguments", "")
        try:
            parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            norm_args = json.dumps(parsed, sort_keys=True, default=str)
        except Exception:
            norm_args = str(raw_args)

        if not name and not norm_args:
            key = ("__raw_call__", call.get("id", str(idx)), idx)
        else:
            key = (name, norm_args)

        if key not in seen:
            seen.add(key)
            unique.append(call)
    return unique


# ── 2. Parameter Aliases & String Normalization ───────────────────────────────

def normalize_params(args: dict[str, Any]) -> dict[str, Any]:
    """Auto-heals parameter alias discrepancies, wrapped quotes, and escaped command syntax."""
    if not isinstance(args, dict):
        return {}

    cleaned: dict[str, Any] = {}
    for k, v in args.items():
        if v is None or v == "null":
            continue
        if isinstance(v, str):
            clean_v = v
            if k not in ("old_str", "new_str", "content", "code"):
                stripped = clean_v.strip()
                if len(stripped) >= 2 and stripped.count(stripped[0]) == 2:
                    if (stripped.startswith('"') and stripped.endswith('"')) or (stripped.startswith("'") and stripped.endswith("'")):
                        inner = stripped[1:-1]
                        if inner[:1] not in ("'", '"') and inner[-1:] not in ("'", '"'):
                            clean_v = inner
                clean_v = clean_v.strip()

            # Schema anchor bleed repair (e.g. "^calc.py$" -> "calc.py")
            if k not in ("pattern", "regex") and len(clean_v) > 2 and clean_v.startswith("^") and clean_v.endswith("$"):
                clean_v = clean_v[1:-1].strip()

            if k in ("pattern", "query") and "\n" in clean_v:
                clean_v = clean_v.replace("\r\n", "\n")

            if k in ("old_str", "new_str", "content", "code", "command"):
                if m := RE_MD_CODE_BLOCK.match(clean_v):
                    clean_v = m.group(1).rstrip()
                elif clean_v.startswith("```") and clean_v.endswith("```") and len(clean_v) >= 6:
                    clean_v = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", clean_v)
                    clean_v = re.sub(r"\s*```$", "", clean_v)

            if k in ("old_str", "new_str"):
                clean_v = _strip_line_number_gutters(clean_v)

            cleaned[k] = clean_v
        else:
            cleaned[k] = v

    # 1. Path Aliases & Leading Slash Normalization
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
            cleaned["path"] = raw_p.strip('\'"`\\\n\r\t ')

        if m := RE_ROOT_SANDBOX.match(cleaned["path"]):
            rem = m.group(1)
            cleaned["path"] = rem.strip('\'"`\\\n\r\t ') if rem else "."

        # Strip accidental leading slashes on workspace relative files
        if cleaned["path"].startswith("/") and not cleaned["path"].startswith(("/home", "/workspace")):
            cleaned["path"] = cleaned["path"].lstrip("/")

        if m := re.search(r":(\d{1,6})(?::\d{1,6})?$", cleaned["path"]):
            stem = cleaned["path"][: m.start()]
            if os.path.splitext(stem)[1] or os.path.exists(stem):
                cleaned["path"] = stem.strip()

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

    # 6. Surgical Edit String Aliases & Unified Diff Parameter Recovery
    if "old_str" not in cleaned:
        for alt in ("old", "old_string", "old_text", "search", "search_str", "target_str", "find", "before", "original"):
            if alt in cleaned and not isinstance(cleaned[alt], bool):
                cleaned["old_str"] = _strip_line_number_gutters(str(cleaned.pop(alt)))
                break

    if "new_str" not in cleaned:
        for alt in ("new", "new_string", "new_text", "replace_str", "replacement", "after", "update", "patch", "diff", "unified_diff", "hunk"):
            if alt in cleaned and not isinstance(cleaned[alt], bool) and str(cleaned[alt]).lower() not in ("true", "1", "yes", "on"):
                cleaned["new_str"] = _strip_line_number_gutters(str(cleaned.pop(alt)))
                break

    # 7. Line Range Aliases & Numeric String Coercion
    if "line_start" not in cleaned:
        for alt in ("start_line", "start", "from_line", "begin"):
            if alt in cleaned:
                try:
                    val = int(cleaned[alt])
                    cleaned["line_start"] = val
                    cleaned.pop(alt)
                    break
                except (ValueError, TypeError):
                    pass
    elif isinstance(cleaned.get("line_start"), str):
        try:
            cleaned["line_start"] = int(cleaned["line_start"])
        except ValueError:
            pass

    if "line_end" not in cleaned:
        for alt in ("end_line", "end", "to_line", "stop"):
            if alt in cleaned:
                try:
                    val = int(cleaned[alt])
                    cleaned["line_end"] = val
                    cleaned.pop(alt)
                    break
                except (ValueError, TypeError):
                    pass
    elif isinstance(cleaned.get("line_end"), str):
        try:
            cleaned["line_end"] = int(cleaned["line_end"])
        except ValueError:
            pass

    # 8. Overwrite & Precedence Disambiguation
    if "overwrite" not in cleaned:
        for alt in ("force", "overwrite_file", "clobber"):
            if alt in cleaned:
                val = cleaned.pop(alt)
                cleaned["overwrite"] = str(val).lower() in ("true", "1", "yes", "on") if not isinstance(val, bool) else val
                break

    if "replace" in cleaned:
        rep_val = cleaned["replace"]
        if isinstance(rep_val, bool) or (isinstance(rep_val, str) and len(rep_val) <= 5 and rep_val.lower() in ("true", "false", "1", "0", "yes", "no", "on", "off")):
            if "overwrite" not in cleaned:
                cleaned["overwrite"] = rep_val if isinstance(rep_val, bool) else rep_val.lower() in ("true", "1", "yes", "on")
            cleaned.pop("replace")
        elif "new_str" not in cleaned:
            cleaned["new_str"] = str(cleaned.pop("replace"))

    return cleaned


# ── 3. Balanced JSON Object Extractor ─────────────────────────────────────────

def _extract_balanced_json(text: str) -> list[dict[str, Any]]:
    """Extracts top-level JSON objects safely by balancing braces with linear bail-out."""
    if not text or len(text) > 200_000:
        return []

    results = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            if text.find("}", i) == -1:
                i += 1
                continue
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
                            except Exception:
                                pass
                            break
            if valid:
                i = j + 1
            else:
                i += 1
        elif text[i] == "[":
            if text.find("]", i) == -1:
                i += 1
                continue
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
                            except Exception:
                                pass
                            break
            if valid_list:
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return results


# ── 4. Self-Healing Tool Call Transformer ─────────────────────────────────────

def _parse_heredoc(cmd: str) -> tuple[str, str, bool] | None:
    """Parses shell heredoc syntax without regex backtracking, tracking delimiter quoting."""
    lines = cmd.splitlines()
    if not lines or len(lines) < 2:
        return None
    first = lines[0].strip()

    m1 = re.match(r"^cat\s*<<\s*(?P<q>['\"]?)(\w+)(?P=q)\s*>\s*(\S+)$", first)
    if m1:
        is_quoted = bool(m1.group("q"))
        delim, path = m1.group(2), m1.group(3)
        target_lines = []
        for l in lines[1:]:
            if l.strip() == delim:
                return path.strip(), "\n".join(target_lines), is_quoted
            target_lines.append(l)
        return None

    m2 = re.match(r"^cat\s*>\s*(\S+)\s*<<\s*(?P<q>['\"]?)(\w+)(?P=q)$", first)
    if m2:
        is_quoted = bool(m2.group("q"))
        path, delim = m2.group(1), m2.group(3)
        target_lines = []
        for l in lines[1:]:
            if l.strip() == delim:
                return path.strip(), "\n".join(target_lines), is_quoted
            target_lines.append(l)
        return None

    m3 = re.match(r"^cat\s*<<\s*(?P<q>['\"]?)(\w+)(?P=q)\s*\|\s*(?:sudo\s+)?tee\s+(\S+)$", first)
    if m3:
        is_quoted = bool(m3.group("q"))
        delim, path = m3.group(2), m3.group(3)
        target_lines = []
        for l in lines[1:]:
            if l.strip() == delim:
                return path.strip(), "\n".join(target_lines), is_quoted
            target_lines.append(l)
        return None

    return None


def heal_tool_call(fname: str, raw_args: str | dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Universal tool adapter: heals parameters, aliases, diffs, and shell file mutations."""
    healed_dict = heal_json_args(raw_args)

    if fname in ("write_file", "edit_file") and "mode" in healed_dict and "overwrite" not in healed_dict:
        m_val = str(healed_dict.pop("mode")).lower()
        healed_dict["overwrite"] = m_val in ("w", "write", "overwrite", "truncate")

    # 1. Scoped resolution for 'script' / 'cell' aliases
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
        for diff_k in ("patch", "diff", "unified_diff", "hunk"):
            if diff_k in healed_dict and "new_str" not in healed_dict:
                healed_dict["new_str"] = healed_dict.pop(diff_k)
                break
        new_val = str(healed_dict.get("new_str", ""))
        old_val = str(healed_dict.get("old_str", ""))
        has_real_diff_header = new_val.startswith("@@") or "\n@@" in new_val or "--- " in new_val
        if has_real_diff_header and (not old_val or old_val in ("...", "diff", "")):
            if extracted := _extract_diff_hunk(new_val):
                healed_dict["old_str"], healed_dict["new_str"] = extracted

    # 3. Intercept and heal shell file mutations into native tools
    if fname == "run_command" and "command" in healed_dict:
        cmd_full = str(healed_dict["command"]).strip()
        if len(cmd_full) > 100_000:
            return fname, healed_dict

        has_touch = bool(re.match(r"^\s*touch\s+\S+\s*(&&|;)\s*", cmd_full))
        cmd_raw = re.sub(r"^\s*touch\s+\S+\s*(&&|;)\s*", "", cmd_full).strip() if has_touch else cmd_full

        # Inline python -c -> exec_python
        if cmd_raw.startswith(("python3 -c", "python -c")):
            rest = re.sub(r"^python3?\s+-c\s+", "", cmd_raw).strip()
            rest_clean = re.sub(r"\s*(2>&1|\|\|\s*true|&&\s*true)\s*$", "", rest).strip()

            py_code = ""
            quote_char = None
            has_trailing_shell = False

            if rest_clean and rest_clean[0] in ("'", '"'):
                q = rest_clean[0]
                quote_char = q
                closing_idx = -1
                esc = False
                for idx in range(1, len(rest_clean)):
                    if esc:
                        esc = False
                    elif rest_clean[idx] == "\\":
                        esc = True
                    elif rest_clean[idx] == q:
                        closing_idx = idx
                        break
                if closing_idx != -1:
                    after_quote = rest_clean[closing_idx + 1:].strip()
                    if any(c in after_quote for c in (">", "|", ";", "&")):
                        has_trailing_shell = True
                    py_code = rest_clean[1:closing_idx]
                else:
                    py_code = rest_clean[1:]
            else:
                if any(c in rest_clean for c in (">", "|", ";", "&")):
                    has_trailing_shell = True
                py_code = rest_clean

            if not has_trailing_shell:
                if quote_char == "'":
                    py_code = py_code.replace(r"'\''", "'").strip()
                elif quote_char == '"':
                    py_code = py_code.replace(r'\"', '"').replace(r"\\", "\\").strip()
                else:
                    py_code = py_code.strip()

                py_code = RE_BOGUS_IMPORTS.sub("", py_code).strip()
                if py_code:
                    return "exec_python", {"code": py_code}

        def _safe_shell_write(cmd_type: str, raw_content: str, path: str, is_single_quote: bool, is_echo_e: bool, append_nl: bool = False) -> tuple[str, dict[str, Any]] | None:
            if any(exp in raw_content for exp in ("$(", "${", "`")):
                return None
            if cmd_type == "printf" and re.search(r"%[a-zA-Z]", raw_content):
                return None

            if is_single_quote:
                unescaped = raw_content.replace(r"'\''", "'")
            elif is_echo_e or cmd_type == "printf":
                unescaped = raw_content.replace("\\\\", "\x00").replace(r'\"', '"').replace(r"\n", "\n").replace(r"\t", "\t").replace("\x00", "\\")
            else:
                unescaped = raw_content.replace("\\\\", "\x00").replace(r'\"', '"').replace("\x00", "\\")

            norm = normalize_params({"path": path.strip(), "content": unescaped})
            if append_nl and isinstance(norm.get("content"), str) and not norm["content"].endswith("\n"):
                norm["content"] += "\n"
            return "write_file", norm

        if heredoc_res := _parse_heredoc(cmd_raw):
            target_path, file_content, is_quoted = heredoc_res
            if is_quoted or not re.search(r"[\$`*?]", file_content):
                if not any(exp in file_content for exp in ("$(", "${", "`")):
                    return "write_file", normalize_params({"path": target_path.strip(), "content": file_content})

        if echo_m := RE_ECHO_REDIRECT.match(cmd_raw):
            cmd_type = echo_m.group("cmd")
            is_single = echo_m.group("quote") == "'"
            is_echo_e = bool(echo_m.group("flags") and "-e" in echo_m.group("flags"))
            if res := _safe_shell_write(cmd_type, echo_m.group("content"), echo_m.group("target"), is_single_quote=(is_single and not is_echo_e), is_echo_e=is_echo_e, append_nl=(cmd_type == "echo")):
                return res

        if tee_echo_m := RE_ECHO_TEE.match(cmd_raw):
            cmd_type = tee_echo_m.group("cmd")
            is_single = tee_echo_m.group("quote") == "'"
            is_echo_e = bool(tee_echo_m.group("flags") and "-e" in tee_echo_m.group("flags"))
            if res := _safe_shell_write(cmd_type, tee_echo_m.group("content"), tee_echo_m.group("target"), is_single_quote=(is_single and not is_echo_e), is_echo_e=is_echo_e, append_nl=(cmd_type == "echo")):
                return res

    return fname, healed_dict


def heal_json_args(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Self-healing JSON tool argument parser for small quantized models (2B–35B)."""
    if isinstance(raw, dict):
        return normalize_params(raw)
    if not raw or not isinstance(raw, str) or not raw.strip():
        return {}

    cleaned = raw.strip()

    # Bare string auto-wrapping (e.g. raw "calc.py" -> {"path": "calc.py"})
    if not cleaned.startswith(("{", "[", "```", "<")):
        if "\n" not in cleaned and re.search(r"\.[a-zA-Z0-9]+$", cleaned):
            return normalize_params({"path": cleaned})
        if cleaned.startswith(("python ", "python3 ", "pytest", "ls ", "cat ", "git ", "find ")):
            return normalize_params({"command": cleaned})

    # Pass 1: Direct JSON parse on clean payload without destructive stripping
    try:
        parsed = json.loads(cleaned, strict=False)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except Exception:
        pass

    # Unwrap only when entire argument payload is enclosed in a Markdown fence
    if cleaned.startswith("```") and cleaned.endswith("```"):
        if m := RE_MD_JSON_WRAPPER.match(cleaned):
            cleaned = m.group(1).strip()
            try:
                parsed = json.loads(cleaned, strict=False)
                if isinstance(parsed, dict):
                    return normalize_params(parsed)
            except Exception:
                pass

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
    except Exception:
        pass

    # Pass 3: Python ast.literal_eval fallback
    try:
        parsed = ast.literal_eval(cleaned)
        if isinstance(parsed, dict):
            clean_dict = {str(k): (str(v) if isinstance(v, (bytes, set)) else v) for k, v in parsed.items()}
            return normalize_params(clean_dict)
    except Exception:
        pass

    # Pass 4: Fallback cleanup only when direct structured parses failed
    fallback_cleaned = RE_XML_TOOL_TAGS.sub("", cleaned).strip()
    extracted: dict[str, Any] = {}
    for match in re.finditer(r'"(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)"\s*:\s*"(?P<val>[\s\S]*?)(?="\s*,\s*"[a-zA-Z_]|\s*"$|\s*\}\s*$)', fallback_cleaned):
        val = match.group("val")
        if val.count('"') % 2 == 0 and val.count('{') == val.count('}'):
            extracted[match.group("key")] = val

    if not extracted:
        for k, v in re.findall(r'"?([a-zA-Z_][a-zA-Z0-9_]*)"?\s*:\s*["\']?([^,"\']+)["\']?', fallback_cleaned):
            if v.count('"') % 2 == 0:
                extracted[k] = v.strip()

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

    last_end = 0
    for m in re.finditer(r"\b(?P<name>[a-zA-Z_]\w*)\s*\(", text):
        fname = m.group("name")
        if fname not in tool_names:
            continue
        start_idx = m.start()
        if start_idx < last_end:
            continue

        line_start = text.rfind("\n", 0, start_idx) + 1
        preceding = text[line_start:start_idx].strip()
        if preceding and not re.match(r"^([a-zA-Z0-9_]+\s*=\s*|print\s*\(?|return\s+)?$", preceding):
            continue
        if start_idx > 0 and text[start_idx - 1] == "`":
            continue

        paren_count = 0
        in_quote = None
        end_idx = None

        max_lookahead = min(len(text), m.end() + 30_000)
        for i in range(m.end() - 1, max_lookahead):
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

        last_end = end_idx
        call_expr = text[start_idx:end_idx].strip()

        try:
            tree = ast.parse(call_expr)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    fn = node.func.id
                    args_dict = {}

                    if node.args:
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

                    for kw in node.keywords:
                        if kw.arg is not None and isinstance(kw.value, ast.Constant):
                            args_dict[kw.arg] = kw.value.value

                    if fn == "final_answer":
                        raw_call = ast.unparse(node) if hasattr(ast, "unparse") else f"final_answer({ast.dump(node.args[0]) if node.args else ''})"
                        calls.append({
                            "id": f"call_ast_{len(calls)}_{int(time.time())}",
                            "type": "function",
                            "function": {
                                "name": "exec_python",
                                "arguments": json.dumps({"code": raw_call}, default=str),
                            },
                        })
                        continue

                    if args_dict or fn in ("list_dir", "architecture_overview"):
                        calls.append(
                            {
                                "id": f"call_ast_{len(calls)}_{int(time.time())}",
                                "type": "function",
                                "function": {
                                    "name": fn,
                                    "arguments": json.dumps(normalize_params(args_dict), default=str),
                                },
                            }
                        )
        except Exception:
            pass

    return calls


# ── 6. Universal Fallback Tool Extraction Suite ───────────────────────────────

def extract_fallback_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extracts, heals, and deduplicates tool calls across non-standard model formats."""
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
        if fname:
            calls.append(
                {
                    "id": f"call_hermes_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": fname,
                        "arguments": json.dumps(normalize_params(params), default=str),
                    },
                }
            )

    # Format 2: DeepSeek & Liquid DSML Format
    for i, m in enumerate(RE_DSML.finditer(text)):
        fname = m.group("name").strip()
        args_val = m.group("args")
        if fname and args_val is not None:
            raw_args = args_val.replace('\\"', '"').replace("\\\\", "\\")
            calls.append(
                {
                    "id": f"call_dsml_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": fname,
                        "arguments": json.dumps(heal_json_args(raw_args), default=str),
                    },
                }
            )

    # Format 3: Mistral Format
    if mm := RE_MISTRAL.search(text):
        try:
            for i, c in enumerate(json.loads(mm.group("calls"), strict=False)):
                fname = c.get("name")
                if isinstance(fname, str) and fname.strip():
                    calls.append(
                        {
                            "id": f"call_mistral_{i}_{int(time.time())}",
                            "type": "function",
                            "function": {
                                "name": fname.strip(),
                                "arguments": json.dumps(
                                    heal_json_args(c.get("arguments", {})), default=str
                                ),
                            },
                        }
                    )
        except Exception:
            pass

    # Format 3.5: Ling 3.0 / Bailing V3 Tagged Format
    for i, m in enumerate(RE_LING_XML.finditer(text)):
        fname = m.group("name").strip()
        raw_params = m.group("params")
        params = {
            pm.group("key").strip(): pm.group("val").strip()
            for pm in RE_LING_PARAM.finditer(raw_params)
        }
        if fname and params:
            calls.append(
                {
                    "id": f"call_ling_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": fname,
                        "arguments": json.dumps(normalize_params(params), default=str),
                    },
                }
            )

    # Format 4: Standard XML/JSON Format (<tool_call>{...}</tool_call>)
    for i, m in enumerate(RE_XML_TOOL_CALL.finditer(text)):
        payload = m.group("payload").strip()
        if obj_list := _extract_balanced_json(payload):
            for obj in obj_list:
                fname = obj.get("name")
                if isinstance(fname, str) and fname.strip():
                    raw_args = obj.get("arguments") or obj.get("parameters") or {}
                    calls.append({
                        "id": f"call_xml_{i}_{int(time.time())}",
                        "type": "function",
                        "function": {"name": fname.strip(), "arguments": json.dumps(heal_json_args(raw_args), default=str)},
                    })

    # Format 5: Balanced Naked JSON Objects ({"name": ..., "arguments": ...})
    balanced_objs = _extract_balanced_json(text)
    for i, obj in enumerate(balanced_objs):
        has_args = any(k in obj for k in ("arguments", "parameters", "args", "input"))
        fname = obj.get("name", "")
        is_valid_fn = isinstance(fname, str) and bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", fname.strip()))

        if is_valid_fn and has_args:
            raw_args = obj.get("arguments") or obj.get("parameters") or obj.get("args") or obj.get("input") or {}
            healed = heal_json_args(raw_args)
            calls.append(
                {
                    "id": f"call_naked_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {"name": fname.strip(), "arguments": json.dumps(healed, default=str)},
                }
            )
        elif "commands" in obj and isinstance(obj["commands"], list):
            for cmd_item in obj["commands"]:
                if isinstance(cmd_item, dict):
                    raw_cmd = (
                        cmd_item.get("command")
                        or cmd_item.get("keystrokes")
                        or cmd_item.get("cmd")
                        or ""
                    )
                    if isinstance(raw_cmd, (list, tuple)):
                        raw_cmd = " ".join(str(x) for x in raw_cmd)
                    cmd_str = str(raw_cmd).strip()
                    if cmd_str:
                        calls.append(
                            {
                                "id": f"call_liquid_plan_{i}_{int(time.time())}",
                                "type": "function",
                                "function": {
                                    "name": "run_command",
                                    "arguments": json.dumps({"command": cmd_str}, default=str),
                                },
                            }
                        )

    # Format 6: AST-Parsed Python Function Calls
    calls.extend(_extract_ast_python_calls(text))

    # Format 7: Standalone Python Markdown Code Block Auto-Execution
    from agent_state import get_state
    is_py_active = get_state("ipython_mode", False) or os.environ.get("AI_IPYTHON_MODE") == "1"
    if (is_py_active or "final_answer(" in text) and not calls and re.search(r"```(?:py|python)\b", text, re.IGNORECASE):
        py_blocks = re.findall(
            r"```(?:py|python)[a-zA-Z0-9_+-]*[ \t]*\n([\s\S]+?)(?:\n```|\Z)", text, re.IGNORECASE
        )
        for i, code_block in enumerate(py_blocks):
            clean_block = code_block.strip()
            triggers = ("final_answer(", "open(", "read_file(", "os.listdir(", "glob.", "edit_file(", "write_file(") if is_py_active else ("final_answer(",)
            if any(k in clean_block for k in triggers):
                clean_block = RE_BOGUS_IMPORTS.sub("", clean_block).strip()
                calls.append({
                    "id": f"call_py_block_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": "exec_python",
                        "arguments": json.dumps({"code": clean_block}, default=str),
                    },
                })
                break

    return deduplicate_tool_calls(calls)
