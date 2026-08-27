# Privacy-First

Built to be lightweight, auditable by a single developer, and private by design.

* **Automatic Masking:** API keys, tokens, and network IPs are sanitized before reaching model context (`ai-status`, `mysys.md`).
* **Zero-Trust Gates:** Out-of-bounds file access and shell execution require explicit interactive confirmation.
* **Isolated Secrets:** Credentials exist solely in `~/.config/py-agent/.env` and are never logged or exported.
* **Zero Telemetry:** Pure local orchestration with zero tracking daemons or background data collection.

---

# System Architecture

```console
                        PY AGENT RUNTIME ARCHITECTURE
                      ┌─────────────────────────────────┐
                      │    ai-hook.sh (Shell Hook)      │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │    ai-agent.py (CLI Driver)     │
                      └───────┬─────────────────┬───────┘
                              │                 │
              ┌───────────────┘                 └──────────────┐
              ▼                                                ▼
┌───────────────────────────┐                    ┌───────────────────────────┐
│ modules/agent_core.py     │                    │ modules/agent_tui.py      │
│ (Streaming, State Engine) │◄───────────────────┤ (Textual TUI, uvloop)     │
└─────────────┬─────────────┘                    └─────────────┬─────────────┘
              │                                                │
   ┌──────────┼──────────────┬──────────────┐                  │
   ▼          ▼              ▼              ▼                  ▼
┌───────┐ ┌──────────┐ ┌───────────┐ ┌─────────────┐ ┌───────────────────────┐
│ Cloud │ │ Sandbox  │ │ Skills    │ │ SQLite DBs  │ │ Sub-Agent IPC Hub     │
│ Engine│ │ Kernel   │ │ & Context │ │ (Sessions/  │ │ (agent_tui_async.py   │
│       │ │ (IPython)│ │           │ │  Memories)  │ │  /tmp/*.sock)         │
└───────┘ └──────────┘ └───────────┘ └─────────────┘ └───────────────────────┘
```

---

## Module Hierarchy

```console
1. Shell & Entry Tier
   ├── ai-hook.sh               - Auto-teleportation, directory tracking, command-not-found handler
   └── ai-agent.py              - CLI entrypoint, interactive REPL, direct query routing

2. Execution & Streaming Engine
   ├── agent_core.py            - SSE parser, token calculation, fallback cascade, tool turn loop
   └── speed_test.py            - Real-time token generation velocity & TPS metrics

3. Sandboxing, Tools & Safety
   ├── agent_tools.py           - AST syntax pre-check, zero-trust path boundary gates
   ├── agent_ipython.py         - Stateful NOOA kernel, in-memory object previews, sub-agent delegate()
   └── agent_skills.py          - Skill loader, dynamic frontmatter parser, on-demand persona injector

4. Concurrency, UI & IPC
   ├── agent_tui.py             - Textual full-screen reactive async workspace (Plan vs Build)
   ├── agent_tui_async.py       - uvloop event loop, /tmp/*.sock sub-agent socket hub, file watcher
   └── agent_ui.py              - Terminal renderers, spinners, box themes, interactive selectors

5. Memory, Indexing & Storage
   ├── agent_context.py         - Jaccard semantic intent router (ai-context.md)
   ├── ai-agent-sessions        - SQLite session logger, checkpoints (-save / -load)
   └── ai-agent-memories        - Temporal Personality Memory (TPM) background compiler
```

---

# Model Select TUI

<div align="center">
  <p><i>Click to view high-resolution version</i></p>
  <a href="https://github.com/user-attachments/assets/cf01e342-810c-4a2b-ace5-157aecf04bd7">
    <img alt="Model Select TUI Thumbnail" src="https://github.com/user-attachments/assets/cf01e342-810c-4a2b-ace5-157aecf04bd7" width="250" />
  </a>
</div>

---

# Interactive TUI

<div align="center">
  <p><i>Click to view high-resolution version</i></p>
  <a href="https://github.com/user-attachments/assets/d7bccb82-5b98-46fc-be65-928ee5ab7f32">
    <img alt="Interactive TUI Thumbnail" src="https://github.com/user-attachments/assets/d7bccb82-5b98-46fc-be65-928ee5ab7f32" width="250" />
  </a>
</div>

---

# Voice to Text

- **Toggle:** Type `/v` or `/voice` in session to start/stop server (or `/v auto` for instant dispatch).
- **Connect:** Open `https://[PC-IP]:9999` on tablet or phone.
- **Speak:** Hold button to talk; speech auto-types directly into your active PyCode composer, browser, or terminal prompt via native Wayland virtual typing (`wtype`).

### Setup (`~/.config/py-agent/.env`)

```env
GEM_VOICE="AIzaSyYourGeminiKeyHere"
GEM_MODEL="gemini-3.5-flash-lite"
```
