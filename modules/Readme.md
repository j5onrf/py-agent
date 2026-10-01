# Private-First

Built to be lightweight, auditable by a single developer, and private by design.

* **Zero-Trust Containment:** Out-of-bounds workspace access, mutating system actions (`systemctl`), and package managers (`sudo`, `pacman`, `pip`) always require interactive `[Y/n]` confirmation.
* **Isolated Secrets:** Credentials exist solely in `~/.config/py-agent/.env` with `0o600` permissions and are never logged, exported, or leaked into prompts or query strings.
* **Standalone Architecture:** 100% standard library Python orchestration with zero background embedding servers and zero tracking services.

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
│ modules/agent_commands.py │                    │ modules/agent_tui.py      │
│ (Command Registry & Router│                    │ (Textual TUI, uvloop)     │
└─────────────┬─────────────┘                    └─────────────┬─────────────┘
              │                                                │
              ▼                                                ▼
┌───────────────────────────┐                    ┌───────────────────────────┐
│ modules/agent_core.py     │◄───────────────────┤ modules/agent_state.py    │
│ (Agentic Execution Loop)  │                    │ (Locking, Atomic Storage) │
└─────────────┬─────────────┘                    └───────────────────────────┘
              │
   ┌──────────┼──────────────┬──────────────┬──────────────┬──────────────┐
   ▼          ▼              ▼              ▼              ▼              ▼
┌───────────┐ ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────┐
│ Stream &  │ │ Adapters   │ │ Sandbox  │ │ Security   │ │ Skills    │ │ SQLite DBs  │
│ Terminal  │ │ (/adp for  │ │ Kernel   │ │ Kernel     │ │ & Context │ │ (Sessions & │
│ (Render)  │ │ Sub-27B)   │ │ (/py)    │ │ (Zero-Trust│ │           │ │  FTS5 Graph)│
└───────────┘ └────────────┘ └──────────┘ └────────────┘ └───────────┘ └─────────────┘
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
      Flagship: Ling-3.0-tiny                        Flagship: Qwen3.8-35B-D
     ─────────────────────────                      ─────────────────────────────
     • Profile: lingtiny.md                         • Profile: Qwen38.md
     • Execution: Native 6-Tools                    • Execution: Dual-Mode (/py + Native)
     • /py: OFF (Avoids escaped code)               • /py: ON (In-Memory REPL & Testing)
     • Adapters: Opt-In (/adp Active)               • Adapters: OFF (Not Used by Default)
     • Reasoning: Dynamic /t (500t Default)         • Reasoning: Dynamic /t (500t Default)
     • Strength: Fast shell triage & diffs          • Strength: Deep reasoning & multi-file
```

### Technical Implementation

1. **Modular Command Dispatching (`agent_commands.py`):**
   - Decouples 25+ interactive slash actions (`/m`, `/mem`, `/t`, `/tts`, `/adp`, `/g`, etc.), file context loaders, and secondary surface launchers from the main CLI loop into an isolated registry.
   - Preserves state continuity across sessions via a structured `SessionContext` without polluting the core REPL driver.

2. **Decoupled State & Boundary Locking Engine (`agent_state.py`):**
   - Extracts all process-isolated state persistence, `fcntl.flock` file locking, and atomic tempfile swapping (`.state.json`) into a zero-dependency standard library module (<0.2ms boot).
   - Isolates Textual TUI layout state (`.tui_state.json`) from core engine state, eliminating lock contention and circular imports across all surfaces.

3. **Streaming SSE, ANSI Geometry & Rendering (`agent_stream.py`):**
   - Manages post-stream terminal rewriting, dynamic leading line spacing, ANSI cursor arithmetic (`get_cursor_up_count`), live thinking glimmer formatting, and lazy Rich Markdown initialization.
   - Decouples terminal presentation entirely from LLM orchestration and tool execution.

4. **Universal Workspace Modularity (`agent_skills.py` & `agent_context.py`):**
   - Any model tier can enable or disable `/map` (Codebase Index-Map & AST graph) and `/mem` (Git-native OKF Markdown memory) independently in `ai init` or via CLI toggles.
   - Frontmatter defaults define recommended baselines, but runtime hotkeys (`m`, `d`, `p`, `a`, `Tab`) always take precedence and persist to `<workspace>/.agent/config.json`.
   - `agent_context.py` houses the 3-Zone Context Compactor (`prune_history`) and Jaccard intent engine, pruning middle turns while preserving system prompts and completed milestone anchors.

5. **Decoupled Multimodal Vision Engine (`agent_vision.py`):**
   - Offloads image attachment pre-processing, diagrams, error screenshots, and UI mockups to Gemini Flash Lite vision for text-only local models.
   - Hardened with strict SSRF defense (blocking private, link-local, loopback, and metadata subnets), a 15 MB payload bound, header-based API key authentication (`x-goog-api-key`), and canonical workspace path containment.

6. **Dynamic Schema Slicing & Core Engine (`agent_core.py`):**
   - Houses the autonomous 10-round agentic loop (`agentic_turn`), thread-local HTTP streaming sessions, and atomic tool history backfilling (`_backfill_missing_tool_results`).
   - `ipython_mode == False`: Restricts schema to `tools.SMOL_TOOLS` (6 discrete atomic tools: `read_file`, `edit_file`, `write_file`, `search_code`, `list_dir`, `run_command`).
   - `ipython_mode == True`: Injects `IPYTHON_TOOL` (`exec_python`) alongside native tools.
   - `use_map == True`: Slices in the AST symbol graph tools (`read_symbol`, `trace_symbol`, `blast_radius`, `find_symbol`, `architecture_overview`, `delegate_task`) regardless of model size.

7. **Zero-Trust Security Enforcement (`agent_security.py`):**
   - Centralizes semantic path resolution with `os.path.commonpath`, container prefix healing (`/workspace/`), forbidden system directory blacklists (`/etc`, `/usr`), and shell command inspection.
   - Implements a non-bypassable authorization gate: in-bounds workspace operations auto-approve under YOLO mode, but out-of-bounds access and mutating system commands strictly ignore YOLO mode and always prompt for `[y/N]` confirmation.

8. **Opt-In Out-of-Band Adapters (`agent_adapters.py`):**
   - **Opt-in only:** Disabled by default across the runtime. Enabled explicitly per profile via `adapters: true` (recommended for Sub-27B SLMs) or toggled on the fly with `/adp`.
   - Large models (27B+) do not use adapters by default, relying on native schema compliance.
   - When active on small models, it normalizes parameter aliases (`file` -> `path`, `cmd` -> `command`), repairs unclosed JSON brackets, and rescues markdown-wrapped tool calls out-of-band without polluting base system prompts.

9. **Deterministic Diffing (`agent_tools.py`):**
   - `_resilient_replace` handles diff execution in 3 stages: Exact -> Whitespace-Normalized -> 88% Fuzzy Match.
   - Validates changes with `ast.parse` prior to writing, catching syntax regressions at the runtime boundary.

---

## Module Hierarchy

```console
1. Shell & Entry Tier
   ├── ai-hook.sh               - Sub-millisecond zero-fork shell hook, teleportation, and chained CNF handler
   ├── ai-agent.py              - CLI entrypoint, single-pass config resolution, REPL loop & direct query router
   └── agent_commands.py        - Modular command dispatcher, 25+ slash action handlers & surface router

2. Execution & Streaming Engine
   ├── agent_core.py            - Autonomous agentic turn execution loop, tool validation, and scratchpad management
   ├── agent_stream.py          - Streaming SSE, ANSI cursor geometry, live thinking formatters & lazy Rich markdown
   ├── agent_vision.py          - Multimodal vision pipeline, Gemini Flash Lite OCR, SSRF defense & 15 MB bounds
   └── agent_adapters.py        - Universal Sub-27B tool adapters (/adp), AST extractors & self-healing JSON parser

3. Sandboxing, Tools & Safety
   ├── agent_security.py        - Zero-Trust security kernel, path containment & non-bypassable gates
   ├── agent_tools.py           - 12-tool suite, container self-healing, 3-stage resilient replace, AST syntax guards
   ├── agent_ipython.py         - Prime Agent & NOOA stateful kernel, bounded previews, in-kernel delegate() sub-agents
   └── agent_skills.py          - O(1) skill candidate resolver, dynamic YAML frontmatter parser, on-demand injector

4. Concurrency, UI & IPC
   ├── agent_tui.py             - Textual full-screen reactive workspace with dedicated .tui_state.json persistence
   ├── agent_tui_async.py       - uvloop event loop, private .run/*.sock sub-agent socket hub, live OKF memory watcher
   └── agent_ui.py              - Terminal renderers, InlineSpinner, box themes, interactive profile selector (a: Adp)

5. Memory, State & Knowledge
   ├── agent_state.py           - Zero-dependency atomic state persistence (.state.json), flock locks & CLI calm guards
   ├── agent_memories.py        - Git-native Open Knowledge Format (OKF) Markdown memory manager (.agent/memory/*.md)
   ├── agent_sessions.py        - SQLite session checkpoints (-save / -load), turn logger, projects/.database/ isolation
   ├── agent_context.py         - 3-zone context compactor (prune_history) & Jaccard semantic intent router
   └── agent_usage.py           - Unified spend ledger, dynamic model_pricing.json override, timer & speed tracker

6. Cloud Providers & Auxiliary Services
   ├── agent_cloud.py           - Single-pass top-down .env cascade engine (Custom HF, Gemini, OpenRouter, DeepSeek)
   ├── model-select.py          - Streamlined interactive TUI model selector, context budget manager & .env key synchronizer
   ├── agent_voice.py           - Token-authenticated HTTPS voice bridge (:9999) with Wayland virtual typing (wtype --)
   ├── agent_tts.py             - Zero-lag neural Kokoro text-to-speech module (process-group tracked pw-play execution)
   └── agent_chat.py            - Standalone analytical recommendation engine for /f, /tk, /b, and /a directives
```


