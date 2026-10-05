# Py-Agent Workspace & Session Manual

Autonomous local developer agent with OKF memory, iPython, and codebase index-map.

```console
~ ❯ ling
[01/01] > [ling-tiny] ai init ~/ling-tiny
✓ Profile set to: Lingtiny [Yolo: ON] [Adp: ON]

╭─ ∿ Py Agent ────────────────────────────────────────╮
│     model:  Ling-3.0-tiny                           │
│ directory:  ~/.config/py-agent/projects/ling-tiny   │
│   profile:  lingtiny                                │
│  database:  stateless                               │
╰─────────────────────────────────────────────────────╯

❯ write a python binary search tree with insert and search methods

╭─ ∿ ────────────────────────────────────────────────────
The user wants a Python binary search tree with insert and search methods. I need to create a Python
script that implements a BST with these methods.
╰────────────────────────────────────────────────────────

  ∗ updating • write_file binary_search_tree.py
  ✓ Done (0.1s)

╭─ ∿ ────────────────────────────────────────────────────
Let me verify the file was created correctly and then provide a summary.
╰────────────────────────────────────────────────────────

Agent: ✓ Task complete: Created a Python BST with insert and search methods.

  [ ↑767 ↓14 R22 · CH97% · 9.8%/8.2k · 0.44s @ 121.31 t/s ]

❯ █
```

---

## UI Box Themes

Switch CLI box styles using `/box [1-7]` (or `/box` to cycle). Persists in `~/.config/py-agent/.state.json`.

| Box Style | Preset Name | Thinking Box Geometry |
| :---: | :--- | :---: |
| **#1** | **Codex Rounded** *(Default)* | **Rounded** (`╭` and `╰`) |
| **#2** | **Crisp Square** | **Square** (`┌` and `└`) |
| **#3** | **Double Border** | **Square** (`┌` and `└`) |
| **#4** | **Heavy Square** | **Square** (`┌` and `└`) |
| **#5** | **Minimalist Line** | **Square** (`┌` and `└`) |
| **#6** | **Dual-Chamber Inset** | **Rounded** (`╭` and `╰`) |
| **#7** | **Minimalist Clean** | **Rounded** (`╭` and `╰`) |

---

## 1. Directory Structure

Workspace metadata is isolated inside `project/.agent/`.

| Path | Purpose |
| :--- | :--- |
| `~/.config/py-agent/projects/.database/*.db` | SQLite session checkpoints (`-save` / `-load`) and turn rollbacks. |
| `~/.config/py-agent/.active_sessions/` | Active process PID tracking files. |
| `~/.config/py-agent/.spend_ledger.json` | Cloud API token spend ledger. |
| `~/<workspace>/.agent/config.json` | Workspace runtime profile, YOLO, Map, Py, and Memory state. |
| `~/<workspace>/.agent/memory/*.md` | Git-native Open Knowledge Format (OKF) Markdown files. |
| `~/<workspace>/.agent/history.md` | Chronological session conversation log. |
| `~/<workspace>/.agent/scratchpad/` | Large tool outputs (>1,500 chars) offloaded to preserve context. |
| `~/<workspace>/.agent/worktrees/agent-<id>/` | Ephemeral Git worktree checkouts for sub-agent sandboxing. |
| `~/<workspace>/.agent/index-map-<project>.txt` | Shorthand codebase index map. |
| `~/<workspace>/.agent/index-map-memory-<project>.db` | AST symbol graph & SQLite FTS5 index. |

---

## 2. Profile Selector (`ai init`)

`ai init <path>` opens the profile selector with RAM frontmatter pre-caching.

```console
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

* **Customize Profiles:** `.md` files in `~/.config/py-agent/skills/profiles/`.
* **Navigation:** `Up`/`Down` synchronizes toggles to the profile's frontmatter defaults.
* **Overrides:**
  * **`Tab`** -> YOLO Mode (`[ON]` disables tool confirmation prompts).
  * **`m`** -> Codebase Map (12 tools + AST graph).
  * **`d`** -> Session Memory & OKF directives.
  * **`p`** -> IPython Kernel (`exec_python` tool execution).
  * **`a`** -> Universal Self-Healing Adapters (`/adp`).

---

## 3. Command Reference (`/help`)

```console
╭─  Help & Commands  ─────────────────────────────────────────────────╮
│   Shortcuts: Esc (Bypass)  |  Ctrl+C (Cancel)  |  q / exit (Quit)   │
│                                                                     │
│   Surfaces & Audio                                                  │
│   /pyc, /pyc web         - PyCode IDE (Desktop / WebUI)             │
│   /dsh                   - DeepSeek Harness (dsh)                   │
│   /zed                   - Zed editor (ACP integration)             │
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
│   /box [1-7]             - Box style preset                         │
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

