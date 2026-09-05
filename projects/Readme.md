# Py-Agent Workspace & Session Manual

High-speed local developer agent, episodic memory, SQLite checkpoints, NOOA-enhanced IPython kernel harness, and codebase index graph.

```console
✓ Profile set to: Hermes Pro [Yolo: ON] [Map: ON] [Mem: ON] [Py: ON]

 Map enabled: compiled index-map.
╭─  ∿ Py Agent  ───────────────────────────────────────────╮
│     model:  Hermes3.6-35B-A3B.gguf                       │
│ directory:  ~/.config/py-agent/projects/omarchyv4        │
│     skill:  hermes/pro                                   │
│  database:  active (0 facts, 0 turns)                    │
╰───────────────────────────────────────── Ctrl+C to exit ─╯
 Startup context: 896 tokens

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
| `~/<workspace>/.agent/config.json` | Project-scoped profile, YOLO, Map, Py, and Memory settings. |
| `~/<workspace>/.agent/session.jsonl` | Structured JSONL turn audit log (timestamp, model, tokens, messages). |
| `~/<workspace>/.agent/tpm.md` | Human-editable Markdown fact memory store. |
| `~/<workspace>/.agent/history.md` | Chronological session history log. |
| `~/<workspace>/.agent/task_log.md` | Audit log for autonomous `/task` loop executions. |
| `~/<workspace>/.agent/scratchpad/` | Large tool outputs (>1,500 chars) offloaded to preserve active context. |
| `~/<workspace>/.agent/index-map-<project>.txt` | Shorthand codebase index map (preloaded into prompt when Map is ON). |
| `~/<workspace>/.agent/index-map-memory-<project>.db` | Relational knowledge graph & `sqlite-vec` embeddings. |

---

## 2. Profile Selector (`ai init`)

Running `ai init <path>` initializes a workspace and opens the interactive profile selector with instant RAM frontmatter pre-caching and single-letter hotkeys.

```console
[ai init] Select default Agent Profile for workspace my-project:

  ─── Custom ────────────────────────
     1. Custom Base          (~200t)
     2. Custom Lfm2          (~200t)
     3. Custom Q2B           (~200t)

  ─── Agents ────────────────────────
     1. Pi Pro               (~180t)
     2. Claude Pro           (~190t)
  ❯  3. Hermes Pro           (~180t)

  :: ↵ select    ↑/↓ navigate    Esc: default
     Tab: YOLO [ON]    m: Map [ON]    d: Mem [ON]    p: Py [ON]
