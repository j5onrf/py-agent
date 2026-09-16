# Private-First

Built to be lightweight, auditable by a single developer, and private by design.

* **Zero-Trust Containment:** Out-of-bounds workspace access, mutating system actions (`systemctl`), and package managers (`sudo`, `pacman`, `pip`) always require interactive `[Y/n]` confirmation.
* **Isolated Secrets:** Credentials exist solely in `~/.config/py-agent/.env` and are never logged, exported, or leaked in prompts.
* **Standalone Architecture:** 100% standard library Python orchestration with zero background embedding servers, zero tracking services.

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

## Dual-Track Execution Architecture

Workspace capabilities (`/map`, `/mem`, `/yolo`, SQLite checkpoints) are universal across all models. The architecture bifurcates strictly on **tool execution style, reasoning depth, and opt-in adapter healing**:

```console
                        DUAL-TRACK EXECUTION ENGINE
                      ┌───────────────────────────────┐
                      │   Stock Engine Core Router    │
                      │  (Universal: /map, /mem, OKF) │
                      └───────────────┬───────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
      TIER 1: Sub-27B SLM                            TIER 2: 27B+ Autonomous MoE
      Flagship: Ling-3.0-tiny                        Flagship: Nex-N2.5-mini
     ─────────────────────────                      ─────────────────────────────
     • Profile: lingtiny.md                         • Profile: nexn25.md
     • Execution: Native 6-Tools                    • Execution: Dual-Mode (/py + Native)
     • /py: OFF (Avoids escaped code)               • /py: ON (In-Memory REPL & Testing)
     • Adapters: Opt-In (/adp Active)               • Adapters: OFF (Not Used by Default)
     • Reasoning: Bounded 500t Scratchpad           • Reasoning: Adaptive 500t Deliberation
     • Strength: Fast shell triage & diffs          • Strength: Deep reasoning & multi-file
```

### Technical Implementation

1. **Universal Workspace Modularity (`agent_skills.py`):**
   - Any model tier can enable or disable `/map` (Codebase Index-Map & AST graph) and `/mem` (Git-native OKF Markdown memory) independently in `ai init` or via CLI toggles.
   - Frontmatter defaults define recommended baselines, but runtime hotkeys (`m`, `d`, `p`, `a`, `Tab`) always take precedence and persist to `<workspace>/.agent/config.json`.

2. **Dynamic Schema Slicing (`agent_core.py`):**
   - `ipython_mode == False`: Restricts schema to `tools.SMOL_TOOLS` (6 discrete atomic tools: `read_file`, `edit_file`, `write_file`, `search_code`, `list_dir`, `run_command`).
   - `ipython_mode == True`: Injects `IPYTHON_TOOL` (`exec_python`) alongside native tools.
   - `use_map == True`: Slices in the AST symbol graph tools (`read_symbol`, `trace_symbol`, `blast_radius`, `find_symbol`, `architecture_overview`) regardless of model size.

3. **Opt-In Out-of-Band Adapters (`agent_adapters.py`):**
   - **Opt-in only:** Disabled by default across the runtime. Enabled explicitly per profile via `adapters: true` (recommended for Sub-27B SLMs) or toggled on-the-fly with `/adp`.
   - Large models (27B+) do not use adapters by default, relying on native schema compliance.
   - When active on small models, it normalizes parameter aliases (`file` -> `path`, `cmd` -> `command`), repairs unclosed JSON brackets, and rescues markdown-wrapped tool calls out-of-band without polluting base system prompts.

4. **Deterministic Diffing (`agent_tools.py`):**
   - `_resilient_replace` handles diff execution in 3 stages: Exact -> Whitespace-Normalized -> 88% Fuzzy Match.
   - Validates changes with `ast.parse` prior to writing, catching syntax regressions at the runtime boundary.

---

## Module Hierarchy

```console
1. Shell & Entry Tier
   ├── ai-hook.sh               - Zero-lag shell hook, auto-teleportation, and command-not-found intent handler
   └── ai-agent.py              - CLI entrypoint, single-pass config resolution, REPL loop & direct query router

2. Execution & Streaming Engine
   ├── agent_core.py            - SSE parser, token calculation, fallback cascade, unclosed-think sanitization
   └── agent_adapters.py        - Universal Sub-27B tool adapters (/adp), AST extractors & self-healing JSON parser

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
   └── agent_usage.py           - Unified spend ledger, high-resolution generation timer & speed tracker

6. Cloud Providers & Auxiliary Services
   ├── agent_cloud.py           - Single-pass top-down .env cascade engine (Custom HF, Gemini, OpenRouter, DeepSeek)
   ├── model-select.py          - Streamlined interactive TUI model selector, context budget manager & .env key synchronizer
   ├── agent_voice.py           - Low-latency HTTPS voice bridge (:9999) with Wayland virtual typing (wtype --)
   ├── agent_tts.py             - Zero-lag neural Kokoro text-to-speech module (OMP-tuned pw-play + koko execution)
   └── chat                     - Standalone analytical recommendation engine for /f, /t, /b, and /a directives
```
