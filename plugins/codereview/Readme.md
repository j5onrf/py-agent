# Open Code Review
# https://github.com/alibaba/open-code-review

## 1. Install

```bash
npm install -g @alibaba-group/open-code-review
```

---

## 2. Usage

Type `opencr` or `codereview` in the terminal:
* Enter a direct file path (e.g. `~/.config/py-agent/modules/agent_core.py`) or directory.
* Automatically uses active credentials and model from `~/.config/py-agent/.env`.
* Audits the file in place with full repository context (strictly read-only; never modifies files).

---

## 3. Direct CLI

Run inside your repository:
* `ocr scan --path <file>` — Audit a single file directly.
* `ocr scan` — Audit full directory.
* `ocr review` — Audit uncommitted Git changes.

