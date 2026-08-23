# Py-Agent Workspace & Session Manual

High-speed local developer agent, episodic memory, SQLite checkpoints, NOOA-enhanced IPython kernel harness, and codebase index graph.

```console
~ ❯ sess
[02/03] ❯ [session test 2] ai init ~/session-test-2
:: ↵ run  Esc: 
[ok] Mapping complete! [session-test-2 index-map & SQLite graph database updated]

[ai init] Select default Agent Profile for workspace session-test-2:

Enable Autonomous YOLO mode? [y/N]: y
✓ Profile set to: Pi Py-Pro (Autonomous YOLO)

╭─  ∿ Py Agent  ───────────────────────────────────────────╮
│     model:  gemini-3.5-flash-lite                        │
│ directory:  ~/.config/py-agent/projects/session-test-2   │
│     skill:  pi/py-pro                                    │
│  database:  active (1 facts, 1 turns)                    │
╰───────────────────────────────────────── Ctrl+C to exit ─╯
 Startup context: 743 tokens

Agent: Workspace loaded. Awaiting instructions.
 [ think: 10 | ans: 10 | 20 tokens | 0.07s @ 336.9 t/s ]
 [ 794 in | 10 out | ctx: 9.8% ]
❯ 
```

---

## UI Box Themes

Switch CLI box styles using `/box [1-5]` (or type `/box` to cycle). Selection persists in `~/.config/py-agent/.state.json`.

#### Style #1: Codex Rounded (Default)
```console
╭─  ∿ Py Agent  ────────────────╮
│     model:  gemini-3.7-flash  │
│ directory:  ~                 │
│     skill:  chat              │
│  database:  stateless         │
╰────────────── Ctrl+C to exit ─╯
```

#### Style #2: Double Border
```console
╔═  ∿ Py Agent  ════════════════╗
║     model:  gemini-3.7-flash  ║
║ directory:  ~                 ║
║     skill:  default           ║
║  database:  stateless         ║
╚══════════════ Ctrl+C to exit ─╝
```

#### Style #3: Heavy Square
```console
┏━  ∿ Py Agent  ━━━━━━━━━━━━━━━━┓
┃     model:  gemini-3.7-flash  ┃
┃ directory:  ~                 ┃
┃     skill:  default           ┃
┃  database:  stateless         ┃
┗━━━━━━━━━━━━━━ Ctrl+C to exit ━┛
```

#### Style #4: Minimalist Line
```console
 ─  Py Agent  ──────────────────
      model:  gemini-3.7-flash   
  directory:  ~                  
      skill:  default            
   database:  stateless          
 ────────────── Ctrl+C to exit ─ 
```

#### Style #5: Classic In-Panel Codex
```console
╭───────────────────────────────╮
│  ∿ Py Agent                   │
│                               │
│     model:  gemini-3.7-flash  │
│ directory:  ~                 │
│     skill:  default           │
│  database:  stateless         │
╰────────────── Ctrl+C to exit ─╯
```

---

## 1. Directory Structure

All auto-created agent metadata files are strictly isolated inside `project/.agent/` to keep project workspaces clean.

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

Running `ai init <path>` sets the default workspace agent profile:

```console
[ai init] Select default Agent Profile for workspace session-test:

  ─── Agents ────────────────────────
  ❯  1. Pi Pro               (~280t)
     2. Claude Pro           (~290t)
     3. Hermes Pro           (~280t)

     1. Pi Lite              (~220t)
     2. Claude Lite          (~220t)
     3. Hermes Lite          (~220t)

  ─── Py ────────────────────────────
     1. Pi Py-Pro            (~300t)
     2. Claude Py-Pro        (~310t)
     3. Hermes Py-Pro        (~300t)

  :: ↵ select  ↑/↓ navigate  Tab: YOLO [OFF]  Esc: default
```

#### Profile Tiers

