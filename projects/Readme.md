# Py-Agent Workspace & Session Manual

local developer agent, episodic memory, SQLite checkpoints, NOOA-enhanced IPython kernel harness, and codebase index graph.

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

All auto-created agent metadata files are strictly isolated inside `project/.agent/` to keep project workspaces completely clean.

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
| **Pro** | `pi/pro`, `claude/pro`, `hermes/pro` | Medium/Large Models | `~280t–290t` | Full-scale codebase graph navigation, surgical edits (`edit_file`), and multi-file workflows. |
| **Lite** | `pi/lite`, `claude/lite`, `hermes/lite` | Small/Medium Models | `~220t` | Native JSON tools (`read_file`, `edit_file`, `write_file`) optimized for zero tool-calling confusion. |
| **Py-Pro** | `pi/py-pro`, `claude/py-pro`, `hermes/py-pro` | Medium/Large Models | `~300t–310t` | NOOA-enhanced IPython kernel harness (`exec_python`) with stateful memory and surgical edit SDK. |

* **Reset Workspace Profile:** Type `/reset` in chat (or delete `.agent/config.json`). This purges workspace settings so `ai init` prompts for a new profile selection on next launch.
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
│  /webui, /web                - llama.cpp WebAgent gateway           │
│  /tui                        - Textual TUI                          │
│  /v [auto], /voice           - Voice to text                        │
│  /tts                        - Text out loud                        │
│  /py [code_or_cmd]           - Toggle or execute via IPython        │
│  /box [1-5]                  - Box style preset                     │
│  /task [goal]                - Autonomous task loop                 │
│  /t [N|show|hide]            - Set reasoning budget or show/hide    │
│  /g, /yolo                   - Toggle confirmation gates (YOLO)     │
│  /m                          - Toggle database memory & TPM facts   │
│  /stats                      - Generation speed stats               │
│  /tok                        - Context token usage                  │
│  /sync                       - Sync index                           │
│  /clear, /c                  - Soft clear active chat history       │
│  /reset, /purge              - Hard reset (.agent & database)       │
│  /s <q>, /s off              - Load or unload on-demand skill       │
│  -save <tag>                 - Save session checkpoint              │
│  -load                       - Load or clone checkpoint             │
│  /f, /tk, /b, /a             - Follow-up, Think, Brainstorm, All    │
│  file <path>                 - Load file into context               │
│  exit, quit, q               - Exit                                 │
╰─────────────────────────────────────────────────────────────────────╯
```

---

## 4. PyCode React Desktop IDE (`/pyc`)

Cross-platform React desktop and WebUI workspace for `py-agent`, powered by a customized fork of [`pingdotgg/t3code`](https://github.com/pingdotgg/t3code). Repo: **[j5onrf/pycode](https://github.com/j5onrf/pycode)**.

* **How It Works:** Connects via Agent Client Protocol (ACP) over stdio JSON-RPC 2.0. Streams thoughts and tokens live, formats reasoning into quote blocks (`> *Thinking...*`), features an optional theme-reactive Gemini ambient aurora glow toggle, and auto-syncs workspace AST maps (`index-map`) and TPM memories (`.agent/tpm.md`).
* **Unified Settings Sync:** PyCode automatically inherits all active CLI toggles (`/tts` audio, `/t` reasoning budgets, `/yolo` confirmation gates, and model endpoints)—configure your environment in terminal, and the GUI adopts it instantly.
* **Instant Stop Cancellation:** Clicking the Stop button in PyCode immediately terminates generation and cleans up active sockets.
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

## 5. llama.cpp WebAgent Gateway (`/webui`)

Autonomous tool-execution streaming reverse proxy for the official `llama.cpp` WebUI. Launch via `/webui` (or `/web`).

* **How It Works:** Spawns a lightweight Python proxy (`server.py`) on port 3000 that wraps `llama-server` (`http://127.0.0.1:8080`). It intercepts `/v1/chat/completions` to inject active workspace skill profiles, shorthand codebase index maps (`.agent/index-map-*.txt`), and multi-round agent tool calls (`read_file`, `edit_file`, `write_file`, `run_command`, AST graph tools) directly into the web chat stream.
* **0s Prefix KV Cache Reuse:** Uses byte-identical prompt formatting aligned with the CLI engine for sub-100ms time-to-first-token.
* **Native Metrics & Timings:** Preserves 100% of official `llama.cpp` web frontend features—including live TPS speed metrics, token timing badges, sampler controls, and gzip decompression.
* **CLI Suspension:** Typing `/webui` suspends the terminal session, launches the proxy, opens `http://127.0.0.1:3000` via `xdg-open`, and cleanly resumes the terminal session upon exit.

