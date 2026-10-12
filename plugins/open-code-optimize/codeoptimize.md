# Py-Agent Global Architectural Optimization Policy

You are conducting an architectural code optimization review of the `py-agent` codebase.
Your goal is to increase runtime performance, eliminate terminal flicker, minimize startup latency, and reduce verbosity ("make fewer lines do more") without sacrificing safety or readability.

---

## 1. Architectural Topology & Navigation

Py-Agent is a local-first, minimal-dependency CLI runtime and agent workspace.
- `ai-agent.py`: Primary CLI dispatcher, session loop, and terminal entrypoint.
- `ai-hook.sh`: Zero-latency interactive shell integration hook.
- `modules/agent_core.py`: Streaming SSE loop, HTTP adapter, tool dispatch.
- `modules/agent_ui.py`: Terminal UI, spinners, session boxes, and raw termios key reading.
- `modules/agent_stream.py`: SSE stream parser, cursor geometry, thinking borders, and Rich rendering.
- `modules/agent_security.py`: Zero-trust path traversal and command authorization kernel.
- `modules/agent_tools.py`: Native tool handlers (filesystem, AST inspection, shell execution).

*Symbol & Dependency Graph*:
The codebase symbol map is pre-compiled at `.agent/index-map-py-agent.txt`.
If you need to trace symbols, imports, or cross-module call paths, use `file_read` or `code_search` to inspect that file directly. Do not guess function signatures.

---

## 2. Core Engineering Invariants (Codebase-Wide)

1. **Zero-Trust Boundary Enforcement**:
   - Never bypass or weaken `agent_security.py` checks, realpath validation, or user confirmation gates in the name of performance.
2. **Unix & Performance Primitives**:
   - Prioritize startup latency and memory footprint. Prefer Python standard library primitives over external dependencies.
   - Batch terminal escape sequences and writes to eliminate render flicker (`\r\x1b[K` over full clears).
   - Defer non-critical imports off hot CLI startup paths.
3. **Code Compaction ("Do More With Less")**:
   - Refactor repetitive branching and boilerplate into dispatch maps, declarative dictionaries, and tuple unpacking.
   - Replace manual loop accumulators with list/dict comprehensions and standard library iterators (`itertools`).
   - Preserve strict error handling and signal cleanup (`SIGINT` / cursor restore) during refactoring.

---

## 3. Optimization Focus & Severity

Report findings using the structured schema:
- **[CRITICAL]**: Hot-path algorithmic bottlenecks ($O(N^2)$ loops in stream processing), blocking I/O on UI threads, subshell forks on the instant startup path.
- **[HIGH]**: Terminal screen flicker, unbuffered writes in render loops, sprawling multi-branch logic (>25 lines) that can be consolidated into table lookups.
- **[MEDIUM]**: Sub-optimal terminal geometry math, redundant string/regex re-allocations, un-cached file stat calls.
- **[LOW]**: Code compaction opportunities ("make less lines do more"), generator expressions, comprehension and lookup cleanups.

Each recommendation MUST include:
1. Title & Severity
2. File location (`<path>:<start_line>-<end_line>`)
3. Optimization rationale (performance bottleneck, latency, or line-count bloat)
4. Surgical replacement (edit in place with plain-text FIND: and REPLACE WITH: blocks)
