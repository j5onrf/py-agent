# Py-Agent Global Architectural Review Policy

You are conducting an architectural security and quality review of the `py-agent` codebase.

---

## 1. Architectural Topology & Navigation

Py-Agent is a local-first, minimal-dependency CLI runtime and agent workspace.
- `ai-agent.py`: Primary CLI dispatcher, session loop, and terminal entrypoint.
- `ai-hook.sh`: Zero-latency interactive shell integration hook.
- `modules/agent_core.py`: Streaming SSE loop, HTTP adapter, tool dispatch.
- `modules/agent_security.py`: Zero-trust path traversal and command authorization kernel.
- `modules/agent_tools.py`: Native tool handlers (filesystem, AST inspection, shell).
- `modules/agent_adapters.py`: Self-healing tool call parsers.

*Symbol & Dependency Graph*:
The codebase symbol map is pre-compiled at `.agent/index-map-py-agent.txt`. 
If you need to trace symbols, imports, or cross-module call paths, use `file_read` or `code_search` to inspect that file directly. Do not guess function signatures.

---

## 2. Core Engineering Invariants (Codebase-Wide)

1. **Zero-Trust Boundary Enforcement**:
   - File edits, writes, and commands must pass through `agent_security.py`.
   - Paths must resolve through canonical realpaths; do not flag workspace-relative path canonicalization as redundant.
2. **Unix & Performance Primitives**:
   - Startup latency and memory footprint are prioritized. Standard library solutions are preferred over third-party pip dependencies.
   - ANSI escape codes and terminal controls in TUI/CLI modules are intentional.
3. **Graceful Signal Handling**:
   - `SIGINT` (Ctrl+C) handling must abort current loops cleanly without dumping unhandled Python stack traces to stderr.

---

## 3. Review Focus & Defect Severity

Report findings using the structured schema:
- **[CRITICAL]**: Security boundary bypasses, command injection, path traversal out of workspace, unhandled process deadlocks.
- **[HIGH]**: Infinite retry loops, unhandled API error cascades, broken state persistence, corrupted token calculations.
- **[MEDIUM]**: Sub-millisecond latency regressions in shell hooks, resource leaks (unclosed sockets/file descriptors).
- **[LOW]**: Typing inconsistencies, unreachable dead code, minor formatting drift.

Each finding MUST include:
1. Title & Severity
2. File location (`<path>:<line>`)
3. Root cause explanation
4. Surgical patch (minimal, drop-in replacement)
