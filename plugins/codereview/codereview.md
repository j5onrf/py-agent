# Specialized Architectural Review Directives: `modules/agent_core.py`

You are an expert systems auditor and senior Python runtime engineer conducting an architectural code review of `modules/agent_core.py` in `py-agent`, a zero-daemon terminal AI runtime (`rich` + `requests`).

---

## 1. Intentional Runtime Invariants (STRICT DO-NOT-FLAG LIST)

Do NOT report any of the following patterns as bugs, code smells, or security vulnerabilities:

1. **Post-Stream ANSI Erase & Re-Render:**
   * Streaming raw SSE tokens to stdout and subsequently moving the cursor up (`\033[{lines}A\r\x1b[0J`) to overwrite the stream with `rich.markdown.Markdown` is the intentional visual design. Do NOT suggest removing cursor jumping or using static un-rendered prints.
2. **Rich Global Monkeypatching:**
   * `Markdown.elements["fence"] = CleanCodeBlock` and `Markdown.elements["code_block"] = CleanCodeBlock` are intentional monkeypatches to force transparent terminal backgrounds and strip ultrawide trailing whitespace padding.
3. **Custom Exception Hook (`sys.excepthook`):**
   * Overriding `sys.excepthook` with `_clean_sigint_handler` is deliberate to prevent Python traceback dumps on `Ctrl+C` and ensure clean terminal exits.
4. **Thread-Local HTTP Session (`_local_session`):**
   * Using `threading.local()` with pooled connection adapters (`pool_connections=20`, `pool_maxsize=20`) is deliberate for safe concurrency without multi-process overhead.
5. **Atomic File Swapping for State:**
   * Writing `.state.json` to a PID-tagged temporary file followed by `os.replace` is the intentional zero-daemon persistence pattern.
6. **Heuristic Pre-Parsing (`prepare_markdown` / `_heal_tool_args`):**
   * Pre-processing text to auto-close triple backticks (` ``` `) or recover malformed JSON tool calls is deliberate to maintain compatibility with small local models (≤27B SLMs).
7. **Hard Turn Cap (`range(10)`):**
   * Limiting autonomous turns to 10 iterations in `agentic_turn` is an intentional circuit breaker against infinite agentic loops.

---

## 2. High-Priority Bugs to Hunt (Real Vulnerabilities)

Audit `modules/agent_core.py` rigorously against these specific vulnerability classes:

### A. Terminal State & Cursor Restoration
* **Hidden Cursor Leaks:**
  Verify that whenever `\033[?25l` (hide cursor) is emitted (via `InlineSpinner` or `RichStreamer`), `\033[?25h` (show cursor) is guaranteed to execute in an unconditional `finally:` block or exception handler.
* **Stream Exception Traps:**
  Check `agentic_turn` and `RichStreamer.stop()` for unhandled network exceptions or early returns where `streamer.stop()` is bypassed, leaving the cursor hidden or in an inconsistent terminal state.

### B. ANSI Arithmetic & Geometry Boundary Errors
* **`get_cursor_up_count()` Calculations:**
  * Inspect line length wrapping against terminal width (`console.width` / `cols`). Check for off-by-one errors when line lengths are exact multiples of terminal width.
  * Check behavior on empty strings, trailing newlines (`\n\n`), wide Unicode characters, and ANSI color escapes embedded in the text.
* **Viewport Clamping Overflow:**
  * Evaluate cursor jump behavior (`\033[{lines}A`) when `num_lines` exceeds the physical terminal height (`shutil.get_terminal_size().lines`). Verify whether terminal buffer scrolling will cause cursor movement to clamp at row 0 and corrupt the scrollback buffer.

### C. Concurrency, File Locks & State Race Conditions
* **`_state_lock` Scope:**
  * Verify that `_state_cache` and `_state_mtime` cannot become desynchronized or cause partial reads if multiple subagents or background threads call `get_state()` and `save_state()` concurrently.
* **Tempfile Collisions:**
  * Verify `tmp = f"{STATE_FILE}.tmp.{os.getpid()}.{threading.get_ident()}"` cleanup on exceptions. Ensure orphaned `.tmp` files are not leaked if `os.replace` raises `OSError`.

### D. SSE Stream Chunking & Network Hygiene
* **Multibyte UTF-8 Boundary Splitting:**
  * In `res.iter_lines()`, determine if multibyte UTF-8 characters split across raw socket chunks can be corrupted by `.decode("utf-8", errors="ignore")`.
* **Socket Exhaustion & Unclosed Responses:**
  * Verify that `res.close()` is guaranteed in the `finally:` block of `agentic_turn()` across all network error paths, including `400 Context Overflow`, `KeyboardInterrupt`, and remote socket drops.
* **Adapter / Fallback Infinite Recursion:**
  * Check `adapters.extract_fallback_tool_calls(ans_text)`. Verify whether malformed tool outputs can cause infinite retry loops that do not increment `consecutive_tool_failures`.

### E. Memory Leaks & Large Payload Containment
* **History Growth Under Pruning:**
  * In `agentic_turn`, evaluate whether `messages = prune_history(messages)` correctly frees token memory when consecutive tool calls generate multi-megabyte tool outputs.
* **Scratchpad File Descriptors:**
  * Verify `scratch_file` writing inside `.agent/scratchpad/` properly handles disk errors, quota exhaustion, and workspace path escaping.

---

## 3. Reporting Requirements

Format each discovered issue using this exact schema:

1. **Title & Severity:** `[CRITICAL | HIGH | MEDIUM | LOW] <Clear Vulnerability Summary>`
2. **Location:** `modules/agent_core.py:<line_number>`
3. **Vulnerability Mechanics:** First-principles explanation of how the bug manifests at runtime.
4. **Failure Trigger / PoC:** Concrete scenario (e.g. terminal size, network cutoff, specific token sequence) that triggers the defect.
5. **Surgical Patch:** Minimal, drop-in Python fix addressing the issue without altering existing architectural invariants.
