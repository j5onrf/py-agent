# Privacy-First

Built to be lightweight, auditable by a single developer, and private by design.

* **Zero-Trust Containment:** Out-of-bounds workspace access, mutating system actions (`systemctl`), and package managers (`sudo`, `pacman`, `pip`) always require interactive `[Y/n]` confirmation.
* **Isolated Secrets:** Credentials exist solely in `~/.config/py-agent/.env` and are never logged, exported, or leaked in prompts.
* **Zero Telemetry & Daemons:** 100% standard library Python orchestration with zero background embedding servers, zero tracking daemons.

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
│ (Streaming, Turn Engine)  │◄───────────────────┤ (Textual TUI, uvloop)     │
└─────────────┬─────────────┘                    └─────────────┬─────────────┘
              │                                                │
   ┌──────────┼──────────────┬──────────────┐                  │
   ▼          ▼              ▼              ▼                  ▼
┌───────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────┐ ┌───────────────────────┐
│ Adapters  │ │ Sandbox  │ │ Skills    │ │ SQLite DBs  │ │ Sub-Agent IPC Hub     │
│ (/adp for │ │ Kernel   │ │ & Context │ │ (Sessions & │ │ (agent_tui_async.py   │
│ Sub-27B)  │ │ (/py)    │ │           │ │  FTS5 Graph)│ │  /tmp/*.sock)         │
└───────────┘ └──────────┘ └───────────┘ └─────────────┘ └───────────────────────┘
```

---

## Module Hierarchy

```console
1. Shell & Entry Tier
   ├── ai-hook.sh               - Zero-lag shell hook, auto-teleportation, and command-not-found intent handler
   └── ai-agent.py              - CLI entrypoint, single-pass config resolution, REPL loop & direct query router

2. Execution & Streaming Engine
   ├── agent_core.py            - SSE parser, token calculation, fallback cascade, unclosed-think sanitization
   ├── agent_adapters.py        - Universal Sub-27B tool adapters (/adp), AST extractors & self-healing JSON parser
   └── speed_test.py            - High-resolution monotonic timer (time.perf_counter) for phase TPS metrics

3. Sandboxing, Tools & Safety
   ├── agent_tools.py           - 12-tool suite, container self-healing, 3-stage resilient replace, AST syntax guards
   ├── agent_ipython.py         - Prime Agent & NOOA stateful kernel, bounded previews, in-kernel delegate() sub-agents
   └── agent_skills.py          - O(1) skill candidate resolver, dynamic YAML frontmatter parser, on-demand injector

4. Concurrency, UI & IPC
   ├── agent_tui.py             - Textual full-screen reactive workspace with live tools and self-healing /adp support
   ├── agent_tui_async.py       - uvloop event loop, /tmp/*.sock sub-agent socket hub, live OKF memory directory watcher
   └── agent_ui.py              - Terminal renderers, InlineSpinner, box themes, interactive profile selector (a: Adp)

5. Memory, Knowledge & Storage
   ├── agent_memories.py        - Git-native Open Knowledge Format (OKF) Markdown memory manager (.agent/memory/*.md)
   ├── agent_sessions.py        - SQLite session checkpoints (-save / -load), turn logger, projects/.database/ isolation
   ├── agent_context.py         - Jaccard semantic intent router for instant terminal shortcuts (ai-context.md)
   └── agent_usage.py           - Zero-overhead token spend ledger with 0ms fast-path bypass for cloud models

6. Cloud Providers & Auxiliary Services
   ├── agent_cloud.py           - Single-pass top-down .env cascade engine (Custom HF, Gemini, OpenRouter, DeepSeek)
   ├── model-select.py          - Streamlined interactive TUI model selector & .env key synchronizer
   ├── agent_voice.py           - Low-latency HTTPS voice bridge (:9999) with Wayland virtual typing (wtype --)
   ├── agent_tts.py             - Zero-lag neural Kokoro text-to-speech module (OMP-tuned pw-play + koko execution)
   └── chat                     - Standalone analytical recommendation engine for /f, /t, /b, and /a directives
```
