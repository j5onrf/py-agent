#!/usr/bin/env python3
"""Tool Format Adapters & Self-Healing Parser for Sub-27B Models [Universal Small-Model Suite]"""

import ast
import json
import re
import time
from typing import Any

# ── 1. Compiled Regex Interceptors ────────────────────────────────────────────

# Hermes 3.x XML (<function=name><parameter=k>v</parameter></function>)
RE_HERMES_XML = re.compile(r"<tool_call>\s*<function=(?P<name>[^>]+)>\s*(?P<params>[\s\S]*?)\s*</function>\s*</tool_call>", re.DOTALL)
RE_HERMES_PARAM = re.compile(r"<parameter=(?P<key>[^>]+)>\s*(?P<val>[\s\S]*?)\s*</parameter>", re.DOTALL)

# DeepSeek & Liquid DSML (<｜DSML｜invoke name="..." arguments="..." />)
RE_DSML = re.compile(r"<｜DSML｜invoke\s+name=[\"'](?P<name>[^\"']+)[\"']\s+arguments=[\"'](?P<args>[\s\S]*?)[\"']\s*/>", re.DOTALL)

# Mistral / Codestral ([TOOL_CALLS] [...])
RE_MISTRAL = re.compile(r"\[TOOL_CALLS\]\s*(?P<calls>\[[\s\S]*?\])", re.DOTALL)

# Standard XML / JSON Wrapper (<tool_call>{"name": ..., "arguments": ...}</tool_call>)
RE_XML_JSON = re.compile(r"<tool_call>\s*\{?[\s\S]*?\"name\":\s*\"(?P<name>[^\"]+)\"[\s\S]*?\"arguments\":\s*(?P<args>\{[\s\S]*?\})\s*\}?\s*</tool_call>", re.DOTALL)

# Raw Python Tool Invocations: read_file(path="..."), list_dir("."), edit_file(path=...)
RE_RAW_CALL = re.compile(r'\b(?P<name>read_file|edit_file|write_file|list_dir|run_command|read_symbol|trace_symbol|blast_radius|find_symbol)\((?P<args>[^)]*)\)')

# Markdown wrappers and stray tokens
RE_MD_JSON_WRAPPER = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.DOTALL)
RE_XML_TOOL_TAGS = re.compile(r"<\|?[a-zA-Z_]+_call_?(?:start|end)?\|?>|</?tool_call>|</?function[^>]*>|</?parameter[^>]*>|<｜/?DSML｜(?:function_calls)?>", re.DOTALL)
RE_JSON_OBJECT = re.compile(r"\{[\s\S]*\}")


# ── 2. Parameter Aliases & Normalization ───────────────────────────────────────

def normalize_params(args: dict[str, Any]) -> dict[str, Any]:
    """Auto-heals common parameter alias discrepancies emitted by small models."""
    if not isinstance(args, dict):
        return {}

    # Normalize 'path' aliases
    if "path" not in args:
        for alt in ("file", "filename", "filepath", "target", "file_path", "target_file"):
            if alt in args:
                args["path"] = args[alt]
                break

    # Normalize 'command' aliases
    if "command" not in args:
        for alt in ("cmd", "exec", "shell_command", "script", "bash"):
            if alt in args:
                args["command"] = args[alt]
                break

    # Normalize 'content' aliases
    if "content" not in args:
        for alt in ("text", "code", "body", "data", "source"):
            if alt in args:
                args["content"] = args[alt]
                break

    # Normalize 'symbol' aliases
    if "symbol" not in args:
        for alt in ("func", "function", "method", "class_name", "target_symbol"):
            if alt in args:
                args["symbol"] = args[alt]
                break

    return args


# ── 3. High-Performance JSON Argument Healer ──────────────────────────────────

def heal_json_args(raw: str) -> dict[str, Any]:
    """Self-healing JSON tool argument parser for small quantized models (2B–8B)."""
    if not raw or not raw.strip():
        return {}
    cleaned = raw.strip()

    if m := RE_MD_JSON_WRAPPER.search(cleaned):
        cleaned = m.group(1).strip()
    cleaned = RE_XML_TOOL_TAGS.sub("", cleaned).strip()

    # Fast-path standard JSON
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except json.JSONDecodeError:
        pass

    # Heuristic repairs for unescaped newlines in Python code payloads
    healed = cleaned.replace("\r\n", "\\n").replace("\n", "\\n").replace("\t", "\\t")
    healed = re.sub(r"(?<!\\)'", '"', healed)
    healed = re.sub(r"(\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*:", r'"\1":', healed)
    healed = re.sub(r",\s*([\]}])", r"\1", healed)

    # Balance unclosed brackets
    ob, cb = healed.count("{"), healed.count("}")
    ok, ck = healed.count("["), healed.count("]")
    if ok > ck:
        healed += "]" * (ok - ck)
    if ob > cb:
        healed += "}" * (ob - cb)

    try:
        parsed = json.loads(healed)
        if isinstance(parsed, dict):
            return normalize_params(parsed)
    except json.JSONDecodeError:
        pass

    # Regex key-value extraction fallback
    extracted = {k: v.strip() for k, v in re.findall(r'"?([a-zA-Z_][a-zA-Z0-9_]*)"?\s*:\s*["\']?([^,"\']+)["\']?', cleaned)}
    return normalize_params(extracted)


