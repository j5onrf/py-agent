# Py-Agent Workspace & Session Manual

High-speed local developer agent, episodic memory, SQLite checkpoints, NOOA-enhanced IPython kernel harness, and codebase index-map.

```console
~ ❯ ling
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
 Startup context: 620 tokens

❯ /calm
 Calm mode enabled (silent tools & boat animation active).

❯ calculate the sum of all prime numbers between 10 and 50 in-memory using python and print the result.
            |>
-~~~-~~~-~\___/~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-

Agent: ✓ Task complete: Sum of all prime numbers between 10 and 50 is 311.
 [ think: 56 | ans: 18 | 74 tokens | 0.61s @ 121.31 t/s ]
 [ 767 in | 53 out | cch: 93% | ctx: 10.0% ]
❯ █
```

---

## UI Box Themes

Switch CLI box styles using `/box [1-8]` (or type `/box` to cycle). Selection persists in `~/.config/py-agent/.state.json`.

* **Style #1:** Codex Rounded (Default)
* **Style #2:** Double Border
* **Style #3:** Crisp Square*
* **Style #4:** Heavy Square
* **Style #5:** Minimalist Line
* **Style #6:** Diamond Nodes
* **Style #7:** Dashed / Synthwave
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
[ai init] Select default Agent Profile for workspace ling-tiny:

  ─── Custom ────────────────────────
     1. Custom Base          (~360t)
     2. Custom Deepseek      (~441t)
     3. Custom Gemini        (~410t)
     4. Custom Lfm2          (~360t)
  ❯  5. Custom Lingtiny      (~426t)
     6. Custom Minicpm       (~456t)
     7. Custom Q2B           (~349t)
     8. Custom Sysadmin      (~480t)

  ─── Agents ────────────────────────
     1. Pi Pro               (~367t)
     2. Claude Pro           (~391t)
     3. Hermes Pro           (~403t)

    Tools: ipython (1 tool, ~80t)         [+Map: ~350t | +Mem: ~40t]

  :: ↵ select    ↑/↓ navigate    Esc: default
     Tab: YOLO [ON]    m: Map [OFF]    d: Mem [OFF]    p: Py [ON]    a: Adp [ON]
