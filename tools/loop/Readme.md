# Autonomous Task Loop Engine (`loop.py`)

A deterministic, multi-turn feedback loop engine for autonomous goal execution. Designed for deep engineering workflows: it inspects codebases, applies targeted surgical edits, executes automated test suites, decomposes failures, and iterates autonomously until tests pass.

---

## 1. How to Use

### A. In-Session Slash Command (Primary Workflow)
Within an active `ai-agent` terminal session, trigger the engine directly via `/task`:

```bash
/task <goal description>
```

**Examples:**
```text
❯ /task Fix the failing assertion in tests/test_auth.py and verify exit 0
❯ /task Refactor database connection pooling to use context managers
❯ /task Resolve all remaining TODOs in src/worker.py
```

### B. Specification-Driven Workflow (`TASK.md`)
For complex or multi-step feature implementations, define the plan in `TASK.md` at your workspace root:

```markdown
# TASK.md

- [ ] Add rate-limiting middleware to `/v1/chat/completions`
- [ ] Return HTTP 429 when client exceeds 30 RPM
- [ ] Write integration test in `tests/test_ratelimit.py` and ensure `pytest` passes
```

*The engine automatically detects `TASK.md`, formulates the initial prompt, and drives execution until all tasks are satisfied.*

## 3. CLI Arguments Reference

| Option | Default | Purpose |
| :--- | :--- | :--- |
| `goal` | `""` | Direct instruction string (if empty, loads `TASK.md`). |
| `-n, --turns <int>` | `15` | Maximum loop cycles allowed before reaching completion. |
| `-f, --file <path>` | `TASK.md` | Path to custom markdown task specification file. |
| `--no-log` | `False` | Disables writing turn history to `<workspace>/.agent/task_log.md`. |

