# Py-Agent Workspace & Session Manual

High-speed local developer agent, episodic memory, SQLite checkpoints, NOOA-enhanced IPython kernel harness, and codebase index graph.

```console
~ ✗ ling
[01/02] ❯ [ling-tiny] ai init ~/ling-tiny
:: ↵ run  Esc: 
✓ Profile set to: Custom Lingtiny [Yolo: ON] [Map: ON] [Mem: ON] [Py: ON] [Adp: ON]

 Map enabled: compiled index-map.
╭─  ∿ Py Agent  ───────────────────────────────────────────╮
│     model:  Ling-3.0-tiny                                │
│ directory:  ~/.config/py-agent/projects/ling-tiny        │
│   profile:  custom/lingtiny                              │
│  database:  active (map + mem: 3m/5t)                    │
╰───────────────────────────────────────── Ctrl+C to exit ─╯
 Startup context: 467 tokens

❯ █
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
| `~/.config/py-agent/projects/.database/*.db` | Global SQLite session checkpoints (`-save` / `-load`) and turn rollbacks. |
| `~/.config/py-agent/.active_sessions/` | Sub-agent PID lockfiles for process tracking. |
| `~/.config/py-agent/.spend_ledger.json` | Cloud API token spend ledger (zero I/O on local models). |
| `~/<workspace>/.agent/config.json` | Workspace profile, YOLO, Map, Py, Memory, and Adapter settings. |
| `~/<workspace>/.agent/memory/*.md` | Git-native Open Knowledge Format (OKF) Markdown files for persistent directives. |
| `~/<workspace>/.agent/history.md` | Chronological session conversation log. |
| `~/<workspace>/.agent/scratchpad/` | Large tool outputs (>1,500 chars) offloaded to preserve active context. |
| `~/<workspace>/.agent/index-map-<project>.txt` | Shorthand codebase index map (injected into context when Map is ON). |
| `~/<workspace>/.agent/index-map-memory-<project>.db` | Relational AST symbol graph & SQLite FTS5 index. |

---

## 2. Profile Selector (`ai init`)

Running `ai init <path>` initializes a workspace and opens the interactive profile selector with instant RAM frontmatter pre-caching and single-letter hotkeys.

```console
[ai init] Select default Agent Profile for workspace project:

  ─── Custom ────────────────────────
     1. Custom Base          (~200t)
     2. Custom Lfm2          (~200t)
     3. Custom lingtiny      (~200t)
     4. Custom Q2B           (~200t)
     5. Custom Sysadmin      (~200t)

  ─── Agents ────────────────────────
     1. Pi Pro               (~180t)
     2. Claude Pro           (~190t)
  ❯  3. Hermes Pro           (~180t)

  :: ↵ select    ↑/↓ navigate    Esc: default
     Tab: YOLO [ON]    m: Map [OFF]    d: Mem [OFF]    p: Py [ON]    a: Adp [ON]
```

* **Customize Profiles:** Modify or create profile `.md` files in `~/.config/py-agent/skills/profiles/`.
* **Instant Frontmatter Auto-Sync:** As you navigate `↑` / `↓` across profiles, the 5 toggles on Line 2 **automatically flip to reflect each author's recommended defaults.**
* **Single-Letter Overrides:**
  * **`Tab`** ➔ Toggle Autonomous YOLO mode (`[ON]` disables confirmation gates).
  * **`m`** ➔ Toggle Codebase Index-Map (11 tools + AST graph intelligence).
  * **`d`** ➔ Toggle Database Session Memory & OKF Memory Directives.
  * **`p`** ➔ Toggle In-Memory IPython Kernel Harness (`exec_python`).
  * **`a`** ➔ Toggle Self-Healing Adapters (`agent_adapters.py` for ≤27B models).
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
│   /adp                   - Toggle small-model self-healing adapters │
│   /py [code]             - In-memory IPython kernel execution       │
│   /task [goal]           - Autonomous task loop                     │
│   /t [N|show|hide]       - Reasoning budget & display               │
│   /g, /yolo              - Toggle tool confirmation gates (YOLO)    │
│   /gnd [budget|on|off]   - Search grounding (Gemini / DDG)          │
│   /s <query|off>         - Load or unload on-demand skill           │
│   /f, /tk, /b, /a        - Follow-up, Think, Brainstorm, All modes  │
│                                                                     │
│   Memory & Workspace                                                │
│   /m, /map               - Toggle Codebase index-map                │
│   /mem [save|list]       - Toggle & manage OKF memory files         │
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

* **The Two Distinct Knowledge Layers:**
  * **Codebase AST Graph (Database 1):** `.agent/index-map-memory-<ws>.db` — SQLite FTS5 database storing AST structural relationships (functions, classes, line spans). Toggled independently via **`/m`**.
  * **Project Memory & Turn Log (Layer 2):** `<workspace>/.agent/memory/*.md` (OKF persistent directives) + `~/.config/py-agent/projects/.database/<ws>.db` (SQLite session turn checkpoints). Toggled independently via **`/mem`**.
* **Zero-Trust Mandatory Fallback:** Out-of-bounds workspace access (e.g. `/etc/`, `~/.ssh/`, external project dirs), mutating system actions (`systemctl start/stop/restart/mask`), and package manager modifications (`sudo`, `pacman -S/-R`, `pip`) **always trigger an interactive `[Y/n]` prompt**, even in Autonomous YOLO mode. Safe read-only inspection commands (`pacman -Q*`, `systemctl status/list-units`, `journalctl`) run autonomously without interruptions. This zero-trust boundary is strictly enforced across native tools, shell commands, and in-kernel Python execution (`agent_ipython.py`).
* **Smolagents Code-First Batching & Loop Protection:** Models operating in `/py` mode write composable Python loops (`read_file`, `search_code`, `list_dir`) to complete multi-step tasks in a single turn instead of ping-ponging single tool calls. Outputs are cleanly decoupled using `final_answer(data)`, and cells are guarded by a 30-second `SIGALRM` execution alarm to halt runaway `while True` loops.
* **3-Stage Resilient File Editing (`edit_file`):**
  1. *Exact match* replacement.
  2. *Whitespace-normalized* indentation matching (handles 2- vs 4-space discrepancies).
  3. *SequenceMatcher fuzzy fallback* (replaces target blocks with $>88\%$ similarity without corrupting file syntax).
* **AST Skeleton Read Guards:** Calling `read_file` on files > 250 lines returns top-level imports, class structures, and function line spans instead of a raw dump. Use `line_start` and `line_end` to read specific blocks.
* **Large Output Scratchpad Offload:** Tool results $> 1,500$ characters are automatically flushed to `.agent/scratchpad/<tool>_<timestamp>.txt`, injecting a concise 1,200-character preview with a pointer to prevent context overflow.
* **Child Sub-Agent Isolation (`delegate_task`):** Isolates research queries to a leaf worker that returns only a 1-line summary report. Guarded by `AI_SUBAGENT_DEPTH` to prevent recursive sub-agent storms.

---

## 5. Open Knowledge Format (OKF) Project Memory

Git-native, human-editable Markdown memory stored in `<workspace>/.agent/memory/*.md`. Zero daemons, zero background LLM calls.

### Commands:
* **`/mem`** ➔ Toggle memory injection ON / OFF.
* **`/mem save <title>: <content>`** ➔ Create or update a memory directive.
* **`/mem list`** (or `/mem ls`) ➔ List active memory files.
* **`/s hindsight`** ➔ Retrospective audit that extracts durable lessons into `.agent/memory/`.

### Manual Editing:
Create or edit `.agent/memory/<slug>.md` directly in any editor:

```yaml
---
title: Database Strategy
type: decision
tags: [sqlite, wal]
date: 2026-09-11
---
Use SQLite with WAL mode and busy_timeout = 30000 for zero-daemon concurrency.
```

### Execution Flow:
* **Memory ON (`/mem` / `d`):** Preloads all active rules and decisions into `<context>` (~50–200 tokens total).
* **Memory OFF:** 0 tokens injected.

---

## 6. Client Surfaces

* **PyCode React Desktop IDE (`/pyc`):** Connects via ACP stdio JSON-RPC 2.0 with live thought/token streaming, ambient aurora glow, and workspace sync.
* **llama.cpp WebAgent (`/webui`):** Autonomous tool reverse proxy for `llama-server` (:8080) with auxiliary Gemini Flash Lite vision pre-processing.
* **Textual PyTUI (`/tui`):** Full-screen terminal interface with `uvloop` background services, real-time thought glimmer waves, adaptive light/dark theme typography, and compact 9-line Quick Tips.
* **NOOA & Smolagents IPython Kernel (`/py`):** Live Python REPL combining NVIDIA NOOA bounded previews (`preview()`), Hugging Face `smolagents` code-first batch loops, and `final_answer()` completion hooks with real-time status line code previews.

---

## 7. Official Skill Frontmatter Schema

Skill profiles (`skills/profiles/**/*.md`) configure agent persona and defaults using YAML frontmatter (`---`).

```yaml
---
description: "Autonomous software engineer"
yolo: true
map: true
memory: true
ipython: true
adapters: true
reasoning_budget: 500
---
```

| Frontmatter Key | Type | Description |
| :--- | :---: | :--- |
| `description` | String | Profile summary displayed in the `ai init` selector menu. |
| `yolo` | Boolean | Sets default Autonomous YOLO mode (`true` turns off confirmation gates). |
| `map` | Boolean | Enables Codebase Index-Map (11 tools + AST graph context). |
| `memory` (or `mem`) | Boolean | Enables persistent session turn logging and OKF project memory pre-loading. |
| `ipython` (or `py`) | Boolean | Enables live persistent in-memory Python kernel harness (`exec_python`). |
| `adapters` (or `adp`) | Boolean | Enables self-healing tool parser (`agent_adapters.py`) for ≤27B models. |
| `reasoning_budget` | Integer | Deep reasoning token budget (e.g. `350`, `500`, or `0` to disable). |

---

## 8. Sub-27B Lite Model Directives

Models under ~27B (`Ling-3.0-tiny`, `LFM2.5-8B`, `MiniCPM5-2B`, `Qwen3.5-2B`) operate as **single-task execution engines** with constrained tool loops.

* **Single-Task Horizon:** Scope prompts to single-file, 1–2 turn tasks. Avoid chaining multi-file refactors in one prompt.
* **`write_file` for Small Files:** Use `write_file(path, content, overwrite=true)` on files < 50 lines to prevent multi-line `old_str` diff matching errors.
* **1-Line Terminal Exit:** Require an explicit halt pattern (`✔ Task complete: <summary>`) upon test pass (`OK`) to prevent post-verification looping.
* **Self-Healing Adapters (`agent_adapters.py`):** Automatically heals Hermes XML, DSML, Mistral, and naked JSON into executable tools without deleting parameter names like `"code"`.
* **Historical `<think>` Stripping:** Previous turns are stripped of reasoning before appending to context, preventing small models from compounding or repeating previous thoughts.

### 8.1 Adapter Performance Impact (`eval-stack`)

Empirical results running the full-stack benchmark suite on **Ling-3.0-tiny (7.9B MoE)**:

| Challenge | Without Adapters | With `/adp` Active | Efficiency Gain |
| :--- | :---: | :---: | :--- |
| **AG-03 (Surgical Edit & Test)** | 20.65s (16 turns) | **10.78s (6 turns)** | **62% fewer turns** (-10 turns) |
| **AG-07 (In-Memory Batch Loop)** | 30.37s (14 turns) | **13.48s (2 turns)** | **85% fewer turns** (-12 turns) |
| **Full Suite Total** | 123.45s @ 45.4 t/s | **92.39s @ 55.8 t/s** | **25% faster overall** (+10.4 t/s) |
