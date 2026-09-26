# Open Code Review
# https://github.com/alibaba/open-code-review

## 1. Install

```bash
npm install -g @alibaba-group/open-code-review
```

---

## 2. Usage

Type `opencr` or `codereview` in the terminal:
* **Target:** Enter an exact file path (e.g. `modules/agent_core.py`) or a directory.
* **Reasoning Budget:** Select thinking depth (press `Enter` for default):
  * `off` (0) — Disabled thinking; maximum throughput.
  * `low` (~1kt) — Fast audit (15m timeout; recommended for files < 500 lines).
  * `medium` (~2.5kt) — Balanced default for deep logic audits (25m timeout).
  * `high` (~4kt) — Deep security & concurrency analysis (30m timeout).
  * `max` (~8kt) — Exhaustive benchmark reasoning (60m timeout).
  * Custom integer (e.g. `1500`, `2500`).
* **Environment:** Automatically uses active credentials and model from `~/.config/py-agent/.env`.
* **Context Budget:** Set `AI_MAX_TOKENS="65536"` in `.env` to prevent truncation on large 1,000+ line files.
* **Execution:** Strictly read-only in-place audit with dynamic watchdog timeout (15m–60m).

---

## 3. Scope & Benchmarks

You can audit either a single file or a directory. Watchdog timeouts scale automatically to prevent premature kills:

| Target Scope | Recommended Budget | Workers | Timeout | Est. Duration | Best For |
|---|---|---|---|---|---|
| **Single File** (<500 lines) | `low` (~1kt) | 2 | 15 min | ~1–2 min | Fast targeted audits and quick fixes |
| **Large File** (~1,000+ lines) | `medium` (~2.5kt) | 2 | 25 min | ~12–18 min | Monoliths |
| **Complex Module** (Security) | `max` (~8kt) | 2 | 60 min | ~20–45 min | Full hypothesis testing & deep verification |
| **Folder / Cluster** (3–6 files) | `low` (~1kt) | 2 | 15 min | ~3–6 min | Subsystem reviews without rate-limit risk |
| **Full Codebase** (15+ files) | `off` or `low` | 2 | 15 min | ~6–12 min | Broad sweeps across large repositories |

*(Tip: For APIs with strict rate limits like 15 RPM, keep directory batches under 6 files or scan files individually).*
