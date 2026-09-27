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
  * `low` (~1kt) — Fast targeted audit (recommended for files < 500 lines).
  * `medium` (~2.5kt) — Balanced default for deep logic audits.
  * `high` (~4kt) — Deep security & concurrency analysis.
  * `max` (~8kt) — Exhaustive benchmark reasoning.
  * Custom integer (e.g. `1500`, `2500`).
* **Environment:** Automatically uses active credentials and model from `~/.config/py-agent/.env`.
* **Set-and-Forget Safety:** Enforces a robust default 60-minute safety timeout that absorbs rate-limit throttling and deep reasoning sweeps without premature aborts.
  * *Optional Override:* Add `OCR_TIMEOUT=${OCR_TIMEOUT:-60}` to your `.env` to customize the timeout ceiling (e.g. `OCR_TIMEOUT=90`).

---

## 3. Scope Recommendations

| Target Scope | Recommended Budget | Workers | Best For |
|---|---|---|---|
| **Single File** (<500 lines) | `low` (~1kt) | 2 | Fast targeted audits and quick fixes |
| **Large File** (~1,000+ lines) | `medium` (~2.5kt) | 2 | Core engine files and monoliths |
| **Complex Module** (Security / Kernel) | `high` or `max` | 2 | Zero-trust verification & hypothesis testing |
| **Subsystem / Folder** (3–10 files) | `low` or `medium` | 2 | Cohesive multi-file audits |
| **Full Codebase** (15+ files) | `off` or `low` | 2 | Broad lint and security sweeps |

*(Reviews terminate immediately upon completion; the 60-minute ceiling serves purely as a socket safety net so you never have to babysit the clock).*
