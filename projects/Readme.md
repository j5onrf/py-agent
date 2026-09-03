# Py-Agent Workspace & Session Manual

High-speed local developer agent, episodic memory, SQLite checkpoints, NOOA-enhanced IPython kernel harness, and codebase index graph.

```console
✓ Profile set to: Pi Py-Pro (Autonomous YOLO)

╭─  ∿ Py Agent  ───────────────────────────────────────────╮
│     model:  Qwen3.6-35B-A3B.gguf                         │
│ directory:  ~/.config/py-agent/projects/session-test-2   │
│     skill:  pi/py-pro                                    │
│  database:  active (1 facts, 1 turns)                    │
╰───────────────────────────────────────── Ctrl+C to exit ─╯
 Startup context: 743 tokens

Agent: Workspace loaded. Awaiting instructions.
❯ 
```

---

## UI Box Themes

Switch CLI box styles using `/box [1-8]` (or type `/box` to cycle). Selection persists in `~/.config/py-agent/.state.json`.

* **Style #1:** Codex Rounded (Default)
* **Style #2:** Double Border
* **Style #3:** Crisp Square
* **Style #4:** Heavy Square
* **Style #5:** Minimalist Line
* **Style #6:** Diamond Nodes
* **Style #7:** Dashed / Cyberpunk
* **Style #8:** Dual-Chamber Inset

---

## 1. Directory Structure

All auto-created agent metadata files are strictly isolated inside `project/.agent/` to keep workspaces clean.

| Path | Purpose |
| :--- | :--- |
| `~/.config/py-agent/projects/database/*.db` | Global SQLite turn history and fact memory database. |
| `~/.config/py-agent/.active_sessions/` | Sub-agent PID lockfiles for process tracking. |
| `~/.config/py-agent/.spend_ledger.json` | Global cloud API token usage and daily spend ledger. |
| `~/<workspace>/.agent/config.json` | Default workspace agent profile and YOLO settings. |
| `~/<workspace>/.agent/session.jsonl` | Structured JSONL turn audit log (timestamp, model, tokens, messages). |
| `~/<workspace>/.agent/tpm.md` | Human-editable Markdown fact memory store. |
| `~/<workspace>/.agent/history.md` | Chronological session history log. |
| `~/<workspace>/.agent/task_log.md` | Audit log for autonomous `/task` loop executions. |
| `~/<workspace>/.agent/index-map-<project>.txt` | Shorthand codebase index map (Agent mode). |
| `~/<workspace>/.agent/index-map-memory-<project>.db` | Relational knowledge graph & `sqlite-vec` embeddings. |

---

## 2. Profile Selector (`ai init`)

Running `ai init <path>` initializes a workspace and opens the interactive profile selector:

```console
[ai init] Select default Agent Profile for workspace my-project:

  ─── Custom ────────────────────────
  ❯  1. Custom Base          (~150t)  <-- Lean (5 tools, Map: OFF)
     2. Custom Base-Map      (~300t)  <-- Index-Map (10 tools, Map: ON)
     3. Custom Base-Py       (~280t)  <-- In-Kernel (Map: OFF)
     4. Custom LFM2          (~240t)  <-- Lite 8B Single-Task Dev

  ─── Agents ────────────────────────
     1. Pi Pro               (~180t)  <-- Fast 5-Tool JSON Agent
     2. Claude Pro           (~190t)
     3. Hermes Pro           (~180t)
     1. Pi Pro-Map           (~280t)  <-- 10-Tool Index-Map Agent (Map: ON)
     2. Claude Pro-Map       (~290t)
     3. Hermes Pro-Map       (~280t)

  ─── Py ────────────────────────────
     1. Pi Py-Pro            (~200t)  <-- Lean Python Kernel REPL
     2. Claude Py-Pro        (~210t)
     3. Hermes Py-Pro        (~200t)
     1. Pi Py-Pro-Map        (~300t)  <-- Python Kernel + Index-Map SDK (Map: ON)
     2. Claude Py-Pro-Map    (~310t)
     3. Hermes Py-Pro-Map    (~300t)

  :: ↵ select  ↑/↓ navigate  Tab: YOLO [OFF]  m: Map [OFF]  Esc: default
```

* **Customize:** Modify or create profile `.md` files in `~/.config/py-agent/skills/profiles/`.
* **Reset Workspace:** Type `/reset` in chat to clear conversation history, purge `.agent/` and database records, and start fresh.

---

## 3. Command Reference (`/help`)

```console
╭─  ∿ Help & Commands  ───────────────────────────────────────────────╮
│   Shortcuts: Esc (Bypass)  •  Ctrl+C (Cancel)  •  q / exit (Quit)   │
│                                                                     │
│   Surfaces & Audio                                                  │
│   /pyc, /pyc web         - Launch PyCode IDE (Desktop / WebUI)      │
│   /webui, /web           - Launch WebAgent UI (llama.cpp)           │
│   /tui                   - Launch interactive terminal UI (PyTUI)   │
│   /v [auto], /voice      - Toggle voice-to-text bridge              │
│   /tts                   - Toggle neural text-to-speech             │
│                                                                     │
│   Agent & Execution                                                 │
│   /py [code]             - Toggle or execute via IPython kernel     │
│   /task [goal]           - Start autonomous task loop               │
│   /t [N|show|hide]       - Configure reasoning budget & display     │
│   /g, /yolo              - Toggle tool confirmation gates (YOLO)    │
│   /gnd [budget|on|off]   - Search grounding (Gemini / DDG)          │
│   /s <query|off>         - Load or unload on-demand skill           │
│   /f, /tk, /b, /a        - Follow-up, Think, Brainstorm, All modes  │
│                                                                     │
│   Memory & Workspace                                                │
│   /m                     - Toggle SQLite memory & facts (TPM)       │
│   /com, /compact         - 3-Zone compaction & token reclaim        │
│   /tok                   - Show context token breakdown             │
│   /sync                  - Synchronize codebase index-map           │
│   file <path>            - Load file contents into context          │
│                                                                     │
│   Session Management                                                │
│   /box [1-8]             - Switch banner box style preset           │
│   /stats                 - Toggle generation speed & TPS stats      │
│   /md                    - Toggle Markdown stream rendering         │
│   /clear, /c             - Clear active chat history                │
│   /reset, /purge         - Reset workspace (.agent & database)      │
│   -save <tag>            - Save session checkpoint                  │
│   -load                  - Restore session checkpoint               │
│   exit, quit, q          - Exit session                             │
╰─────────────────────────────────────────────────────────────────────╯
```

