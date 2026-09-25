```markdown
# Open Code Review
# https://github.com/alibaba/open-code-review

## 1. Install

```bash
npm install -g @alibaba-group/open-code-review
```

---

## 2. Usage

Type `opencr` in the terminal:
* Enter the path to review (or press `Enter` for the current directory).
* Automatically uses the active credentials and model from `~/.config/py-agent/.env`.

---

## 3. Direct CLI

Run inside any target directory:
* `ocr scan` — Audit full directory.
* `ocr review` — Audit uncommitted Git changes.

*(Tip: Copy files to an isolated directory like `~/codereview` to avoid scanning `.env` or keys).*
```
