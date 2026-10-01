# Specialized Architectural Review Directives: `plugins/zed/gpui-bridge.py`

You are an expert protocol engineer and senior Python runtime auditor conducting an architectural code review of `plugins/zed/gpui-bridge.py` in `py-agent`. This module implements a dedicated JSON-RPC 2.0 stdio bridge conforming to Zed's Agent Client Protocol (ACP).

---

## 1. Intentional Runtime Invariants (STRICT DO-NOT-FLAG LIST)

Do NOT report any of the following patterns as bugs, code smells, or architectural defects:

1. **Two-Way Stdio JSON-RPC Architecture:**
   * Reading line-delimited JSON-RPC from `sys.stdin` and writing responses/notifications to `sys.stdout` (guarded by `_stdout_lock`) is the core ACP protocol contract. Do NOT suggest using sockets, WebSockets, or HTTP servers.
2. **Per-Turn Daemon Worker Threads:**
   * Spawning `threading.Thread(target=_worker, daemon=True).start()` in `handle_session_prompt` is deliberate so the bridge can stream chunks asynchronously without blocking the `sys.stdin` dispatch loop from handling `session/cancel` or user permission responses.
3. **Synchronous ACP Permission Handshake:**
   * In `_request_client_permission()`, emitting an outbound `session/request_permission` RPC request to Zed and waiting on a `threading.Event(timeout=60.0)` is the intentional ACP interactive permission flow. Do NOT flag this synchronous wait as a blocking thread anti-pattern.
4. **`loadSession: False` Capability:**
   * Advertising `"loadSession": False` in `agentCapabilities` and rejecting `session/load` for un-cached sessions with `-32602` is intentional. ACP session resumption from historical SQLite databases is currently disabled.
5. **Single-Component Leading Slash Normalization:**
   * Stripping the leading slash from single-component paths (e.g. `/calc.py` -> `calc.py`) while preserving forbidden system roots (`/etc`, `/usr`, `/var`, etc.) is deliberate to heal hallucinated root paths emitted by small SLMs.
6. **Ephemeral Memory Injection:**
   * Injecting `memories.get_memory_context` only into transient turn request messages (`messages[-1]`) while keeping the clean user prompt in `session["history"]` is intentional to prevent compounding context bloat across multi-turn sessions.
7. **Process-Level Pooled HTTP Session:**
   * Using module-level `_http_session = requests.Session()` with connection pooling adapters across SSE streaming turns is deliberate to minimize connection handshake latency.

---

## 2. High-Priority Bugs to Hunt (Real Vulnerabilities)

Audit `plugins/zed/gpui-bridge.py` rigorously against these specific vulnerability classes:

### A. ACP JSON-RPC 2.0 Protocol Compliance
* **Hanging Pending Requests:**
  Verify that whenever an incoming request with an `id` is received, an error response (`-32601`, `-32602`, `-32603`) is guaranteed to be returned on any exception path or invalid payload so Zed is never left hanging until timeout.
* **Permission Response Matching:**
  Verify that responses to agent-initiated requests (`session/request_permission`) correctly parse Zed's outcome object (`{"outcome": {"outcome": "selected", "optionId": "allow"}}`) and clean up the `_pending_requests` table on all exit paths (success, rejection, or timeout).
* **Notification vs. Request Handling:**
  Ensure notifications (messages without `id`, such as `session/cancel` or `session/update`) never generate an outbound JSON-RPC response payload.

### B. Concurrency, Race Conditions & Deadlocks
* **Session Lock Coverage:**
  Inspect `session["lock"]` and verify that concurrent operations (such as incoming `session/cancel` or `/clear` on the main thread while `_execute_acp_turn` is running on a worker thread) cannot race, desynchronize message history, or leak a permanent `session["busy"] = True` state.
* **Worker Cleanup Invariants:**
  Verify that `session["busy"] = False` is strictly guaranteed in a `finally:` block of `_worker()` even on unhandled network drops, parsing failures, or client disconnections.

### C. Streaming Network Hygiene & Socket Leaks
* **Stream Exception Traps:**
  Verify that `_http_session.post(..., stream=True)` responses are wrapped in `with res:` blocks across all error paths to guarantee socket disposal on `res.iter_lines()` exceptions (e.g. `ChunkedEncodingError`, network drops).
* **HTTP Error Reporting:**
  Ensure HTTP status codes other than 200 (such as `400 Context Overflow`, `401 Unauthorized`, `502 Bad Gateway`) are surfaced as explicit error chunks rather than silently completing the turn with an empty assistant message.

### D. Tool Execution Integrity & Security Gates
* **Conversation History Poisoning (Orphaned Tool Calls):**
  Verify that whenever an assistant message containing `tool_calls` is appended to `messages`, every single tool call in that turn is guaranteed to receive a matching `{"role": "tool", "tool_call_id": ...}` response, even if execution raises an exception or is declined by the user.
* **Security Gate Invariants:**
  Verify that `_confirm_gate` properly differentiates between safe in-bounds file edits (auto-approved when `is_yolo` is active or `AI_CONFIRM_GATES == "0"`) and critical security events (`OUT-OF-BOUNDS`, `PYTHON DANGEROUS OP`, `PYTHON SHELL ESCAPE`), ensuring security events always require explicit user permission.
* **Honest Tool Status Reporting:**
  Ensure tool call notifications (`emit_tool_call`) report status `"failed"` when a tool returns `[denied]`, `[error]`, or raises an unhandled exception.

### E. Content Ingestion & Edge Cases
* **Non-Text Block Parsing:**
  Verify that multi-block inputs from Zed (`resource`, `resource_link`, `image`) cannot cause `AttributeError` or `KeyError` if unexpected or missing fields occur in the payload.
* **Path Traversal in Workspace Resolution:**
  Verify that `workspace` paths extracted from `params.get("cwd")` or environment variables cannot escape local filesystem bounds.

---

## 3. Reporting Requirements

Format each discovered issue using this exact schema:

1. **Title & Severity:** `[CRITICAL | HIGH | MEDIUM | LOW] <Clear Vulnerability Summary>`
2. **Location:** `plugins/zed/gpui-bridge.py:<line_number>`
3. **Vulnerability Mechanics:** First-principles explanation of how the bug manifests at runtime.
4. **Failure Trigger / PoC:** Concrete scenario (e.g. payload sequence, network drop, concurrent RPC call) that triggers the defect.
5. **Surgical Patch:** Minimal, drop-in Python fix addressing the issue without altering existing architectural invariants.