---

## 4. Tooling & Safety Architecture

* **AST Skeleton Read Guards:** Calling `read_file` on files > 250 lines returns top-level imports, class structures, and function line spans instead of a blind head-slice. Use `line_start` and `line_end` to read specific blocks.
* **Whitespace-Tolerant `edit_file`:** Automatically handles 1–2 space indentation mismatches and trailing whitespace differences.
* **Mandatory Fallback Security Gates:** Out-of-bounds file targets and package managers (`pip`, `pacman`, `sudo`) **always trigger an interactive `[Y/n]` prompt**, even in Autonomous YOLO mode. Denials halt tool execution immediately.
* **Modular Adapter Layer (`agent_adapters.py`):** Self-healing parser resolving Hermes XML, DSML, Mistral, naked JSON, and raw function calls out-of-band without bloating the core engine.
* **3-Zone Context Compactor (`/compact`):** Condenses intermediate tool turns while preserving a completed milestone progress anchor.

---

## 5. Client Surfaces

* **PyCode React Desktop IDE (`/pyc`):** Connects via ACP stdio JSON-RPC 2.0 with live thought/token streaming, ambient aurora glow, and workspace sync.
* **llama.cpp WebAgent (`/webui`):** Autonomous tool reverse proxy for `llama-server` (:8080) with auxiliary Gemini Flash Lite vision pre-processing.
* **Textual PyTUI (`/tui`):** Full-screen terminal interface with `uvloop` background workers, sub-agent IPC sockets, and real-time reasoning waves.
* **NOOA IPython Kernel (`/py`):** Stateful Python REPL keeping DataFrames, variables, and imports in RAM with pass-by-reference previews (`preview()`) and `delegate()` sub-agents.

---

## 6. Execution, Loops & Sub-Agents

* **In-Kernel SDK Objects (`/py`):** Provides model-callable `graph` (snippets, call trees, blast radius), `memory` (search, facts), `preview(obj)`, and sandbox `delegate("goal")` directly in Python RAM.
* **Autonomous Task Loops (Ralph Engine):** `/task "goal"` (or `TASK.md`) runs self-directed iterations with failure decomposition and completion detection.
* **Sub-Agents & Concurrency:** In-kernel `delegate()` sandbox sub-agents + multi-terminal `ai init` instances with self-healing PID locks and SQLite `WAL` mode.
* **Skill Frontmatter (`---`):** YAML headers configure `reasoning_budget`, `yolo`, `map`, and `ipython` overrides automatically on profile load.
* **Reasonix Cognitive Engine (`/t`):** `/t <N>` configures reasoning token budgets while `/t show|hide` toggles real-time thinking panel visibility.
* **Context Budget Override:** Override limits per session: `AI_MAX_TOKENS=16000 ai init ~/my-project`.

---

## 7. Memory, Knowledge & Audio

* **Checkpoints (`-save` / `-load`):** Snapshot and restore episodic memory and conversation states to SQLite across sessions.
* **On-Demand Skills (`/s <skill>`):** Stack up to 3 specialized prompts (`/s pirate`, `/s ponytail`) on the fly with automatic category auto-swapping and `/s off` reset.
* **Codebase Graph Mapper (`index-map`):** Dual-mode AST call graph mapping across 7 languages with `sqlite-vec` semantic vector search.
* **Temporal Personality Memory (TPM):** Async extraction compiles persistent human facts into `<context>` blocks, synced via `.agent/tpm.md`.
* **Voice & Neural Audio (`/v` & `/tts`):** Zero-latency HTTPS tablet/phone voice bridge (`:9999`) + local PipeWire Kokoro TTS reader with silent thinking/code filtering.
* **Google Search Grounding (`/gnd`):** Real-time web search retrieval via Gemini Grounding (`/gnd [budget]`) with automatic DuckDuckGo fallback across all surfaces.

---

## 8. Sub-27B Lite Model Directives

Models under ~27B (`LFM2.5-8B`, `Qwen3.5-2B`) operate as **single-task execution engines** with constrained tool loops.

* **Atomic Task Horizon:** Scope prompts to single-file, 1–2 turn tasks. Avoid chaining multi-file refactors in one prompt.
* **`write_file` for Small Files:** Use `write_file(path, content, overwrite=true)` on files < 50 lines to prevent multi-line `old_str` diff matching errors.
* **1-Line Terminal Exit:** Require an explicit halt pattern (`✔ Task complete: <summary>`) upon test pass (`OK`) to prevent post-verification looping.
* **Tokenizer Escaping Guard:** Avoid raw ellipsis literals (`+ "..."`) in prompt templates to prevent tokenizer quote-dropping syntax errors.
* **Self-Healing Adapters (`agent_adapters.py`):** Automatically intercepts raw planning envelopes (`{"analysis": ...}`, `{"commands": ...}`), DSML, and naked JSON into executable tools.
* **Constrained Reasoning:** Keep reasoning budgets between 350–500 tokens.