| Tier | Profiles | Model Scale | Overhead | Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Pro** | `pi/pro`, `claude/pro`, `hermes/pro` | Medium/Large Models | `~280t–290t` | Full-scale codebase graph navigation & multi-file editing. |
| **Lite** | `pi/lite`, `claude/lite`, `hermes/lite` | Small/Medium Models | `~220t` | Native JSON tools optimized for zero tool-calling confusion. |
| **Py-Pro** | `pi/py-pro`, `claude/py-pro`, `hermes/py-pro` | Medium/Large Models | `~300t–310t` | NOOA-enhanced IPython kernel harness (`exec_python`) with stateful memory. |

* **Reset Workspace Profile:** Type `/reset` in chat (or delete `.agent/config.json`).
* **Skill Frontmatter Overrides:** Add `---` YAML headers to skill `.md` files to set `reasoning_budget`, `yolo`, or `description` automatically on load.
* **Customize Skills:** Modify or create profile `.md` files in `~/.config/py-agent/skills/profiles/`.

---

## 3. Command Reference

```console
╭─  ⚙ Help & Commands  ───────────────────────────────────────────────╮
│   Shortcuts: Esc: bypass  Ctrl+C: cancel                            │
│                                                                     │
│   Available commands:                                               │
│  /h                          - Help menu                            │
│  /pyc, /pyc web              - Desktop GUI or WebUI                 │
│  /tui                        - Textual TUI                          │
│  /v [auto], /voice           - Voice to text                        │
│  /tts                        - Text out loud                        │
│  /py [code_or_cmd]           - Toggle or execute via IPython        │
│  /box [1-5]                  - Box style preset                     │
│  /task [goal]                - Autonomous task loop                 │
│  /t [N|show|hide]            - Set reasoning budget or show/hide    │
│  /g, /yolo                   - Toggle confirmation gates (YOLO)     │
│  /m                          - Toggle database memory               │
│  /md                         - Toggle Markdown                      │
│  /stats                      - Generation speed stats               │
│  /tok                        - Context token usage                  │
│  /sync                       - Sync index                           │
│  /clear, /c                  - Soft clear active chat history       │
│  /reset, /purge              - Hard reset (.agent & database)       │
│  /sp                         - Spellchecker                         │
│  /s <q>, /s off              - Load or unload on-demand skill       │
│  -save <tag>                 - Save session checkpoint              │
│  -load                       - Load or clone checkpoint             │
│  /f, /tk, /b, /a             - Follow-up, Think, Brainstorm, All    │
│  file <path>                 - Load file into context               │
│  exit, quit, q               - Exit                                 │
╰─────────────────────────────────────────────────────────────────────╯
```

---

## 4. PyCode React Desktop GUI (`/pyc`)