## 4. Adaptive Resilience (/adp)

The `/adp` layer rescues malformed JSON, unclosed quotes, and sequence drift on Turn 1 with zero runtime overhead on compliant models.

| Benchmark Challenge | Without `/adp` | With `/adp` Active | Efficiency Gain |
| :--- | :---: | :---: | :--- |
| **AG-03 (Surgical Edit & Test)** | 16 turns | **6 turns** | **62% fewer turns** |
| **AG-07 (In-Memory Batch Loop)** | 14 turns | **2 turns** | **85% fewer turns** |
| **Full Suite Pass Rate** | Failures / Retries | **100% (7/7)** | **Zero unhandled syntax failures** |

---

## 5. Tooling, Context & Safety

### 5.1 Operational Tiers
* **Pure Chat (`ai`):** **211 tokens** (zero tools).
* **Native Mode (`Py: OFF`):** **6 tools (`SMOL_TOOLS`)**, ~680t schema.
* **Dual Mode (`Py: ON`):** **7 tools (`python + native`)**, ~760t schema with ~95% KV cache hits.
* **Index-Map Mode (`Map: ON`):** **12 tools (`EDIT_TOOLS`)**, ~1.1kt schema.

### 5.2 Context Ceilings & Scratchpad Scaling
File ceilings dynamically adapt to `AI_MAX_TOKENS`:

| Budget (`AI_MAX_TOKENS`) | Target Environment | Line Ceiling | Character Cap |
| :--- | :--- | :---: | :---: |
| **<= 16k** | Local Models (2B–35B) | **250 lines** | ~20,000 chars |
| **32k** | Cloud / 24GB GPU | **1,000 lines** | ~45,000 chars |
| **64k** | DeepSeek / Claude / GPT | **2,000 lines** | ~90,000 chars |
| **>= 128k** | High-Capacity Cloud | **4,000 lines** | ~180,000 chars |

* **Zero-Trust Safety (`agent_security.py`):** Privileged mutations (`sudo`, `pacman`, `systemctl`) and out-of-bounds paths strictly require interactive `[y/N]` confirmation regardless of YOLO mode.
* **Surgical Edits (`edit_file`):** 3-stage replacement (Exact -> Whitespace-tolerant -> 88% Fuzzy match).

---

## 6. Memory & Directives

* **Global (`skills/system_instructions.md`):** Always-on rules applied across all workspaces.
* **Workspace (`<workspace>/.agent/memory/*.md`):** Project rules loaded when Memory is `[ON]`.
  * `/mem save <topic>: <rule>` -> Save rule (e.g. `/mem save os: Arch Linux`).
  * `/mem list` -> List active memory files and weights.
  * `/mem` -> Toggle memory injection ON / OFF.
  * `/hs` -> Hindsight audit: extracts session decisions into memory files.

---

## 7. Client Surfaces

* **PyCode Desktop IDE (`/pyc`, `/pyc web`):** ACP stdio JSON-RPC 2.0 with live token streaming and diff review.
* **DeepSeek Harness (`/dsh`):** DSH Web Cockpit bound to the active workspace.
* **llama.cpp WebAgent (`/webui`):** Autonomous tool reverse proxy for `llama-server` (`:8080`).
* **Textual PyTUI (`/tui`):** Full-screen terminal dashboard with real-time thought shimmer.

---

## 8. Sub-Agent Worktree Sandboxing

Opening a secondary terminal in an active Git workspace automatically assigns `[sub-agent #1]` and provisions an isolated Git worktree (`.agent/worktrees/agent-1`).

* **Zero-Blast-Radius:** File writes, command executions, and tests occur strictly on a dedicated branch (`subagent-1`), leaving the main branch pristine.
* **Parallel Workflows:** Multiple terminals can execute independent tasks on the same codebase without file collisions.
* **Teardown & Merge:** Exiting the sub-agent (`q` or `Ctrl+C`) prompts to `Merge` or `Discard`, cleanly deleting the worktree directory and branch.

---

## 9. Skill Frontmatter Schema

Skill profiles (`skills/profiles/**/*.md`) configure agent persona and flags using YAML frontmatter:

```yaml
---
description: "Autonomous software engineer"
category: "Local"          # Optional: Cloud (0) → Local (1) → Roles (2) → Custom (3+)
yolo: true
map: true
memory: true
ipython: true
adapters: true
reasoning_budget: 500
---
```