```

* **Customize Profiles:** Modify or create profile `.md` files in `~/.config/py-agent/skills/profiles/`.
* **Instant Frontmatter Auto-Sync:** As you navigate `↑` / `↓` across profiles, the 5 toggles on Line 2 **automatically flip to reflect each author's recommended defaults.**
* **Real-Time Tools Inspector:** The `Tools:` line dynamically recalculates active tool schema cost (`ipython`, `native json`, or `index-map`) alongside prompt context add-ons (`[+Map | +Mem]`).
* **Single-Letter Overrides:**
  * **`Tab`** ➔ Toggle Autonomous YOLO mode (`[ON]` disables confirmation gates).
  * **`m`** ➔ Toggle Codebase Index-Map (11 tools + AST graph intelligence).
  * **`d`** ➔ Toggle Database Session Memory & OKF Memory Directives.
  * **`p`** ➔ Toggle In-Memory IPython Kernel Harness (`exec_python` single-tool mode).
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
│   /calm, /zen            - Toggle Calm mode (boat anime)            │
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
│   /hs, /hindsight        - Retrospective session memory audit       │
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

* **Dual Knowledge Layers:**
  * **Codebase AST Graph (Layer 1):** `.agent/index-map-memory-<ws>.db` SQLite FTS5 database storing AST structural connections, symbols, and line spans. Toggled via **`/m`**.
  * **Project Memory & Turn Log (Layer 2):** `<workspace>/.agent/memory/*.md` (OKF persistent directives) and `~/.config/py-agent/projects/.database/<ws>.db` (SQLite session turn checkpoints). Toggled via **`/mem`**.
* **Zero-Trust Mandatory Fallback:** Out-of-bounds workspace paths, mutating system actions (`systemctl start/stop/restart/mask`), and package modifications (`sudo`, `pacman -S/-R`, `pip`) **always trigger an interactive `[Y/n]` confirmation**, even in Autonomous YOLO mode. Safe read-only inspection commands (`pacman -Q*`, `systemctl status/list-units`, `journalctl`) run autonomously without prompts.
* **Prime Agent, NOOA & Smolagents In-Memory Kernel (`/py`):** Stateful Python REPL combining Prime Agent stateful execution with in-kernel `delegate("goal")` sub-agents and model-callable `memory`/`graph` APIs, NVIDIA NOOA bounded previews (`preview()`), and Hugging Face `smolagents` code-first batch loops with `final_answer(data)` completion hooks, guarded by a 30-second `SIGALRM` runaway loop breaker.
* **3-Stage Resilient File Editing (`edit_file`):**
  1. *Exact match* replacement.
  2. *Whitespace-normalized* indentation matching (handles 2- vs 4-space discrepancies).
  3. *SequenceMatcher fuzzy fallback* (replaces target blocks with $>88\%$ similarity without syntax corruption).

---

### 4.1 Adaptive Context Protection & File Inspection (`read_file`)

`py-agent` automatically scales file-reading ceilings and scratchpad thresholds based on your active context budget (`AI_MAX_TOKENS`):

| Context Budget (`AI_MAX_TOKENS`) | Target Environment | Auto Line Ceiling | Single-Call Character Cap |
| :--- | :--- | :---: | :---: |
| **≤ 16k** (8,192 – 16,384) | Local Models (2B–8B) | **250 lines** | ~20,000 chars |
| **32k** (32,768) | Cloud / 24GB GPU | **1,000 lines** | ~45,000 chars |
| **64k** (65,536) | DeepSeek / Claude / GPT | **2,000 lines** | ~90,000 chars |
| **≥ 128k** (131,072) | High-Capacity Cloud | **4,000 lines** | ~180,000 chars |

#### Configuring `AI_MAX_TOKENS`:
* **Model Selector TUI:** Run `model select` (or `cloud`), select `🧠 Context Budget`, and choose a preset (4k to 128k) or enter a custom limit.
* **Persistent Config (`.env`):** Edit `~/.config/py-agent/.env`:
  ```env
  AI_MAX_TOKENS="32768"
  ```
* **CLI Session Override:** Export in your shell or prepend to your launch command:
  ```bash
  export AI_MAX_TOKENS=32768
  # or single command:
  AI_MAX_TOKENS=65536 ai init ~/my-project
  ```
* **Scratchpad Offload:** Automatically offloads to `.agent/scratchpad/` only when tool output exceeds ~35% of the active context window.

---

## 5. Project Memory (OKF)

Persistent directives stored in `.agent/memory/*.md` that load automatically into prompt context when Memory is ON (`/mem` or `d` in selector).

### Quick Commands:
* `/mem save <topic>: <rule>` ➔ Save a new rule or preference (e.g. `/mem save os: User runs Arch Linux`).
* `/mem list` (or `/mem ls`) ➔ List active memory files and token weights.
* `/mem` ➔ Toggle memory injection ON / OFF.
* `/hs` (or `/hindsight`) ➔ Audit entire session history and extract durable engineering rules directly into `.agent/memory/`.

### Manual Editing:
Create or edit any `.md` file directly in `<workspace>/.agent/memory/` using any text editor (`nvim`, `nano`, `code`). Files are loaded in `< 0.1ms` on turn startup with zero background processes.

---

## 6. Client Surfaces

* **PyCode React Desktop IDE (`/pyc`):** Connects via ACP stdio JSON-RPC 2.0 with live thought/token streaming, ambient aurora glow, and workspace sync.
* **llama.cpp WebAgent (`/webui`):** Autonomous tool reverse proxy for `llama-server` (:8080) with auxiliary Gemini Flash Lite vision pre-processing.
* **Textual PyTUI (`/tui`):** Full-screen terminal interface with `uvloop` background services, real-time thought glimmer waves, adaptive light/dark theme typography, and compact 9-line Quick Tips.

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

---

## 8. Sub-27B Lite Model Directives

Models under ~27B (`Ling-3.0-tiny`, `LFM2.5-8B`, `MiniCPM5-2B`, `Qwen3.5-2B`) operate as **single-task execution engines** with constrained tool loops.

* **Single-Task Horizon:** Scope prompts to single-file, 1–2 turn tasks. Avoid chaining multi-file refactors in one prompt.
* **`write_file` for Small Files:** Use `write_file(path, content, overwrite=true)` on files < 50 lines to prevent multi-line `old_str` diff matching errors.
* **1-Line Terminal Exit:** Require an explicit halt pattern (`✓ Task complete: <summary>`) upon test pass (`OK`) to prevent post-verification looping.
* **Self-Healing Adapters (`agent_adapters.py`):** Automatically heals Hermes XML, DSML, Mistral, and naked JSON into executable tools without deleting parameter names like `"code"`.
* **Historical `<think>` Stripping:** Previous turns are stripped of reasoning before appending to context, preventing small models from compounding or repeating previous thoughts.

### 8.1 Adapter Performance Impact (`eval-stack`)

Empirical results across small quantized models (Sub-27B):

| Benchmark Challenge | Without Adapters | With `/adp` Active | Efficiency Gain |
| :--- | :---: | :---: | :--- |
| **AG-03 (Surgical Edit & Test)** | 16 turns | **6 turns** | **62% fewer turns** (eliminates diff-retry loops) |
| **AG-07 (In-Memory Batch Loop)** | 14 turns | **2 turns** | **85% fewer turns** (executes batch script on Turn 1) |
| **Full Suite Pass Rate** | Fragile / Retries | **100% (7/7)** | **Zero unhandled syntax or format failures** |

* **Why it matters:** Sub-27B models often emit malformed JSON, markdown code blocks, or broken import syntax. `/adp` heals these out-of-band, preventing wasted multi-turn recovery cycles and preserving active context window space on any hardware.
