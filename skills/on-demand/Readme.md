# On-Demand Skills (`/s` & `/skill`)

Drop `.md` skill files (or subfolders) anywhere inside `skills/on-demand/` to make them instantly searchable in chat.

---

### 1. Supported Skill Formats

#### Format A: Universal YAML Frontmatter (Standard)
```markdown
---
name: omarchy-desktop
description: Configure Hyprland, themes, bar widgets, shortcuts, and desktop settings.
---
# Prompt instructions here...
```

#### Format B: Legacy Intent Header
```markdown
# [SKILL] reviewer ---> review, check, audit, bug, code review
Your prompt instructions here...
```

---

### 2. Usage in Chat:
* **Interactive Search & Menu:** `/s` (lists all available skills)
* **Direct Filter Search:** `/s <query>` (e.g. `/s crash`, `/s review`, `/s hypr`)
* **Unload Skills:** `/s off` (or `/s clear` / `/s reset`) to revert to base profile.
* **Controls:** `↑` / `↓` navigate $\cdot$ `Type` to live filter $\cdot$ `↵` load $\cdot$ `Esc` cancel.

---

### 3. Advanced Features:
* **Multi-Skill Stacking:** Stack up to 3 on-demand skills simultaneously in active memory.
* **Category Auto-Swap:** Loading a new skill of the same category (e.g. `personality/`) automatically replaces the older one.
* **Subfolder Support:** Skills in nested folders (e.g. `omarchy/`, `personality/`, `code/`) are automatically indexed and searchable.

