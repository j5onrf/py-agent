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
     1. Custom Base          (~370t)
     2. Custom Deepseek      (~431t)
     3. Custom Gemini        (~398t)
     4. Custom Lfm2          (~361t)
  ❯  5. Custom Lingtiny      (~395t)
     6. Custom Minicpm       (~431t)
     7. Custom Q2B           (~365t)
     8. Custom Sysadmin      (~442t)

  ─── Agents ────────────────────────
     1. Pi Pro               (~378t)
     2. Claude Pro           (~425t)
     3. Hermes Pro           (~423t)

    Tools: python + native (7 tools, ~760t)

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

## 4. Tooling & Safety

### 4.1 Operational Tiers & Token Footprint
* **Pure Chat (`ai`):** **211 tokens** (ultra-minimal, zero tools).
* **Native Mode (`Py: OFF`):** **6 tools (`SMOL_TOOLS`)**, ~680t schema.
* **Dual Mode (`Py: ON`):** **7 tools (`python + native`)**, ~760t schema with ~95% KV cache hits.
* **OKF Memory:** `.agent/memory/*.md` with 1-shot `/hs` retrospective audits.

### 4.2 Guardrails & Execution
* **Zero-Trust Safety Gate:** System mutations (`sudo`, `pacman`, `systemctl`) and out-of-bounds file access always require explicit `[y/N]` confirmation—even in YOLO mode.
* **Surgical File Edits (`edit_file`):** 3-stage replacement (Exact $\to$ Whitespace-tolerant $\to$ 88% Fuzzy match).
* **Adaptive Reads (`read_file`):** Automatically switches to an AST structural outline when files exceed your active context ceiling (250 to 4,000 lines).

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

## 8. Sub-27B Model Tips (Ling, Qwen-2B, MiniCPM)

* **Scope to Single Tasks:** Keep prompts focused on 1 file or 1 objective per turn for maximum accuracy.
* **Use Native Tools (`Py: OFF`):** Small models are fastest and most reliable with the 6 native tools (`SMOL_TOOLS`), avoiding raw Python scripting loops.

### 8.1 Adapter Performance Impact (`eval-stack`)

Empirical results across small quantized models (Sub-27B):

| Benchmark Challenge | Without Adapters | With `/adp` Active | Efficiency Gain |
| :--- | :---: | :---: | :--- |
| **AG-03 (Surgical Edit & Test)** | 16 turns | **6 turns** | **62% fewer turns** (eliminates diff-retry loops) |
| **AG-07 (In-Memory Batch Loop)** | 14 turns | **2 turns** | **85% fewer turns** (executes batch script on Turn 1) |
| **Full Suite Pass Rate** | Fragile / Retries | **100% (7/7)** | **Zero unhandled syntax or format failures** |

* **Why it matters:** Sub-27B models often emit malformed JSON, markdown code blocks, or broken import syntax. `/adp` heals these out-of-band, preventing wasted multi-turn recovery cycles and preserving active context window space on any hardware.

---

## 9. Technical Reference: Lineage, Foundations & Extended Capabilities

A comprehensive map of all upstream foundations, architectural roots, and secondary services integrated into `py-agent`:

### 9.1 Architectural Foundations & Upstream Roots

| System | Upstream Roots & Inspiration | Purpose & Architecture |
| :--- | :--- | :--- |
| **Codebase Graph** | [Graphify](https://github.com/Graphify-Labs/graphify) + [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Standard-library Python AST parsing (`ast.NodeVisitor`) coupled with SQLite `fts5` virtual table indexing for sub-millisecond symbol queries (`index-map`). |
| **Task Loop Engine** | [Ralph Wiggum](https://github.com/ghuntley/how-to-ralph-wiggum) | Self-directed task loop (`ralph.py`) that reads specifications (`TASK.md`), decomposes execution steps, and retries on failure states until pass verification. |
| **Kernel Harness** | [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent) + [NVIDIA NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents) | Stateful in-memory IPython REPL with bounded object representations (`preview()`), 30s `SIGALRM` execution alarm, and model-callable `memory`/`graph` APIs (`/py`). |
| **Code-First Batching** | [Hugging Face smolagents](https://github.com/huggingface/smolagents) | Enables models to execute multi-file batch loops in Python RAM and conclude with a clean `final_answer(data)` completion signal. |
| **Surgical File Edits** | [SmallCoder](https://github.com/Doorman11991/smallcode) | 3-stage resilient replacement (`edit_file`) tolerant of whitespace/indentation variances, with overwrite protection on `write_file`. |
| **Context Compaction** | [Pi Coding Agent](https://pi.dev) | 3-zone context compactor (`prune_history`) that condenses middle turns while preserving completed milestone anchors and modified file tracking. |
| **Cognitive Stepping** | [Reasonix](https://github.com/esengine/deepseek-reasonix) | Real-time cognitive transition extraction and streaming step badges inside thinking traces (`/t`). |
| **Multi-Agent State** | [Vercel Eve](https://github.com/vercel/eve) + [herdr](https://github.com/ogulcancelik/herdr) | Process-isolated sub-agent PID lockfile tracking with checkpoint rollback (`-save` / `-load`) and in-kernel `delegate()` sandboxing. |
| **Adapter Healing** | [Unsloth AI](https://github.com/unslothai/unsloth) | Self-healing tool format adapters (`agent_adapters.py`) resolving Hermes XML, DSML, Mistral, and raw planning JSON out-of-band for ≤27B models (`/adp`). |

### 9.2 Auxiliary Subsystems & Services

* **Live Web Grounding (`/gnd`):** Dual-mode factual web search using the official Gemini Grounding Search tool with automatic keyless DuckDuckGo fallback across CLI, TUI, and Web surfaces.
* **Multimodal Vision OCR (`describe_image_gemini`):** Cloud pre-processor utilizing Gemini Flash Lite vision to transcribe images, diagrams, error screenshots, and UI mockups into structured text descriptions for text-only local models.
* **Low-Latency Voice Bridge (`/v [auto]`):** Standalone HTTPS server on port `9999` with Gemini speech-to-text and Wayland virtual typing (`wtype --`) directly into the CLI or PyCode editor.
* **Local Kokoro Audio (`/tts`):** Zero-lag neural text-to-speech reader using local `koko` via PipeWire (`pw-play`), automatically filtering code blocks and thinking traces.
* **System Administration Suite:** Integrated diagnostics in `tools/agentic/system/` including real-time hardware inspection (`system-health`), automated log triage (`log-checker`), AUR package auditing (`aur-audit`), and dynamic security auditing (`security-audit`).
