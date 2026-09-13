# Py-Agent Skills

Modular personas, on-demand behaviors, system directives, and prompt harnesses.

---

### Quick Reference

| Action | Command / Location | Behavior |
|---|---|---|
| **Browse / Search Skills** | `/s` or `/skill` | Opens live fuzzy TUI selector across `on-demand/`. |
| **Load Skill** | `/s <name>` *(e.g. `/s hindsight`)* | Stacks skill into active system prompt (max 3). |
| **One-Shot Run** | `/s <name> <prompt>` | Loads skill and executes query in single turn. |
| **Unload Skills** | `/s off` (or `/s clear`) | Reverts to base workspace profile. |
| **Select Workspace Profile** | `ai init <dir>` | Selects base profile from `profiles/` with toggle auto-sync. |
| **Dynamic Context Tool** | Registered in `ai-context.md` | Ephemeral single-turn context injection via `cat`. |