---

## 6. Textual PyTUI Interface (`/tui`)

Full-screen async Textual interface powered by `uvloop` background workers. Launch via `/tui` or run `agent_tui.py`.

* **Plan / Build Modes (`Tab`):** Toggle between **Plan** (confirmation gate per tool action) and **Build** (Autonomous YOLO).
* **Border Toggle (`Ctrl+F`):** Toggle card outline borders ON/OFF instantly.
* **Background Services:** `uvloop` libuv file watching (`.agent/tpm.md`) and Unix domain socket IPC hub (`/tmp/py-agent-<workspace>.sock`) for multi-terminal sub-agent tracking.

---

## 7. IPython Kernel Harness (`/py`) - NOOA-Enhanced

Stateful Python REPL (NVIDIA Object-Oriented Agent architecture) keeping variables, DataFrames, and imports alive in kernel RAM across turns—saving up to 90% context tokens.

- **Toggle / Execution:** `/py` to toggle ON/OFF, or `/py <code_or_cmd>` for instant cell execution.
- **In-Kernel Harness Objects:**
  - `graph` — `.snippet(sym)`, `.trace(sym)`, `.blast_radius(sym)`, `.search(pat)`, `.architecture()`
  - `memory` — `.search(query)`, `.get_facts()`, `.add_fact(key, val)`
  - `preview(obj)` / `bounded_repr(obj)` — Compact previews of DataFrames/lists while keeping live objects in RAM.
  - `delegate("goal")` — Runs an isolated sub-agent in a private sandbox; returns only final summary to kernel variable.
  - `read_file()`, `edit_file()`, `write_file()`, `list_dir()`, `run_command()` — Native workspace file I/O & shell execution.
- **Zero-Trust Boundary:** Out-of-bounds `open()`, `os.listdir()`, and file I/O targeting paths outside workspace root trigger mandatory authorization gates.

<details>
<summary><b>💡 Top 5 Everyday Real-World Use Cases (Click to Expand)</b></summary>
<br>

1. **Fix a Bug or Add a Feature (Surgical Edits):** Ask in plain English (*"The contact form isn't validating email addresses. Fix it and test it"*). The agent uses the graph engine to pinpoint the exact file, reads only that function, writes the fix, and runs tests to prove it works.
2. **Safety Check Before Changing Anything (Blast Radius):** Ask *"If I change the pricing calculation, what else will break?"*. The agent runs a `blast_radius` check across all connected files and alerts you before making changes.
3. **Understand How Your App Works (Plain English Explanations):** Ask *"Explain in plain English how user login works in this project"*. The agent extracts *only* the login function from the graph and explains it simply without dumping 500 lines of code.
4. **Process Big Log Files or Datasets (Zero Context Bloat):** Ask *"I have a 20,000-line error log. Tell me why my app crashed today"*. In `/py` mode, it opens the file in background RAM, filters out normal lines, and gives a 3-bullet summary without lagging your session.
5. **Build a Full Feature Start-to-Finish (`/task`):** Type `/task "Create a user profile page with an avatar upload button and tests"`. The agent enters a self-directed loop, creates files, writes code, executes tests, self-corrects if tests fail, and notifies you when 100% complete.

</details>

---

## 8. Autonomous Task Loops (Ralph Engine)

Self-directed iterative loop that runs tools, verifies results, and self-corrects until a task is complete.