```

* **Customize Profiles:** Modify or create profile `.md` files in `~/.config/py-agent/skills/profiles/`.
* **Instant Frontmatter Auto-Sync** As you navigate `↑` / `↓` across profiles, the 4 toggles on Line 2 **automatically flip to reflect each author's recommended defaults**
* **Single-Letter Overrides:**
  * **`Tab`** ➔ Toggle Autonomous YOLO mode (`[ON]` disables confirmation gates).
  * **`m`** ➔ Toggle Codebase Index-Map (11 tools + AST graph intelligence).
  * **`d` (or `Shift+M`)** ➔ Toggle Database Session Memory & TPM Facts.
  * **`p`** ➔ Toggle In-Memory IPython Kernel Harness (`exec_python`).
* **Hierarchy of Precedence:** Manual button presses take precedence over frontmatter defaults and are saved permanently to `<workspace>/.agent/config.json`.
* **Auto-Compiling Index-Map:** When Map is `[ON]`, `ai init` automatically builds missing or stale index maps on startup and injects them directly into turn 0.

---

## 3. Command Reference (`/help`)

```console
╭─  ∿ Help & Commands  ───────────────────────────────────────────────╮
│   Shortcuts: Esc (Bypass)  •  Ctrl+C (Cancel)  •  q / exit (Quit)   │
│                                                                     │
│   Surfaces & Audio                                                  │
│   /pyc, /pyc web         - PyCode IDE (Desktop / WebUI)             │
│   /webui, /web           - WebUI gateway (llama.cpp)                │
│   /tui                   - Terminal UI (PyTUI)                      │
│   /v [auto], /voice      - Voice to text                            │
│   /tts                   - Text to speech (Kokoro)                  │
│                                                                     │
│   Agent & Execution                                                 │
│   /py [code]             - In-memory IPython kernel execution       │
│   /task [goal]           - Autonomous task loop                     │
│   /t [N|show|hide]       - Reasoning budget & display               │
│   /g, /yolo              - Toggle tool confirmation gates (YOLO)    │
│   /gnd [budget|on|off]   - Search grounding (Gemini / DDG)          │
│   /s <query|off>         - Load or unload on-demand skill           │
│   /f, /tk, /b, /a        - Follow-up, Think, Brainstorm, All modes  │
│                                                                     │
│   Memory & Workspace                                                │
│   /m, /map               - Toggle Codebase index-map (11 tools)     │
│   /mem, /memory          - Toggle database session memory & TPM     │
│   /com, /compact         - 3-Zone context compaction                │
│   /tok                   - Context token usage status               │
│   /sync                  - Sync codebase index-map AST graph        │
│   file <path>            - Load file into context                   │
│                                                                     │
│   Session Management                                                │
│   /box [1-8]             - Box style preset                         │
│   /stats                 - Generation speed stats                   │
│   /md                    - Toggle Markdown stream rendering         │
│   /clear, /c             - Soft clear active chat history           │
│   /reset, /r             - Hard reset (.agent & database purge)     │
│   -save <tag>            - Save checkpoint                          │
│   -load                  - Restore checkpoint                       │
│   exit, quit, q          - Exit conversation                        │
╰─────────────────────────────────────────────────────────────────────╯
```

---

## 4. Tooling & Safety Architecture

* **The Two Distinct Databases:**
  * **Database 1 (Codebase Graph):** `.agent/index-map-memory-<ws>.db` — Stores AST relationships (functions, classes, callers/callees). Toggled via **`/m`**.
  * **Database 2 (Session Memory):** `~/.config/py-agent/projects/database/<ws>.db` — Stores conversation history, checkpoints, and long-term user facts (TPM). Toggled via **`/mem`**.
* **Zero-Trust Mandatory Fallback:** Out-of-bounds file access (e.g. `/etc/os-release`, `~/.ssh/`) and system package commands (`sudo`, `pacman`, `pip`) **always trigger an interactive `[Y/n]` prompt**, even in Autonomous YOLO mode.
* **Kernel Zero-Trust Overrides (`agent_ipython.py`):** In Python REPL mode, `builtins.open` is intercepted during cell execution to enforce workspace boundaries while allowing background system threads (TTS, logging) to operate without false alarms.
* **3-Stage Resilient File Editing (`edit_file`):**
  1. *Exact match* replacement.
  2. *Whitespace-normalized* indentation matching (handles 2- vs 4-space discrepancies).
  3. *SequenceMatcher fuzzy fallback* (replaces target blocks with $>88\%$ similarity without corrupting file syntax).
* **AST Skeleton Read Guards:** Calling `read_file` on files > 250 lines returns top-level imports, class structures, and function line spans instead of a raw dump. Use `line_start` and `line_end` to read specific blocks.
* **Large Output Scratchpad Offload:** Tool results $> 1,500$ characters are automatically flushed to `.agent/scratchpad/<tool>_<timestamp>.txt`, injecting a concise 1,200-character preview with a pointer to prevent context overflow.
* **Child Sub-Agent Isolation (`delegate_task`):** Isolates research queries to a leaf worker that returns only a 1-line summary report. Guarded by `AI_SUBAGENT_DEPTH` to prevent recursive sub-agent storms.

---

## 5. Client Surfaces

* **PyCode React Desktop IDE (`/pyc`):** Connects via ACP stdio JSON-RPC 2.0 with live thought/token streaming, ambient aurora glow, and workspace sync.
* **llama.cpp WebAgent (`/webui`):** Autonomous tool reverse proxy for `llama-server` (:8080) with auxiliary Gemini Flash Lite vision pre-processing.
* **Textual PyTUI (`/tui`):** Full-screen terminal interface with `uvloop` background services, real-time thought glimmer waves, adaptive light/dark theme typography, and compact 9-line Quick Tips.
* **NOOA IPython Kernel (`/py`):** Live Python REPL keeping variables, imports, and DataFrames in memory across conversational turns, with real-time status line code previews.

---

## 6. Official Skill Frontmatter Schema

Skill profiles (`skills/profiles/**/*.md`) configure agent persona and defaults using YAML frontmatter (`---`).

```yaml
---
description: "Hermes autonomous software engineer"
yolo: true
map: true
memory: true
ipython: true
reasoning_budget: 350
---
```

| Frontmatter Key | Type | Description |
| :--- | :---: | :--- |
| `description` | String | Profile summary displayed in the `ai init` selector menu. |
| `yolo` | Boolean | Sets default Autonomous YOLO mode (`true` turns off confirmation gates). |
| `map` | Boolean | Enables Codebase Index-Map (11 tools + AST graph context). |
| `memory` (or `mem`) | Boolean | Enables persistent session turn logging and TPM user fact extraction. |
| `ipython` (or `py`) | Boolean | Enables live persistent in-memory Python kernel harness (`exec_python`). |
| `reasoning_budget` | Integer | Deep reasoning token budget (e.g. `350`, `500`, or `0` to disable). |

---

## 7. Sub-27B Lite Model Directives

Models under ~27B (`LFM2.5-8B`, `Qwen3.5-2B`) operate as **single-task execution engines** with constrained tool loops.

* **Single-Task Horizon:** Scope prompts to single-file, 1–2 turn tasks. Avoid chaining multi-file refactors in one prompt.
* **`write_file` for Small Files:** Use `write_file(path, content, overwrite=true)` on files < 50 lines to prevent multi-line `old_str` diff matching errors.
* **1-Line Terminal Exit:** Require an explicit halt pattern (`✔ Task complete: <summary>`) upon test pass (`OK`) to prevent post-verification looping.
* **Self-Healing Adapters (`agent_adapters.py`):** Automatically heals Hermes XML, DSML, Mistral, and naked JSON into executable tools without deleting parameter names like `"code"`.
* **Historical `<think>` Stripping:** Previous turns are stripped of reasoning before appending to context, preventing small models from compounding or repeating previous thoughts.
