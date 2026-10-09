# Design & Privacy

Built in Python with no background tracking daemons, analytics services, or external vector databases.

* **Workspace Containment:** Operations outside the project root, mutating system commands (`systemctl`), and package managers (`sudo`, `pacman`, `pip`) require interactive `[y/N]` confirmation.
* **Local Secrets:** API credentials reside strictly in `~/.config/py-agent/.env` (permissions `0600`) and are not logged, exported, or included in prompt history.
* **Standard Library Core:** Python runtime orchestration without background embedding servers or external service daemons.

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
│ Terminal  │ │ (/adp)     │ │ Kernel   │ │ Kernel     │ │ & Context │ │ (Sessions & │
│ (Render)  │ │            │ │ (/py)    │ │ (Zero-Trust│ │           │ │  FTS5 Graph)│
└───────────┘ └────────────┘ └──────────┘ └────────────┘ └───────────┘ └─────────────┘
```

---

## Dual-Track Execution Architecture

Workspace capabilities (`/map`, `/mem`, `/yolo`, SQLite checkpoints) apply across all models. The runtime adapts tool execution and prompt schemas based on model size:

```console
                        DUAL-TRACK EXECUTION ENGINE
                      ┌───────────────────────────────┐
                      │   Stock Engine Core Router    │
                      │  (Universal: /map, /mem, OKF) │
                      └───────────────┬───────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
      TIER 1: Sub-27B SLM                            TIER 2: 27B+ MoE / LLM
      Baseline: Ling-3.0-tiny                        Baseline: Qwen3.8-35B-D
     ─────────────────────────                      ─────────────────────────────
     • Profile: lingtiny.md                         • Profile: Qwen38.md
     • Execution: Native 6-Tools                    • Execution: Dual-Mode (/py + Native)
     • /py: OFF (Avoids escaped code)               • /py: ON (In-Memory REPL & Testing)
     • Adapters: Opt-In (/adp Active)               • Adapters: OFF (Not Used by Default)
     • Reasoning: Dynamic /t (500t Default)         • Reasoning: Dynamic /t (500t Default)
     • Strength: Shell triage & direct diffs        • Strength: Multi-file edits & logic
```

### Technical Implementation

1. **Command Dispatcher (`agent_commands.py`):**
   - Decouples interactive slash commands (`/m`, `/mem`, `/t`, `/tts`, `/adp`, `/g`, etc.), file context injection, and surface launchers from the main CLI driver.
   - Passes execution state via a structured `SessionContext` without polluting the REPL loop.

2. **State & Locking Engine (`agent_state.py`):**
   - Implements process-level state persistence, `fcntl.flock` file locking, and atomic file swaps (`.state.json`) using Python standard library primitives.
   - Isolates Textual TUI interface state (`.tui_state.json`) from core engine state to avoid lock contention.

3. **Terminal Output & Stream Engine (`agent_stream.py`):**
   - Manages cursor positioning (`get_cursor_up_count`), live thinking displays, and lazy-initialized Rich Markdown rendering.
   - Separates terminal geometry from LLM streaming and tool execution.

4. **Context & Workspace Configuration (`agent_skills.py` & `agent_context.py`):**
   - Allows enabling or disabling `/map` (codebase index map) and `/mem` (Markdown memory files) via `ai init` or CLI toggles.
   - Profile frontmatter sets initial defaults; runtime hotkeys (`m`, `d`, `p`, `a`, `Tab`) take precedence and write to `<workspace>/.agent/config.json`.
   - `agent_context.py` provides conversation pruning (`prune_history`) and Jaccard intent matching, trimming older turns while preserving system prompts.

5. **Multimodal Vision Engine (`agent_vision.py`):**
   - Pre-processes image attachments, diagrams, and error screenshots through Gemini Flash Lite for text-only local models.
   - Validates URLs against private, link-local, loopback, and cloud metadata IP ranges (SSRF defense), enforces a 15 MB payload bound, and verifies local workspace boundaries.

6. **Agent Loop & Tool Injection (`agent_core.py`):**
   - Implements the multi-round turn loop (`agentic_turn`), thread-local HTTP sessions, and missing tool result backfilling (`_backfill_missing_tool_results`).
   - `ipython_mode == False`: Restricts tools to `tools.SMOL_TOOLS` (6 core tools: `read_file`, `edit_file`, `write_file`, `search_code`, `list_dir`, `run_command`).
   - `ipython_mode == True`: Adds `IPYTHON_TOOL` (`exec_python`).
   - `use_map == True`: Adds AST graph tools (`read_symbol`, `trace_symbol`, `blast_radius`, `find_symbol`, `architecture_overview`, `delegate_task`).

7. **Security & Path Enforcement (`agent_security.py`):**
   - Canonicalizes file paths using `os.path.commonpath`, removes synthetic container prefixes (`/workspace/`), checks system directory blocklists (`/etc`, `/usr`), and parses shell commands.
   - Enforces execution gates: in-bounds workspace actions auto-approve under YOLO mode, while out-of-bounds paths and mutating system commands always require interactive `[y/N]` confirmation.

8. **Tool Argument Adapters (`agent_adapters.py`):**
   - Disabled by default. Enabled per profile with `adapters: true` or toggled with `/adp`.
   - Normalizes parameter aliases (`file` -> `path`, `cmd` -> `command`), repairs unclosed JSON structures, and extracts markdown-wrapped tool calls out-of-band for smaller models.

9. **File Editing Engine (`agent_tools.py`):**
   - `_resilient_replace` applies diffs in three stages: exact match, whitespace-normalized, and 88% fuzzy match.
   - Validates changes with `ast.parse` before writing Python files to catch syntax regressions at the boundary.

---

## Module Hierarchy

```console
1. Shell & Entry Tier
   ├── ai-hook.sh               - Shell hook, directory tracking, and command-not-found handler
   ├── ai-agent.py              - CLI entrypoint, config resolution, REPL loop, and query router
   └── agent_commands.py        - Command dispatcher, slash actions, and surface routing

2. Execution & Streaming Engine
   ├── agent_core.py            - Agentic turn execution loop, tool validation, and scratchpad management
   ├── agent_stream.py          - Streaming SSE, cursor geometry, thinking formatting, and markdown rendering
   ├── agent_vision.py          - Vision pipeline, OCR pre-processing, SSRF filtering, and size bounds
   └── agent_adapters.py        - Sub-27B tool adapters (/adp), AST extractors, and JSON repair

3. Sandboxing, Tools & Safety
   ├── agent_security.py        - Boundary checks, path containment, and interactive gates
   ├── agent_tools.py           - 12-tool suite, container path handling, 3-stage replace, and AST syntax checks
   ├── agent_ipython.py         - Stateful IPython kernel, bounded output previews, and in-kernel delegation
   └── agent_skills.py          - Skill resolver, YAML frontmatter parser, and on-demand injection

4. Concurrency, UI & IPC
   ├── agent_tui.py             - Textual full-screen terminal workspace with dedicated .tui_state.json storage
   ├── agent_tui_async.py       - uvloop event loop, socket IPC hub, and memory file watcher
   └── agent_ui.py              - Terminal formatters, spinners, box themes, and interactive profile selector

5. Memory, State & Knowledge
   ├── agent_state.py           - Atomic state persistence (.state.json), file locks, and calm mode guards
   ├── agent_memories.py        - Markdown memory manager (.agent/memory/*.md)
   ├── agent_sessions.py        - SQLite session checkpoints (-save / -load) and turn logging
   └── agent_context.py         - Context compactor (prune_history) and Jaccard intent router

6. Cloud Providers & Auxiliary Services
   ├── agent_cloud.py           - .env provider resolution (Custom HF, Gemini, OpenRouter, DeepSeek)
   ├── model-select.py          - Interactive terminal model selector and .env key manager
   ├── agent_voice.py           - HTTPS voice bridge (:9999) with Wayland virtual typing (wtype)
   ├── agent_tts.py             - Kokoro text-to-speech module using PipeWire playback
   └── agent_chat.py            - Suggestion engine for /f, /tk, /b, and /a directives
```
