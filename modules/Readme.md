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
     • Reasoning: Dynamic /t (500t Default)         • Reasoning: Dynamic /t (500t Default)
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

---

<h2 align="center">Key Systems & Integrations</h2>

| Feature System | Foundation & Architectural Roots | Interface Command / Link |
| :--- | :--- | :--- |
| **Memory (OKF)** | Git-native Open Knowledge Format ([OKF](https://github.com/okf-memory/okf-agent-memory)) persistent Markdown rules, architectural decisions & project directives. | `.agent/memory/` |
| **Codebase Graph & Index-Map** | Structural codebase maps ([Graphify](https://github.com/Graphify-Labs/graphify)) + relational queries ([codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)) + standard library SQLite FTS5 symbol graph. | `index-map <dir>` |
| **Autonomous Task Loop** | Self-directed iteration loop ([Ralph Wiggum](https://github.com/ghuntley/how-to-ralph-wiggum)) executing tasks against project specs (`TASK.md`) with failure decomposition. | `/task [goal]` |
| **Prime & NOOA Kernel Harness** | Prime Agent ([Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent)) + NVIDIA NOOA ([NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents)) stateful Python kernel with bounded previews (`preview()`), model-callable `memory`/`graph` APIs, and in-kernel `delegate()` sub-agents. | `/py` |
| **Surgical Edits** | Whitespace-tolerant replacements (`edit_file`) + AST skeleton guards (>250 lines) + overwrite protection (`write_file`) inspired by [SmallCoder](https://github.com/Doorman11991/smallcode). | `edit_file <path>` |
| **3-Zone Context Compactor** | Token preservation compactor inspired by [Pi Coding Agent](https://pi.dev)—condenses older tool outputs while preserving completed task progress anchors. | `/compact` (or `/com`) |
| **Audit & IPC** | Unified Markdown conversation logs (`.agent/history.md`) + JSON-RPC 2.0 socket IPC + YAML skill frontmatter overlays. | `.agent/history.md` |
| **Reasonix Cognitive** | Real-time reasoning trace step extraction ([Reasonix](https://github.com/esengine/deepseek-reasonix)) + cognitive phase formatting inside thinking stream. | `/t [N\|show\|hide]` |
| **System Admin & Diagnostics** | Live health monitoring, AUR/security audits, system optimization, status routing, and git commit hooks. | [`tools/agentic/system/`](tools/agentic/system) |
| **Model Select TUI** | Real-time **[Cloud Connection](modules/Readme.md)** TUI, key toggles, and endpoint selector. | `model select` |
| **Interactive Textual PyTUI** | Full-screen **[Textual](modules/Readme.md)** TUI workspace with JSON-RPC 2.0 socket IPC powered by a C-speed `uvloop` event loop. | `/tui` |
| **PyCode Desktop IDE** | Customized [T3 Code](https://github.com/pingdotgg/t3code) fork connected via Agent Client Protocol (ACP) over stdio JSON-RPC 2.0 with live token & thought streaming. | `/pyc` (or `/pyc web`) |
| **llama.cpp WebAgent Gateway** | Full autonomous agent tool execution (`list_dir`, `write_file`, AST graph) + Gemini multimodal vision for text-only local models. | `/webui` |
| **Adapters** | **Sub-27B Healer** | Self-healing tool format adapters (`agent_adapters.py`) resolving Hermes XML, DSML, Mistral, and raw planning JSON out-of-band for ≤27B models. | `/adp` |

---

<h2 align="center">Core Capabilities</h2>

| Core Module | Capability | Description |
| :--- | :--- | :--- |
| **Engine** | **Zero-Daemon** | 0% idle CPU/RAM usage. Native Python standard-library execution. |
| **Providers** | **Active Provider** | Direct `.env` configuration: Custom Endpoints / HF, Gemini, OpenRouter, OpenAI, Claude, Grok, or Local GGUF. |
| **Multi-Agent** | **Subagents** | [Vercel Eve](https://github.com/vercel/eve)-style sub-agents with [herdr](https://github.com/ogulcancelik/herdr) multiplexing (`-save`/`-load`) + in-kernel `delegate("goal")` sandboxes. |
| **Safety** | **Zero-Trust Fallback** | Mandatory non-bypassable `[Y/n]` confirmation for out-of-bounds workspace paths, mutating system actions (`systemctl start/stop`), and package managers (`sudo`, `pacman -S`, `pip`) across both CLI tools and in-kernel Python execution. |
| **Integrity** | **Type-Safe & AST Guard** | [Pydantic AI](https://github.com/pydantic/pydantic-ai) schemas + AST-validated Python file writes with live diff previews. |
| **Resilience** | **Self-Healing Tools** | Unsloth-inspired JSON argument healer re-serializing valid schemas to prevent server `HTTP 500` errors. |
| **Optimization** | **Token-Slasher** | Custom [`tools/`](tools/) and [`skills/`](skills/) integration built for minimal token consumption. |
| **Grounding** | **Web Search Engine** | Real-time factual search retrieval (`/gnd`) with Gemini Grounding and DuckDuckGo safety fallback in CLI, TUI & WEB/PYC. |
| **Voice-to-Text** | **Tablet/Phone Bridge** | Zero-latency HTTPS voice bridge with Gemini cloud transcription and native Wayland virtual typing (`wtype --`) directly into PyCode IDE and CLI (`/v [auto]`). |
| **Text-to-Speech** | **Neural Kokoro TTS** | Local PipeWire audio reader (`/tts`) using `koko` with silent code/thinking filtering and concise status announcements. |

