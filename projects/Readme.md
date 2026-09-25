# Py-Agent Workspace & Session Manual

Autonomous local developer agent with OKF memory, in-memory Python, and codebase indexing.

```console
~ ❯ ling
[01/02] > [ling-tiny] ai init ~/ling-tiny
OK: Profile set to: Custom Lingtiny [Yolo: ON] [Map: ON] [Mem: ON] [Py: ON] [Adp: ON]

 Map enabled: compiled index-map.
╭─ ∿ Py Agent ─────────────────────────────────────────────╮
│     model:  Ling-3.0-tiny                                │
│ directory:  ~/.config/py-agent/projects/ling-tiny        │
│   profile:  custom/lingtiny                              │
│  database:  active (map + mem: 3m/5t)                    │
╰──────────────────────────────────────────────────────────╯

❯ /calm
 [Calm On]
 
❯ /stats
 [Stats On]

❯ calculate the sum of all prime numbers between 10 and 50 and print the result.
            |>
-~~~-~~~-~\___/~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-~~~-

Agent: Task complete: Sum is 311.
 [ think: 56 | ans: 18 | 74 tokens | 0.61s @ 121.31 t/s ]
 [ 767 in | 53 out | cch: 93% | ctx: 10.0% ]
 
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
* **Style #7:** Dashed Line
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
~ ❯ sess
[01/01] > [session test] ai init ~/session-test

[ai init] Select default Agent Profile for workspace session-test:

  ─── Cloud ─────────────────────────
  >  1. Cloud                (~633t)
     2. Deepseek             (~431t)

  ─── Local ─────────────────────────
     1. Katcoder             (~574t)
     2. Lfm2                 (~588t)
     3. Lingtiny             (~458t)
     4. Minicpm              (~464t)
     5. Nexn25               (~606t)
     6. Occamy               (~575t)
     7. Ornith               (~677t)
     8. Q2Bu                 (~466t)
     9. Qwen38D              (~444t)
    10. Tielcoder            (~522t)

  ─── Roles ─────────────────────────
     1. Sysadmin             (~442t)
     2. Tini Cybersec        (~664t)

    Tools: python + native (7 tools, ~760t)

  :: Enter select    Up/Down navigate    Esc: default
     Tab: YOLO [ON]    m: Map [OFF]    d: Mem [OFF]    p: Py [ON]    a: Adp [OFF]
```

* **Customize Profiles:** Modify or create profile `.md` files in `~/.config/py-agent/skills/profiles/`.
* **Instant Frontmatter Auto-Sync:** Navigating `Up` / `Down` across profiles automatically synchronizes the toggle row to reflect each profile's frontmatter defaults.
* **Real-Time Tools Inspector:** The `Tools:` line dynamically calculates active tool schema cost (`ipython`, `native json`, or `index-map`) alongside prompt context add-ons (`[+Map | +Mem]`).
* **Single-Letter Overrides:**
  * **`Tab`** -> Toggle Autonomous YOLO mode (`[ON]` disables confirmation gates).
  * **`m`** -> Toggle Codebase Index-Map (12 tools + AST graph intelligence).
  * **`d`** -> Toggle Database Session Memory & OKF Memory Directives.
  * **`p`** -> Toggle In-Memory IPython Kernel Harness (`exec_python` tool execution).
  * **`a`** -> Toggle Self-Healing Adapters (`agent_adapters.py` universal out-of-band safety net).
* **Hierarchy of Precedence:** Manual toggle overrides take precedence over frontmatter defaults and are saved to `<workspace>/.agent/config.json`.
* **Auto-Compiling Index-Map:** When Map is `[ON]`, `ai init` automatically builds missing or stale index maps on startup and injects them directly into turn 0.

---

## 3. Command Reference (`/help`)