- **Inline Execution:** `/task "Create a module string_utils.py with tests and run unittest"`
- **Spec File Mode:** Create `TASK.md` in project root and run `/task`
- **Surgical Code Modifications:** Utilizes `edit_file` for targeted line changes without rewriting entire files.
- **Context Compaction Watchdog:** Auto-prunes older tool responses if context exceeds 80% to ensure long multi-turn tasks complete without context overflow.
- **Dual Completion Detection:** Checks both assistant text responses **and** tool execution logs (`exec_python`, `run_command`, etc.) for completion markers (`TASK COMPLETE`).
- **Stagnation Recovery:** Automatically detects duplicate turns and injects course-correction prompts.
- **Audit Logging:** Logs turn-by-turn goal progress into `.agent/task_log.md`.
- **Engine Script:** `~/.config/py-agent/tools/loop/ralph.py` (Supports flags `-n` / `--turns`, `-f` / `--file`, `--no-log`, `--plan-model`).

<details>
<summary><b>💡 Quick Use Cases & Tips (Click to Expand)</b></summary>
<br>

* **Hands-Off Feature Development:** Give a high-level goal like `/task "Refactor string_utils.py to handle Unicode text and run test suite"`. The loop runs continuously until all tests pass.
* **Spec-Driven Refactoring (`TASK.md`):** Write a checklist of 5 features in `TASK.md`, run `/task`, and let the agent check off items one by one autonomously.

</details>

---

## 9. Checkpoints & Save States

- **Save:** `-save <tag>` — Snapshot session state to SQLite.
- **Load:** `-load` — Restore or clone session checkpoint across workspaces.

---

## 10. Local RAG, Skills & Context Injection

- **Whole File:** `file <path>` — Append entire file into context.
- **Targeted Symbol:** `read_symbol("<symbol>")` — Inject specific AST function/class snippet from index graph (saves 95% tokens).
- **On-Demand Skills (`/s <skill>`):** Inject specialized specialty prompts (`/s pirate`, `/s caveman`, `/s reviewer`) on the fly into active chat sessions.
  - **Multi-Skill Stacking:** Stack up to 3 active on-demand skills simultaneously.
  - **Category Auto-Swap:** Loading a new skill of the same category (e.g. `personality/`) automatically replaces the old skill to prevent persona collisions.
  - **Unload Skills (`/s off`):** Type `/s off` (or `/s clear` / `/s reset`) to remove all on-demand skills and revert to your base profile skill.

<details>
<summary><b>💡 Quick Tips for Skills (Click to Expand)</b></summary>
<br>

* **Quick Persona Swap:** Type `/s caveman` to switch to token-slashing caveman mode. Type `/s pirate` to swap directly to pirate mode.
* **Stack Specialty Skills:** Type `/s pirate reviewer` to combine pirate persona with code reviewer instructions!
* **Reset to Default:** Type `/s off` anytime to clear on-demand skills and return to your base workspace profile.

</details>

---

## 11. Codebase Graph Mapper

The codebase intelligence engine features **dual-mode output routing**:

- **Agent Mode (`ai init` / `/sync`):** Outputs map files directly to `project/.agent/` to keep source directories clean.
- **Standalone CLI Mode (`index-map`):** Outputs map files to the project root directory when run independently in shell.
- **AST Graph:** Maps classes, methods, call-chains, and class inheritance across Python, Rust, Go, JS/TS, C/C++, Lua.
- **Vector Search:** Embeds codeblocks into `sqlite-vec` virtual tables for semantic retrieval.

<details>
<summary><b>💡 Quick Use Cases & Tips (Click to Expand)</b></summary>
<br>

* **Instant Codebase Orientation:** Run `index-map architecture` or ask *"Give me an architecture overview"* to map all files, classes, and call counts instantly.
* **Surgical Code Inspection:** Instead of reading 500-line files, ask *"Show me snippet for PhysicsEngine.compute_trajectory"* to load only the 15 lines you need.

</details>

---

## 12. Temporal Personality Memory (TPM)

- **Async Fact Extraction:** Auto-extracts user preferences in background thread after each turn.
- **Strict Fact Filtering:** Key blacklisting prevents project files/code from contaminating user memory.
- **Context Injection:** Compiles and injects facts into model `<context>` blocks every turn.
- **Human-Editable Sync:** Reconciles manual edits in `.agent/tpm.md` into SQLite on startup.

<details>
<summary><b>💡 Quick Use Cases & Tips (Click to Expand)</b></summary>
<br>

* **Persistent Habits:** Tell the AI *"I prefer type-annotated Python and pytest over unittest"*. The AI saves this preference to `.agent/tpm.md` and respects it across all future sessions.
* **Direct Manual Editing:** Edit `.agent/tpm.md` directly in your text editor—the agent syncs your manual edits on next startup.

