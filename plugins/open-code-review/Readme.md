# Open Code Review
# https://github.com/alibaba/open-code-review

## 1. Install

```bash
npm install -g @alibaba-group/open-code-review
```

---

## 2. Usage

Run `cr`, `opencr`, or `codereview` in terminal:
* **Target:** File path, directory, or leave blank for interactive prompt.
* **Reasoning Budget:**
  * `off` (0) — Disabled thinking; maximum speed.
  * `low` (~1kt) — Fast targeted audit (< 500 lines).
  * `medium` (~2.5kt) — Balanced default for logic audits.
  * `high` (~4kt) — Deep security & concurrency analysis.
  * `max` (~8kt) — Exhaustive benchmark reasoning.
  * `<number>` — Custom token ceiling (e.g. `1500`).
* **Environment:** Automatically reads active provider, model, and keys from `~/.config/py-agent/.env`.
* **Config Overrides (`.env`):**
  * `OCR_TIMEOUT=60` — Timeout ceiling in minutes (default: 60).
  * `OCR_CONCURRENCY=2` — Worker thread count (default: 2).
  * `OCR_BUDGET=medium` — Default reasoning level.

---

## 3. Directives & Rule System

Two configuration files steer the reviewer to prevent false positives and eliminate manual profile swapping:

* **`plugins/open-code-review/codereview.md` (Global Architectural Policy):**
  * Injected into all reviews via `--background-file`.
  * Informs the model of overall system architecture, zero-daemon constraints, report schema (`[CRITICAL]` to `[LOW]`), and points to `.agent/index-map-*.txt` so the reviewer can read symbol definitions across files without hallucinating call graphs.

* **`.opencodereview/rule.json` (Target-Specific File Invariants):**
  * Automatically matched by file path globs whenever a specific target is scanned.
  * Whitelists deliberate low-level patterns per file (e.g. `eval` in `ai-hook.sh`, loose regex in `agent_adapters.py`, monkeypatching in `agent_core.py`, raw termios in `agent_ui.py`) and lists exact bug classes to hunt for that module.

* **Verify active rule for a file:**
  ```bash
  ocr rules check <path/to/file>
  ```

---

## 4. Scope Recommendations

| Target Scope | Recommended Budget | Workers | Best For |
|---|---|---|---|
| **Single File** (<500 lines) | `low` (~1kt) | 2 | Fast targeted audits and quick fixes |
| **Large File** (~1,000+ lines) | `medium` (~2.5kt) | 2 | Core engine files and monoliths |
| **Complex Module** (Security / Kernel) | `high` or `max` | 2 | Zero-trust verification & hypothesis testing |
| **Subsystem / Folder** (3–10 files) | `low` or `medium` | 2 | Cohesive multi-file audits |
| **Full Codebase** (15+ files) | `off` or `low` | 2 | Broad lint and security sweeps |