```console
╭─  Help & Commands  ─────────────────────────────────────────────────╮
│   Shortcuts: Esc (Bypass)  |  Ctrl+C (Cancel)  |  q / exit (Quit)   │
│                                                                     │
│   Surfaces & Audio                                                  │
│   /pyc, /pyc web         - PyCode IDE (Desktop / WebUI)             │
│   /webui, /web           - WebUI gateway (llama.cpp)                │
│   /tui                   - Terminal UI (PyTUI)                      │
│   /calm, /zen            - Toggle Calm mode (boat progress)         │
│   /v [auto], /voice      - Voice to text                            │
│   /tts                   - Text to speech (Kokoro)                  │
│                                                                     │
│   Agent & Execution                                                 │
│   /adp                   - Toggle universal self-healing adapters   │
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

## 4. Adaptive Resilience & Model Tuning (/adp)

* **Scope to Single Tasks:** Keep prompts focused on 1 file or 1 objective per turn for maximum accuracy.
* **Universal Safety Net:** While originally designed for Sub-27B SLMs, `/adp` operates non-invasively across all model tiers (including 27B+ and MTP speculative builds). If a model emits 100% compliant native tool calls, the adapter does not execute (0ms overhead). If quantization or speculative drafting causes markdown code fencing or parameter aliasing, `/adp` rescues the call on Turn 1, preventing multi-turn recovery loops.

### 4.1 Adapter Performance Impact (`eval-stack`)

Empirical results across models with `/adp` active:

| Benchmark Challenge | Without Adapters | With `/adp` Active | Efficiency Gain |
| :--- | :---: | :---: | :--- |
| **AG-03 (Surgical Edit & Test)** | 16 turns | **6 turns** | **62% fewer turns** (eliminates diff-retry loops) |
| **AG-07 (In-Memory Batch Loop)** | 14 turns | **2 turns** | **85% fewer turns** (executes batch script on Turn 1) |
| **Full Suite Pass Rate** | Retries / Failures | **100% (7/7)** | **Zero unhandled syntax or format failures** |

---

## 5. Tooling & Safety

### 5.1 Operational Tiers & Token Footprint
* **Pure Chat (`ai`):** **211 tokens** (ultra-minimal, zero tools).
* **Native Mode (`Py: OFF`):** **6 tools (`SMOL_TOOLS`)**, ~680t schema.
* **Dual Mode (`Py: ON`):** **7 tools (`python + native`)**, ~760t schema with ~95% KV cache hits.
* **Full Graph Mode (`Map: ON`):** **12 tools (`EDIT_TOOLS`)**, ~1.1kt schema.
* **OKF Memory:** `.agent/memory/*.md` with 1-shot `/hs` retrospective audits.

### 5.2 Guardrails & Execution
* **Zero-Trust Safety Gate (`agent_security.py`):** System mutations (`sudo`, `pacman`, `systemctl`) and out-of-bounds file access strictly ignore YOLO mode and always require interactive `[y/N]` confirmation.
* **Surgical File Edits (`edit_file`):** 3-stage replacement (Exact -> Whitespace-tolerant -> 88% Fuzzy match).
* **Adaptive Reads (`read_file`):** Automatically switches to an AST structural outline when files exceed your active context ceiling (250 to 4,000 lines).

### 5.3 Adaptive Context Protection & File Inspection (`read_file`)

`py-agent` automatically scales file-reading ceilings and scratchpad thresholds based on your active context budget (`AI_MAX_TOKENS`):

| Context Budget (`AI_MAX_TOKENS`) | Target Environment | Auto Line Ceiling | Single-Call Character Cap |
| :--- | :--- | :---: | :---: |
| **<= 16k** (8,192 - 16,384) | Local Models (2B-8B) | **250 lines** | ~20,000 chars |
| **32k** (32,768) | Cloud / 24GB GPU | **1,000 lines** | ~45,000 chars |
| **64k** (65,536) | DeepSeek / Claude / GPT | **2,000 lines** | ~90,000 chars |
| **>= 128k** (131,072) | High-Capacity Cloud | **4,000 lines** | ~180,000 chars |

#### Configuring `AI_MAX_TOKENS`:
* **Model Selector TUI:** Run `model select` (or `cloud`), choose Context Budget, and select a preset or custom limit.
* **Persistent Config (`.env`):** Edit `~/.config/py-agent/.env` and set `AI_MAX_TOKENS=<limit>`.
* **Scratchpad Offload:** Automatically offloads to `.agent/scratchpad/` only when tool output exceeds ~35% of the active context window.

---

## 6. Project Memory (OKF)

Persistent directives stored in `.agent/memory/*.md` that load automatically into prompt context when Memory is ON (`/mem` or `d` in selector).

### Quick Commands:
* `/mem save <topic>: <rule>` -> Save a new rule or preference (e.g. `/mem save os: User runs Arch Linux`).
* `/mem list` (or `/mem ls`) -> List active memory files and token weights.
* `/mem` -> Toggle memory injection ON / OFF.
* `/hs` (or `/hindsight`) -> Audit session history and extract durable engineering rules into `.agent/memory/`.

### Manual Editing:
Create or edit any `.md` file directly in `<workspace>/.agent/memory/` using any text editor (`nvim`, `nano`, `code`). Files are loaded in `< 0.1ms` on startup with zero background process overhead.

---

## 7. Client Surfaces

* **PyCode React Desktop IDE (`/pyc`):** Connects via ACP stdio JSON-RPC 2.0 with live token streaming and workspace synchronization.
* **llama.cpp WebAgent (`/webui`):** Autonomous tool reverse proxy for `llama-server` (:8080) with auxiliary Gemini Flash Lite vision pre-processing.
* **Textual PyTUI (`/tui`):** Full-screen terminal interface with `uvloop` background services, real-time thought shimmer, adaptive theme typography, and compact Quick Tips.

---

## 8. Official Skill Frontmatter Schema

Skill profiles (`skills/profiles/**/*.md`) configure agent persona and defaults using YAML frontmatter (`---`).

```yaml
---
description: "Autonomous software engineer"
category: "Cloud"          # Optional: Cloud (0) → Local (1) → Roles (2) → Custom (3+)
yolo: true
map: true
memory: true
ipython: true
adapters: true
reasoning_budget: 500
---
```

* **`category` (optional):** Section header in `ai init`. Built-in ordering: `Cloud` (0) → `Local` (1) → `Roles` (2) → Any custom frontmatter categories (3+). If omitted, category is inferred automatically from the filename.