# ── 4. Universal Fallback Tool Extraction Suite ───────────────────────────────

def extract_fallback_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extracts and normalizes tool calls across all sub-27B model variations."""
    if not text or not text.strip():
        return []

    calls = []

    # Format 1: Hermes 3.x XML
    for i, m in enumerate(RE_HERMES_XML.finditer(text)):
        fname = m.group("name").strip()
        raw_params = m.group("params")
        params = {pm.group("key").strip(): pm.group("val").strip() for pm in RE_HERMES_PARAM.finditer(raw_params)}
        calls.append({
            "id": f"call_hermes_{i}_{int(time.time())}",
            "type": "function",
            "function": {"name": fname, "arguments": json.dumps(normalize_params(params))}
        })

    # Format 2: DeepSeek & Liquid DSML
    if not calls:
        for i, m in enumerate(RE_DSML.finditer(text)):
            raw_args = m.group("args").replace('\\"', '"').replace("\\\\", "\\")
            calls.append({
                "id": f"call_dsml_{i}_{int(time.time())}",
                "type": "function",
                "function": {"name": m.group("name"), "arguments": json.dumps(heal_json_args(raw_args))}
            })

    # Format 3: Mistral / Codestral
    if not calls and (mm := RE_MISTRAL.search(text)):
        try:
            for i, c in enumerate(json.loads(mm.group("calls"))):
                calls.append({
                    "id": f"call_mistral_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {"name": c.get("name"), "arguments": json.dumps(normalize_params(c.get("arguments", {})))}
                })
        except Exception:
            pass

    # Format 4: Standard XML/JSON (<tool_call>{"name": ..., "arguments": ...}</tool_call>)
    if not calls:
        for i, m in enumerate(RE_XML_JSON.finditer(text)):
            calls.append({
                "id": f"call_xml_{i}_{int(time.time())}",
                "type": "function",
                "function": {"name": m.group("name"), "arguments": json.dumps(heal_json_args(m.group("args")))}
            })

    # Format 5: Raw Python Tool Syntax (e.g. read_file(path="..."), list_dir("."))
    if not calls:
        for i, m in enumerate(RE_RAW_CALL.finditer(text)):
            fname = m.group("name")
            raw_arg_str = m.group("args").strip()
            extracted = {}

            # Extract keyword arguments (key='val' or key="val")
            for k, v in re.findall(r'(\w+)\s*=\s*[\'"]([^\'"]*)[\'"]', raw_arg_str):
                extracted[k] = v

            # Positional arguments fallback (e.g. read_file("calculator.py"))
            if not extracted and raw_arg_str:
                clean_pos = raw_arg_str.strip('\'"')
                param_key = "command" if fname == "run_command" else "path"
                extracted[param_key] = clean_pos

            if extracted or fname in ("list_dir", "architecture_overview"):
                calls.append({
                    "id": f"call_raw_{i}_{int(time.time())}",
                    "type": "function",
                    "function": {"name": fname, "arguments": json.dumps(normalize_params(extracted))}
                })

    # Format 6: Liquid Benchmark Planning Objects ({"commands": [{"command": "...", "path": "..."}]})
    if not calls and '"commands":' in text:
        try:
            if m := RE_JSON_OBJECT.search(text):
                data = json.loads(m.group(0))
                if "commands" in data and isinstance(data["commands"], list):
                    for i, cmd_item in enumerate(data["commands"]):
                        if isinstance(cmd_item, dict):
                            p = cmd_item.get("path")
                            c = cmd_item.get("command", "").strip()
                            if p and (not c or any(c.startswith(pref) for pref in ("cat ", "head ", "tail ", "less "))):
                                calls.append({
                                    "id": f"call_bench_{i}_{int(time.time())}",
                                    "type": "function",
                                    "function": {"name": "read_file", "arguments": json.dumps({"path": p})}
                                })
                            elif c:
                                calls.append({
                                    "id": f"call_bench_{i}_{int(time.time())}",
                                    "type": "function",
                                    "function": {"name": "run_command", "arguments": json.dumps({"command": c})}
                                })
        except Exception:
            pass

    return calls
