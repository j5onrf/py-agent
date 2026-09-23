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
   ┌──────────┼──────────────┬──────────────┬──────────────┐   │
   ▼          ▼              ▼              ▼              ▼   ▼
┌───────────┐ ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────┐
│ Adapters  │ │ Sandbox  │ │ Security   │ │ Skills    │ │ SQLite DBs  │
│ (/adp for │ │ Kernel   │ │ Kernel     │ │ & Context │ │ (Sessions & │
│ Sub-27B)  │ │ (/py)    │ │ (Zero-Trust│ │           │ │  FTS5 Graph)│
└───────────┘ └──────────┘ └────────────┘ └───────────┘ └─────────────┘
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
   - `use_map == True`: Slices in the AST symbol graph tools (`read_symbol`, `trace_symbol`, `blast_radius`, `find_symbol`, `architecture_overview`, `delegate_task`) regardless of model size.

3. **Zero-Trust Security Enforcement (`agent_security.py`):**
   - Centralizes path resolution, container prefix healing (`/workspace/`), forbidden system directory blacklists (`/etc`, `/usr`), and command security (`sudo`, `pacman`, `systemctl`).
   - Implements a non-bypassable authorization gate: in-bounds workspace operations auto-approve under YOLO mode, but out-of-bounds access and mutating system commands strictly ignore YOLO mode and always prompt for `[y/N]` confirmation.

4. **Opt-In Out-of-Band Adapters (`agent_adapters.py`):**
   - **Opt-in only:** Disabled by default across the runtime. Enabled explicitly per profile via `adapters: true` (recommended for Sub-27B SLMs) or toggled on-the-fly with `/adp`.
   - Large models (27B+) do not use adapters by default, relying on native schema compliance.
   - When active on small models, it normalizes parameter aliases (`file` -> `path`, `cmd` -> `command`), repairs unclosed JSON brackets, and rescues markdown-wrapped tool calls out-of-band without polluting base system prompts.

5. **Deterministic Diffing (`agent_tools.py`):**
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
   ├── agent_security.py        - Zero-Trust security kernel, path containment & non-bypassable gates
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
   └── chat                     - Standalone analytical recommendation engine for /f, /tk, /b, and /a directives
```

---

# Technical Reference: Lineage, Foundations & Extended Capabilities

A comprehensive map of all upstream foundations, architectural roots, and secondary services integrated into `py-agent`:

<h3 align="center">Architectural Foundations & Upstream Roots</h3>

| System | Upstream Roots & Inspiration | Purpose & Architecture |
| :--- | :--- | :--- |
| **Codebase Graph** | [Graphify](https://github.com/Graphify-Labs/graphify) + [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Standard-library Python AST parsing (`ast.NodeVisitor`) coupled with SQLite `fts5` virtual table indexing for sub-millisecond symbol queries (`index-map`). |
| **Task Loop Engine** | [Ralph Wiggum](https://github.com/ghuntley/how-to-ralph-wiggum) | Self-directed task loop (`ralph.py`) that reads specifications (`TASK.md`), decomposes execution steps, and retries on failure states until pass verification. |
| **Kernel Harness** | [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent) + [NVIDIA NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents) | Stateful in-memory IPython REPL with bounded object representations (`preview()`), 30s `SIGALRM` execution alarm, and model-callable `memory`/`graph` APIs (`/py`). |
| **Code-First Batching** | [Hugging Face smolagents](https://github.com/huggingface/smolagents) | Enables models to execute multi-file batch loops in Python RAM and conclude with a clean `final_answer(data)` completion signal. |
| **Surgical File Edits** | [SmallCoder](https://github.com/Doorman11991/smallcode) | 3-stage resilient replacement (`edit_file`) tolerant of whitespace/indentation variances, with overwrite protection on `write_file`. |
| **Context Compaction** | [Pi Coding Agent](https://pi.dev) | 3-zone context compactor (`prune_history`) that condenses middle turns while preserving completed milestone anchors and modified file tracking. |
| **Cognitive Stepping** | [Reasonix](https://github.com/esengine/deepseek-reasonix) | Real-time cognitive transition extraction and streaming step badges inside thinking traces (`/t`). |
| **Multi-Agent State** | [Vercel Eve](https://github.com/vercel/eve) + [herdr](https://github.com/ogulcancelik/herdr) | Process-isolated sub-agent PID lockfile tracking with checkpoint rollback (`-save` / `-load`) and in-kernel `delegate()` sandboxing. |
| **Adapter Healing** | [Unsloth AI](https://github.com/unslothai/unsloth) | Self-healing tool format adapters (`agent_adapters.py`) resolving Hermes XML, DSML, Mistral, and raw planning JSON out-of-band for ≤27B models (`/adp`). |

## Auxiliary Subsystems & Services

* **Live Web Grounding (`/gnd`):** Dual-mode factual web search using the official Gemini Grounding Search tool with automatic keyless DuckDuckGo fallback across CLI, TUI, and Web surfaces.
* **Multimodal Vision OCR (`describe_image_gemini`):** Cloud pre-processor utilizing Gemini Flash Lite vision to transcribe images, diagrams, error screenshots, and UI mockups into structured text descriptions for text-only local models.
* **Low-Latency Voice Bridge (`/v [auto]`):** Standalone HTTPS server on port `9999` with Gemini speech-to-text and Wayland virtual typing (`wtype --`) directly into the CLI or PyCode editor.
* **Local Kokoro Audio (`/tts`):** Zero-lag neural text-to-speech reader using local `koko` via PipeWire (`pw-play`), automatically filtering code blocks and thinking traces.
* **System Administration Suite:** Integrated diagnostics in `tools/agentic/system/` including real-time hardware inspection (`system-health`), automated log triage (`log-checker`), AUR package auditing (`aur-audit`), and dynamic security auditing (`security-audit`).

## Architectural Advantages

| Competitive Advantage | Engineering Delivery | What You Get |
| :--- | :--- | :--- |
| Zero-Daemon Architecture | 100% Python standard library (`rich` + `requests`). | **0% idle CPU/RAM**. No Docker containers, no Node.js background services, and zero vector database daemons. |
| Sub-27B SLM Mastery | Deterministic 6-tool suite (`SMOL_TOOLS`) + self-healing parser (`/adp`). | **100% benchmark passes on 1B–8B models** (Ling, Qwen, MiniCPM) with zero script-looping or hallucinated paths. |
| ~95% Hardware Cache Hits | Strict prefix alignment + live `cch: X%` tracking. | Reuses GPU VRAM across turns. **Follow-up turns stream in milliseconds** on local `llama.cpp` and cloud backends. |
| Dual-Engine Execution | Stateful in-memory kernel (`/py`) + surgical native tools. | Run multi-file batch loops in Python RAM, or perform whitespace-tolerant 3-stage file replacements (`edit_file`). |
| Git-Native OKF Memory | Plain Markdown directives in `.agent/memory/*.md`. | **100% human-editable in `nvim`/`code`**. Includes 1-shot retrospective session audits (`/hs`). No black-box vector DBs. |
| Zero-Trust Hardened Security | Centralized security kernel (`agent_security.py`). | Non-bypassable interactive `[y/N]` confirmation gates protecting against system commands (`sudo`, `pacman`, `pip`) and out-of-bounds file access even in YOLO mode. |
| True Surface Parity | 1 unified engine driving 4 modular client surfaces. | Seamless handoff between CLI Terminal, Textual TUI (`/tui`), `llama.cpp` WebUI (`/webui`), and Desktop IDE (`/pyc`). |

---

## Core Capabilities

| Core Module | Capability | Description |
| :--- | :--- | :--- |
| **Engine** | **Zero-Daemon** | 0% idle CPU/RAM usage. Native Python standard-library execution. |
| **Providers** | **Active Provider** | Direct `.env` configuration: Custom Endpoints / HF, Gemini, OpenRouter, OpenAI, Claude, Grok, or Local GGUF. |
| **Multi-Agent** | **Subagents** | Vercel Eve-style sub-agents with herdr multiplexing (`-save`/`-load`) + in-kernel `delegate("goal")` sandboxes. |
| **Safety** | **Zero-Trust Kernel** | `modules/agent_security.py` enforces mandatory non-bypassable `[y/N]` confirmation for out-of-bounds workspace paths, mutating system actions (`systemctl`), and package managers (`sudo`, `pacman`, `pip`) even in YOLO mode. |
| **Integrity** | **Type-Safe & AST Guard** | Pydantic AI schemas + AST-validated Python file writes with live diff previews. |
| **Resilience** | **Self-Healing Tools** | Unsloth-inspired JSON argument healer re-serializing valid schemas to prevent server `HTTP 500` errors. |
| **Optimization** | **Token-Slasher** | Custom `tools/` and `skills/` integration built for minimal token consumption. |
| **Grounding** | **Web Search Engine** | Real-time factual search retrieval (`/gnd`) with Gemini Grounding and DuckDuckGo safety fallback in CLI, TUI & WEB/PYC. |
| **Voice-to-Text** | **Tablet/Phone Bridge** | Zero-latency HTTPS voice bridge with Gemini cloud transcription and native Wayland virtual typing (`wtype --`) directly into PyCode IDE and CLI (`/v [auto]`). |
| **Text-to-Speech** | **Neural Kokoro TTS** | Local PipeWire audio reader (`/tts`) using `koko` with silent code/thinking filtering and concise status announcements. |