</details>

---

## 13. Sub-Agents & Concurrency

The Py Agent framework provides **dual-mode sub-agent execution**:

### 1. In-Kernel Programmatic Sub-Agents (`delegate("goal")`)
* **Context Token Protection:** The sub-agent runs tool operations inside an isolated private sandbox memory. All intermediate investigation logs are discarded, returning **only the final summary report** to your kernel variable.
* **Speed:** Sub-agent tasks complete in 1–2 seconds with 0 context token bloat.

### 2. Multi-Terminal Parallel Sub-Agents (`ai init`)
* **Process Badges:** Assigns sequence IDs (`[sub-agent #1]`, `[sub-agent #2]`) when launching `ai init` in parallel terminals.
* **Self-Healing Registry:** Auto-purges stale PID lockfiles (`.active_sessions/`) on exit or crash.
* **SQLite Lock Protection:** `PRAGMA busy_timeout = 30000` + `WAL` mode eliminates multi-agent database locks.
* **Unix Socket IPC:** Async socket hub (`/tmp/py-agent-<workspace>.sock`) parses JSON-RPC 2.0 status messages for live TUI notifications.

<details>
<summary><b>💡 Quick Use Cases & Tips (Click to Expand)</b></summary>
<br>

* **Context-Free Heavy Auditing:** Use `delegate("Audit string_utils.py for edge cases")` to let a sub-agent perform 10 background file reads and test runs without filling your main chat history.
* **Multi-Terminal Workflow:** Open 3 terminal tabs running `ai init ~/my-project` to work on 3 features simultaneously (`[sub-agent #1]`, `[sub-agent #2]`, `[sub-agent #3]`).

</details>

---

## 14. Skill Profile Frontmatter Overrides (`---`)

Skill profiles support **YAML (`---`) or JSON (`{...}`) frontmatter headers** to override runtime settings automatically on load (`ai init` or `/s <skill>`).

#### Frontmatter Syntax Example (`my-skill.md`):

```markdown
---
reasoning_budget: 750
yolo: true
description: "Expert Python refactoring agent with high reasoning budget"
---
# [SKILL] Python Refactoring ---> python-refactor
Act as a senior staff engineer...
```

#### Supported Frontmatter Keys:

| Key | Type | Description |
| :--- | :--- | :--- |
| `reasoning_budget` | Integer | Deep reasoning token budget (e.g. `750` or `0`). |
| `yolo` | Boolean | Autonomous mode (`true` disables gates, `false` enables). |
| `description` | String | Skill summary description shown in TUI menu. |

---

## 15. Security & Execution Isolation

- **Read-Only Default:** Workspace edits require explicit `ai init` enablement.
- **Directory Lock:** Enforces confirmation gates for paths outside project root.
- **Visual Diffs:** Shows colorized diffs prior to file writes.
- **Kernel Zero-Trust Overrides:** In IPython mode, built-ins (`open`, `os.listdir`) are guarded against out-of-bounds file access.

---

## 16. Reasonix Cognitive Engine (`/t`)

Real-time reasoning trace step extraction and cognitive phase formatting inside the live thinking stream.

- **Set Token Budget:** `/t <N>` — Set thinking token budget (e.g. `/t 500` or `/t 0` to disable thinking).
- **Show / Hide Thinking:** `/t show` or `/t hide` — Toggle real-time thinking panel visibility while reasoning mode stays active.
- **Quick Toggle:** `/t` — Toggle deep reasoning mode ON/OFF.

---

## 17. Voice Bridge & Neural Audio (`/v` & `/tts`)

- **Voice to Text (`/v` / `/v auto`):** HTTPS bridge (`:9999`) for mobile/tablet dictation. Use `/v` for prompt review, `/v auto` for auto-submit.
- **Neural TTS (`/tts`):** Reads responses aloud via PipeWire & Kokoro; auto-filters code and `<think>` blocks.
- **Stop Speech:** Run `pkill -9 -f "pw-play|koko"`, type `stop talking`, or bind `Super+Shift+X`.

---

## 18. Environment Variables & Context Limits

Override max context token limits or model defaults:
```bash
AI_MAX_TOKENS=16000 ai init ~/my-project
```
