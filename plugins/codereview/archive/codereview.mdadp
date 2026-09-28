# Py-Agent Architectural Review Directives: Tool Format Adapters & Parsers

Target module: `modules/agent_adapters.py`
Architecture context: Zero-daemon, out-of-band tool call healing layer for SLMs and quantized LLMs (≤27B, MoE, and speculative drafting).

---

## 1. Intentional Designs (DO NOT Flag as Bugs)

* **Permissive Heuristics & Partial Parsers:**
  Using heuristic bracket closure, multi-line regex field extraction, and `ast.literal_eval` fallbacks is deliberate. Small models emit unclosed brackets, single-quoted JSON, and raw text. Do NOT suggest replacing these with strict `json.loads()` or throwing exceptions on non-standard syntax.
* **Regex-Based Tool Interception:**
  Extracting tool calls via regex (`RE_HERMES_XML`, `RE_DSML`, `RE_LING_XML`, `RE_XML_TOOL_CALL`) is required because local servers (`llama.cpp`, vLLM) frequently fail to parse multi-argument calls into standard OpenAI JSON arrays. Do NOT recommend relying solely on provider `delta.tool_calls`.
* **State-Machine Quote Closure:**
  `_close_unterminated_quote()` intentionally appends trailing unclosed quotes to shell strings. This prevents syntax errors in downstream bash shells when models emit unterminated command strings.
* **Shell-to-Tool Rewrite:**
  Rewriting shell commands (`cat << 'EOF'`, `echo ... > file`, `python3 -c ...`) into structured tool calls (`write_file`, `exec_python`) is intentional to ensure mutations route through the zero-trust security kernel and session tracking.

---

## 2. High-Priority Bugs to Hunt (Real Parser Vulnerabilities)

### A. Catastrophic Regex Backtracking (ReDoS)
* Inspect all multiline regexes using `[\s\S]*?` or `.*` (e.g., `RE_LING_XML`, `RE_HERMES_XML`, `RE_CAT_EOF_*`, `RE_MD_CODE_BLOCK`).
* Verify that overlapping quantifier groups cannot cause exponential backtracking or freeze the agent turn when processing large prompts, diffs, or unclosed tags.

### B. Destructive Parameter Sanitization (Data Loss in Code Edits)
* In `_strip_line_number_gutters` and `normalize_params`:
  * Verify that single-line or multi-line code containing valid numeric prefixes (such as dictionary keys `{1: 'admin'}`, port mappings `8080: 80`, Python match statements, or numeric tuples) is NEVER mistakenly stripped as line numbers.
  * Verify that stripping markdown wrappers (`RE_MD_CODE_BLOCK`) preserves exact internal indentation and does not strip critical trailing newlines from replacement code blocks.

### C. Parameter Alias Collision & Precedence Inversion
* In `normalize_params`:
  * Ensure alias lists for one tool do not accidentally consume or clobber parameters intended for another (e.g., `pattern` vs `old_str`, `search` vs `target_str`, `replace` as string replacement vs `replace` as boolean overwrite).
  * Ensure that popping aliases (`cleaned.pop(alt)`) cannot overwrite an already-normalized standard key (`old_str`, `new_str`, `path`, `command`).
  * Verify boolean/overwrite parsing: confirm that non-boolean values like `"replace": "some text"` are never coerced to `overwrite=True`.

### D. Path Cleansing & Boundary Stripping
* In `normalize_params["path"]`:
  * Verify that grep/search line suffixes (`mod_a.py:1` or `mod_a.py:1:10`) are stripped without corrupting paths containing legitimate digits (e.g., `app_v2.py`, `model3.py`).
  * Ensure paths with directory traversal (`../`) or absolute container roots (`/workspace`, `/home/user`) are healed into relative paths without dropping target subdirectories.

### E. Idempotency of `heal_tool_call` and `normalize_params`
* When a model emits an already-valid, compliant OpenAI tool call (standard JSON, correct parameter names, clean strings), `heal_tool_call` and `normalize_params` must be strictly idempotent:
  `normalize_params(normalize_params(args)) == normalize_params(args)`
* Flag any mutation that alters valid code strings when re-parsed.

### F. Re-serialization and Schema Validity
* In `extract_fallback_tool_calls`:
  * Verify that all generated tool call entries strictly produce valid JSON strings for `function.arguments`:
    `json.dumps(normalize_params(...))`
  * Ensure `calls` never appends dictionaries with identical IDs or un-serializable objects that crash `agent_core.py`.
