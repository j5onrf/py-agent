#!/usr/bin/env python3
"""Tool Format Adapters & Self-Healing Parser for Small-Models"""

import ast
import json
import re
import time
from typing import Any

# ── 1. Compiled Regex Interceptors ────────────────────────────────────────────

RE_HERMES_XML = re.compile(
    r"<tool_call>\s*<function=(?P<name>[^>]+)>\s*(?P<params>[\s\S]*?)\s*</function>\s*</tool_call>",
    re.DOTALL,
)
RE_HERMES_PARAM = re.compile(
    r"<parameter=(?P<key>[^>]+)>\s*(?P<val>[\s\S]*?)\s*</parameter>", re.DOTALL
)
RE_DSML = re.compile(
    r"<｜DSML｜invoke\s+name=[\"'](?P<name>[^\"']+)[\"']\s+arguments=[\"'](?P<args>[\s\S]*?)[\"']\s*/>",
    re.DOTALL,
)
RE_MISTRAL = re.compile(r"\[TOOL_CALLS\]\s*(?P<calls>\[[\s\S]*?\])", re.DOTALL)
RE_XML_JSON = re.compile(
    r"<tool_call>\s*\{?[\s\S]*?\"name\":\s*\"(?P<name>[^\"]+)\"[\s\S]*?\"arguments\":\s*(?P<args>\{[\s\S]*?\})\s*\}?\s*</tool_call>",
    re.DOTALL,
)
RE_MD_JSON_WRAPPER = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.DOTALL)
RE_XML_TOOL_TAGS = re.compile(
    r"<\|?[a-zA-Z_]+_call_?(?:start|end)?\|?>|</?tool_call>|</?function[^>]*>|</?parameter[^>]*>|<｜/?DSML｜(?:function_calls)?>",
    re.DOTALL,
)
RE_PATH_EXTRACT = re.compile(
    r"([a-zA-Z0-9_\-\./]+\.(?:py|json|md|txt|sh|html|css|js|ts|cpp|c|h|rs|go))"
)


# ── 2. Parameter Aliases & String Normalization ───────────────────────────────

def normalize_params(args: dict[str, Any]) -> dict[str, Any]:
    """Auto-heals parameter alias discrepancies, wrapped quotes, and escaped command syntax from small models."""
    if not isinstance(args, dict):
        return {}

    cleaned: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str):
            clean_v = v.strip().strip("'\"").strip()
            if k in ("pattern", "query", "regex") and "\n" in clean_v:
                clean_v = " ".join(clean_v.split())
            cleaned[k] = clean_v
        else:
            cleaned[k] = v

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

    if "command" not in cleaned:
        for alt in ("cmd", "exec", "shell_command", "script", "bash"):
            if alt in cleaned:
                cleaned["command"] = cleaned.pop(alt)
                break

    if "command" in cleaned and isinstance(cleaned["command"], str):
        c = cleaned["command"].strip()
        if r"\"" in c or r"\'" in c:
            c = c.replace(r"\"", '"').replace(r"\'", "'")
        cleaned["command"] = c

    if "pattern" not in cleaned:
        for alt in ("query", "regex", "search_term", "find", "match"):
            if alt in cleaned:
                cleaned["pattern"] = cleaned.pop(alt)
                break

    if "content" not in cleaned:
        for alt in ("text", "code", "body", "data", "source"):
            if alt in cleaned:
                cleaned["content"] = cleaned.pop(alt)
                break

    if "symbol" not in cleaned:
        for alt in ("func", "function", "method", "class_name", "target_symbol"):
            if alt in cleaned:
                cleaned["symbol"] = cleaned.pop(alt)
                break

    return cleaned


# ── 3. Balanced JSON Object Extractor ─────────────────────────────────────────

def _extract_balanced_json(text: str) -> list[dict[str, Any]]:
    """Extracts top-level JSON objects safely by balancing braces and ignoring braces inside strings."""
    results = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "{":
            start = i
            depth = 0
            in_str = False
            esc = False
            valid = False
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
                                if isinstance(parsed, dict) and ("name" in parsed or "commands" in parsed):
                                    results.append(parsed)
                                    valid = True
                            except Exception:
                                pass
                            i = j
                            break
            if not valid:
                i += 1
        elif text[i] == "[":
            start = i
            depth = 0
            in_str = False
            esc = False
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
                            except Exception:
                                pass
                            i = j
                            break
            i += 1
        else:
            i += 1
    return results


# ── 4. Self-Healing JSON Argument Parser ──────────────────────────────────────

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

    # Pass 1: Strict False standard parse (handles unescaped literal newlines in strings)
    try:
        parsed = json.loads(cleaned, strict=False)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except Exception:
        pass

    # Pass 2: Heuristic bracket closure
    ob, cb = cleaned.count("{"), cleaned.count("}")
    ok, ck = cleaned.count("["), cleaned.count("]")
    healed = cleaned
    if ok > ck:
        healed += "]" * (ok - ck)
    if ob > cb:
        healed += "}" * (ob - cb)

    try:
        parsed = json.loads(healed, strict=False)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except Exception:
        pass

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
    }

    for m in re.finditer(r"\b(?P<name>[a-zA-Z_]\w*)\s*\(", text):
        fname = m.group("name")
        if fname not in tool_names:
            continue
        start_idx = m.start()

        paren_count = 0
        in_quote = None
        end_idx = None

        for i in range(m.end() - 1, len(text)):
            ch = text[i]
            if in_quote:
                if ch == in_quote and (i == 0 or text[i - 1] != "\\"):
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

                    if not args_dict and node.args:
                        arg_keys = (
                            ["path", "old_str", "new_str"]
                            if fn == "edit_file"
                            else (
                                ["command"]
                                if fn == "run_command"
                                else (
                                    ["pattern", "path"]
                                    if fn in ("search_code", "find_symbol")
                                    else ["path", "content"]
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
        except Exception:
            pass

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
            raw_args = m.group("args").replace('\\"', '"').replace("\\\\", "\\")
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

    # Format 4: Standard XML/JSON Format (<tool_call>{...}</tool_call>)
    if not calls:
        for i, m in enumerate(RE_XML_JSON.finditer(text)):
            calls.append(
                {
                    "id": f"call_xml_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": m.group("name"),
                        "arguments": json.dumps(heal_json_args(m.group("args"))),
                    },
                }
            )

    # Format 5: Balanced Naked JSON Objects or Lists ({"name": ..., "arguments": ...})
    if not calls:
        balanced_objs = _extract_balanced_json(text)
        for i, obj in enumerate(balanced_objs):
            if "name" in obj:
                fname = obj.get("name", "")
                raw_args = obj.get("arguments", {})
                healed = heal_json_args(raw_args)
                if fname:
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

    return calls
