# Skills & Directives

## 1. Profiles (`skills/profiles/`)

### Setup
1. Type `newp` in terminal to create a project.
2. Launch the project by typing its intent shortcut.
3. Select an existing profile on first run (or create a new `.md` file in `skills/profiles/`).

### What Profiles Are For
* **Identity & Directives:** Defines tone, brevity, standards, and role (Cloud, Local GGUF, or Task Persona).
* **Workspace Defaults:** Sets default flags for `ipython`, `map`, `memory`, `yolo`, and `adapters`.
* **Reasoning Baseline:** Sets initial `reasoning_budget` (adjust anytime in-session via `/t <budget>`).

---

## 2. Skills (`skills/on-demand/`)

Stackable behaviors loaded on top of the active workspace profile.

| Command | Action |
|---|---|
| `/s` | Open interactive skill selector. |
| `/s <name>` | Stack skill into active session (max 3). |
| `/s <name> <prompt>` | Run single-turn query with skill. |
| `/s off` | Unload skills and revert to base profile. |

---

## 3. Global System Instructions (`system_instructions.md`)

Persistent rules injected into turn 0 across **all** workspaces.
* Edit `skills/system_instructions.md`.
* Lines starting with `#` are ignored. Active lines apply globally (e.g. environment constraints, universal preferences).

---

## 4. Hindsight (`hindsight.md`)

Retrospective session auditor and durable lesson compiler.
* **Trigger:** Run `/hs` (or `/hindsight`) before ending a session.
* **Action:** Audits conversation history for root-cause fixes, tool quirks, and architectural rules, persisting them directly to `.agent/memory/` via `save_memory` (Human editable).