Cross-platform React desktop and WebUI workspace for `py-agent`, powered by a customized fork of [`pingdotgg/t3code`](https://github.com/pingdotgg/t3code). Repo: **[j5onrf/pycode](https://github.com/j5onrf/pycode)**.

* **How It Works:** Connects via Agent Client Protocol (ACP) over stdio JSON-RPC 2.0. Streams thoughts and tokens live, formats reasoning into quote blocks (`> *Thinking...*`), features an optional theme-reactive Gemini ambient aurora glow toggle, and auto-syncs workspace AST maps (`index-map`) and TPM memories (`.agent/tpm.md`).
* **Unified Settings Sync:** PyCode automatically inherits all active CLI toggles (`/tts` audio, `/t` reasoning budgets, `/yolo` confirmation gates, and model endpoints)—configure your environment in terminal, and the GUI adopts it instantly.
* **CLI Suspension:** Typing `/pyc` suspends the terminal session and cleanly resumes upon closing the window.

### Installation
```bash
~/.config/py-agent/plugins/pycode/setup.sh
# (or run: install-pycode)
```

### Launch Modes
| Mode | Command | Description |
| :--- | :--- | :--- |
| **Desktop App** | `/pyc` (or `pycode`) | Cross-platform React Desktop IDE on Wayland/X11 |
| **Web Browser** | `/pyc web` (or `pycode web`) | Browser WebUI on `http://localhost:3773` |

---

## 5. Textual PyTUI Interface (`/tui`)

Full-screen async Textual interface powered by `uvloop` background workers. Launch via `/tui` or run `agent_tui.py`.

* **Plan / Build Modes (`Tab`):** Toggle between **Plan** (confirmation gate per tool action) and **Build** (Autonomous YOLO).
* **Border Toggle (`Ctrl+F`):** Toggle card outline borders ON/OFF.
* **Background Services:** `uvloop` libuv file watching (`.agent/tpm.md`) and Unix domain socket IPC hub (`/tmp/py-agent-<workspace>.sock`) for multi-terminal sub-agent tracking.

---

## 6. IPython Kernel Harness (`/py`) - NOOA-Enhanced

Stateful Python REPL (NVIDIA Object-Oriented Agent architecture) keeping variables, DataFrames, and imports alive in kernel RAM across turns—saving up to 90% context tokens.

- **Toggle / Execution:** `/py` to toggle ON/OFF, or `/py <code_or_cmd>` for instant cell execution.
- **In-Kernel Harness Objects:**
  - `graph` — `.snippet(sym)`, `.trace(sym)`, `.blast_radius(sym)`, `.search(pat)`, `.architecture()`
  - `memory` — `.search(query)`, `.get_facts()`, `.add_fact(key, val)`
  - `preview(obj)` / `bounded_repr(obj)` — Compact previews of DataFrames/lists while keeping live objects in RAM.
  - `delegate("goal")` — Runs an isolated sub-agent in a private sandbox; returns only final summary to kernel variable.
  - `read_file()`, `write_file()`, `list_dir()`, `run_command()` — Native workspace file I/O & shell execution.
- **Zero-Trust Boundary:** Out-of-bounds `open()`, `os.listdir()`, and file I/O targeting paths outside workspace root trigger mandatory authorization gates.

<details>
<summary><b>💡 Top 5 Everyday Real-World Use Cases (Click to Expand)</b></summary>
<br>

1. **Fix a Bug or Add a Feature (Surgical Edits):** Ask in plain English (*"The contact form isn't validating email addresses. Fix it and test it"*). Pinpoints the exact function via graph, writes the fix, and runs tests.
2. **Safety Check Before Changing Anything (Blast Radius):** Ask *"If I change the pricing calculation, what else will break?"*. Runs a `blast_radius` check across all connected files.
3. **Understand How Your App Works:** Ask *"Explain in plain English how user login works in this project"*. Extracts only the login function from the graph without dumping whole files.
4. **Process Big Log Files or Datasets:** Ask *"I have a 20,000-line error log. Tell me why my app crashed today"*. Opens in RAM, filters lines, and summaries without context bloat.
5. **Build a Full Feature Start-to-Finish (`/task`):** Type `/task "Create a user profile page with avatar upload button and tests"`. Loops until 100% verified complete.

</details>

---

## 7. Autonomous Task Loops (Ralph Engine)

Self-directed iterative loop that runs tools, verifies results, and self-corrects until a task is complete.

- **Inline Execution:** `/task "Create a module string_utils.py with tests and run unittest"`
- **Spec File Mode:** Create `TASK.md` in project root and run `/task`
- **Dual Completion Detection:** Checks assistant text **and** tool execution logs (`exec_python`, `run_command`) for `TASK COMPLETE`.
- **Stagnation Recovery:** Detects duplicate turns and injects course-correction prompts.
- **Audit Logging:** Logs goal progress into `.agent/task_log.md`.
- **Engine Script:** `~/.config/py-agent/tools/loop/ralph.py` (Flags: `-n` / `--turns`, `-f` / `--file`, `--no-log`).

---

## 8. Checkpoints & Save States

- **Save:** `-save <tag>` — Snapshot session state to SQLite.
- **Load:** `-load` — Restore or clone session checkpoint across workspaces.

---

## 9. Local RAG, Skills & Context Injection

- **Whole File:** `file <path>` — Append entire file into context.
- **Targeted Symbol:** `read_symbol("<symbol>")` — Inject specific AST function/class snippet from index graph (saves 95% tokens).
- **On-Demand Skills (`/s <skill>`):** Inject specialty prompts (`/s pirate`, `/s caveman`, `/s reviewer`) on the fly.
  - **Multi-Skill Stacking:** Stack up to 3 active on-demand skills simultaneously.
  - **Category Auto-Swap:** Loading a new skill of the same category (e.g. `personality/`) automatically replaces the old skill.
  - **Unload Skills (`/s off`):** Type `/s off` (or `/s clear` / `/s reset`) to revert to base profile skill.

---

## 10. Codebase Graph Mapper

- **Agent Mode (`ai init` / `/sync`):** Outputs map files directly to `project/.agent/` to keep source trees clean.
- **Standalone CLI Mode (`index-map`):** Outputs map files to project root when run independently in shell.
- **AST Graph:** Maps classes, methods, call-chains, and inheritance across Python, Rust, Go, JS/TS, C/C++, Lua.
- **Vector Search:** Embeds codeblocks into `sqlite-vec` virtual tables for semantic retrieval.

---

## 11. Temporal Personality Memory (TPM)

- **Async Fact Extraction:** Auto-extracts user preferences in background thread after each turn.
- **Strict Fact Filtering:** Key blacklisting prevents project code from contaminating user memory.
- **Context Injection:** Compiles and injects facts into model `<context>` blocks every turn.
- **Human-Editable Sync:** Reconciles manual edits in `.agent/tpm.md` into SQLite on startup.

---

## 12. Sub-Agents & Concurrency

### 1. In-Kernel Programmatic Sub-Agents (`delegate("goal")`)
* **Context Token Protection:** Sub-agent runs tools in an isolated sandbox and returns **only the final summary report** to your kernel variable.

### 2. Multi-Terminal Parallel Sub-Agents (`ai init`)
* **Process Badges:** Sequence IDs (`[sub-agent #1]`, `[sub-agent #2]`) when launching `ai init` in parallel terminals.
* **Self-Healing Registry:** Auto-purges stale PID lockfiles (`.active_sessions/`) on exit or crash.
* **SQLite Lock Protection:** `PRAGMA busy_timeout = 30000` + `WAL` mode eliminates database locks.
* **Unix Socket IPC:** Async socket hub (`/tmp/py-agent-<workspace>.sock`) for live status broadcasting.

---

## 13. Skill Profile Frontmatter Overrides (`---`)

YAML (`---`) or JSON (`{...}`) frontmatter headers override runtime settings automatically on load (`ai init` or `/s <skill>`).

```markdown
---
reasoning_budget: 750
yolo: true
description: "Expert Python refactoring agent with high reasoning budget"
---
# [SKILL] Python Refactoring ---> python-refactor
Act as a senior staff engineer...
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `reasoning_budget` | Integer | Deep reasoning token budget (e.g. `750` or `0`). |
| `yolo` | Boolean | Autonomous mode (`true` disables gates, `false` enables). |
| `description` | String | Skill summary description shown in menus. |

---

## 14. Security & Execution Isolation

- **Read-Only Default:** Workspace edits require explicit `ai init` enablement.
- **Directory Lock:** Enforces confirmation gates for paths outside project root.
- **Visual Diffs:** Shows colorized diffs prior to file writes.
- **Kernel Zero-Trust Overrides:** In IPython mode, built-ins (`open`, `os.listdir`) are guarded against out-of-bounds file access.

---

## 15. Reasonix Cognitive Engine (`/t`)

- **Set Token Budget:** `/t <N>` — Set thinking token budget (e.g. `/t 500` or `/t 0` to disable).
- **Show / Hide Thinking:** `/t show` or `/t hide` — Toggle real-time thinking display.
- **Quick Toggle:** `/t` — Toggle deep reasoning mode ON/OFF.

---

## 16. Voice Bridge & Neural Audio (`/v` & `/tts`)

- **Voice to Text (`/v` / `/v auto`):** Zero-latency HTTPS bridge (`:9999`) for mobile/tablet dictation using Gemini cloud transcription. Emits native Wayland virtual keypresses (`wtype`) directly into PyCode desktop, browser WebUI, or active terminal prompts.
- **Neural TTS (`/tts`):** Reads responses aloud via PipeWire & Kokoro; auto-filters code and `<think>` blocks.
- **Stop Speech:** Run `pkill -9 -f "pw-play|koko"`, type `stop talking`, or bind `Super+Shift+X`.

---

## 17. Environment Variables & Context Limits

Override max context token limits or model defaults:
```bash
AI_MAX_TOKENS=16000 ai init ~/my-project
```
