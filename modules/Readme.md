# Privacy-First

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

## Dual-Track Execution Engine (SLM vs. Cloud / 27B+)

Py-Agent enforces a strict architectural bifurcation recognizing that Sub-27B Small Language Models (SLMs) and 27B+ Large Language Models (LLMs) operate under fundamentally different cognitive constraints:

```console
                        DUAL-TRACK EXECUTION ENGINE
                      ┌───────────────────────────────┐
                      │    Model & Profile Selector   │
                      │   (ai init / .agent/config)   │
                      └───────────────┬───────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
      TRACK 1: SLM Core                               TRACK 2: Cloud / 27B+ Core
 (Qwen-2B/3B, Ling-3.0-Tiny, MiniCPM)               (Qwen-35B, DeepSeek, Claude, Pi)
  ──────────────────────────────────                 ──────────────────────────────────
  • Schema: Strict 6 Native Tools (~680t)            • Schema: Full 11 Tools + Map (~1,100t–2,500t)
  • /py Mode: OFF (Deterministic Files)              • /py Mode: ON (Stateful In-Memory REPL)
  • Decision Budget: 1 Tool Per Action Type          • Multi-Tool Freedom: index-map AST graph
  • Diffing: Handled by _resilient_replace           • Reasoning: Long-chain thought (1k–4k tokens)
  • Exit Discipline: Token-1 Direct Action           • Architecture: Multi-file recursive sub-agents
  • Healing: agent_adapters.py (/adp active)         • Schemas: Strict OpenAI / Anthropic format
```

### Technical Implementation

1. **Profile Frontmatter Decoupling (`agent_skills.py`):**
   - **Track 1 Profiles (`skills/profiles/custom/`):** Set `ipython: false`, `map: false`, and `adapters: true`. Limits schema prefill to ~680 tokens and locks the model into single-action deterministic tools.
   - **Track 2 Profiles (`skills/profiles/{pi,claude,hermes}/`):** Set `ipython: true`, `map: true`, and `adapters: false`. Grants full AST graph access, unbounded sub-agent delegation (`delegate_task`), and Prime/NOOA kernel execution.

2. **Schema Slicing (`agent_core.py`):**
   On every turn, `agentic_turn()` inspects `ipython_mode` and `use_map`:
   - If `ipython_mode == False`: Emits `tools.SMOL_TOOLS` (exactly 6 discrete tools: `read_file`, `edit_file`, `write_file`, `search_code`, `list_dir`, `run_command`).
   - If `ipython_mode == True`: Slices in `IPYTHON_TOOL` (`exec_python`) alongside native tools.
   - If `use_map == True`: Slices in full `index-map` relational tools (`read_symbol`, `trace_symbol`, `blast_radius`, `find_symbol`, `architecture_overview`).

3. **Out-of-Band Self-Healing (`agent_adapters.py`):**
   - Active only when `adapters: true` is set in the profile (Track 1).
   - Normalizes non-standard outputs (Hermes XML, DSML, markdown code blocks, parameter aliases) without polluting the system prompt or confusing larger models.

4. **Deterministic Python Diffing (`agent_tools.py`):**
   - Rather than expecting a 2B parameter model to emit line-perfect whitespace diffs, `_resilient_replace` executes a 3-stage resolution (Exact $\to$ Whitespace Normalized $\to$ 88% Fuzzy Match).
   - File edits validate against `ast.parse` before committing to disk, catching syntax errors silently at the runtime level.

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
