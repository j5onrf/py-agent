<div align="center">
  <img alt="py-agent" src="logo.svg" height="130" />
</div>

<h1 align="center">Py Agent <img src="https://shieldcn.dev/badge/version-v0.9.9.09.svg?variant=secondary" alt="Version"><a href="https://github.com/j5onrf/py-agent"></a></h1>

<p align="center">
  <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/github/last-commit/j5onrf/py-agent.svg?color=emerald&variant=secondary" alt="Last Commit"></a>
  <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/Python.svg?variant=branded&brand=python" alt="Language"></a>
  <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/C%2B%2B.svg?variant=branded&brand=cplusplus"></a>
  <a href="https://github.com/j5onrf/py-agent/blob/main/LICENSE"><img src="https://shieldcn.dev/badge/license-MIT-green.svg" alt="License"></a>
  <a href="https://shieldcn.dev/badge/status-beta-blue.svg"><img src="https://shieldcn.dev/badge/status-beta-blue.svg" alt="Status"></a>
</p>

<p align="center">
  <code>gpt</code> &nbsp; <code>claude</code> &nbsp; <code>grok</code> &nbsp; <code>gemini</code> &nbsp; <code>openrouter</code> &nbsp; <code>hf</code> &nbsp; <code>gguf</code>
</p>

---

<h2 align="center">Overview & Execution Modes</h2>

Lightweight Python orchestration (`rich` + `requests` + `sqlite-vec` + `uvloop`) controlling a C++ backend `llama-server`. Built for extreme efficiency on fine-tuned quantized local models (`Qwen3.5-2B+` for instant chat, `Qwen3.6-35B-A3B` / `Qwen3.8-27B` for developer agents) and cloud providers—supporting both **universal native JSON tool calling** and an advanced **stateful IPython kernel execution harness (`/py`)** for in-memory Python actions.

🟢 **Active:** Official `Hugging Face` Router endpoints ([`Qwen/Qwen3.8-27B`](https://huggingface.co/Qwen/Qwen3.8-27B), [`moonshotai/Kimi-K3`](https://huggingface.co/moonshotai/Kimi-K3), [`zai-org/GLM-5.3-Flash`](https://huggingface.co/zai-org/GLM-5.3-Flash), [`DeepSeek-V4-Flash-0731`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731), [`Qwen/Qwen3.8-2.4T-A95B`](https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B)).
> 💡 *Use `model select` to auto-configure free community HF Spaces.*

- **Direct Shell Jaccard (`<plugins>`):** Sub-millisecond fuzzy intent routing for shell shortcuts, diagnostic tools, and custom plugins mapped in [`ai-context.md`](ai-context.md).
- **Single-Turn Query (`ai <query>`):** Instant response piped straight back to your active shell prompt.
- **Multi-Turn Chat (`ai`):** Persistent interactive terminal session with memory context.
- **Workspace Agent (`ai init <path>`):** Full codebase graph indexing, path-healing file editing, and sub-agent concurrency.
- **Native GUI IDE (`/pyc`):** Cross-platform React desktop & browser development workspace powered by [PyCode](https://github.com/j5onrf/pycode).
- **llama.cpp WebAgent (`/webui`):** Autonomous tool-enabled web gateway on top of official `llama-server` UI (`http://127.0.0.1:3000`) with auxiliary Gemini vision pre-processing for text-only local models.

---

<h2 align="center">Key Systems & Integrations</h2>

| Feature System | Foundation & Architectural Roots | Interface Command / Link |
| :--- | :--- | :--- |
| **PyCode Native Desktop IDE** | Customized [T3 Code](https://github.com/pingdotgg/t3code) fork connected via native Agent Client Protocol (ACP) over stdio JSON-RPC 2.0 with live token & thought streaming. | `/pyc` (or `/pyc web`) |
| **Temporal Personality Memory (TPM)** | Reconciles personal identity & workspace habits using [Weaviate Engram](https://github.com/weaviate/engram-python-sdk) concepts + [Noema](https://github.com/Fail-Safe/Noema) Markdown files. | `.agent/tpm.md` |
| **Codebase Graph & Relational Index** | Structural codebase maps ([Graphify](https://github.com/Graphify-Labs/graphify)) + relational queries ([codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)) + [sqlite-vec](https://github.com/asg017/sqlite-vec) vector RAG with class inheritance graph mapping. | `index-map <dir>` |
| **Ralph Autonomous Task Loop** | Self-directed iteration loop ([Ralph Wiggum](https://github.com/ghuntley/how-to-ralph-wiggum)) executing tasks against project specs (`TASK.md`) until verified complete. | `/task [goal]` |
| **NOOA IPython Kernel Harness** | NVIDIA Object-Oriented Agent ([NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents) + [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent)) stateful Python kernel with pass-by-reference bounded previews (`preview()`), model-callable `memory`/`graph` APIs, and in-kernel `delegate()` sub-agents. | `/py` |
| **Surgical Editing & Scaffold-Fit** | Surgical line replacement (`edit_file`) + overwrite protection (`write_file`) + read-before-edit invariants inspired by [little-coder](https://github.com/itayinbarr/little-coder) and [Aider](https://github.com/paul-gauthier/aider). | `edit_file <path>` |
| **3-Zone Context Compactor** | Token preservation architecture inspired by Mario Zechner's [Pi Coding Agent](https://pi.dev)—compacts intermediate tool turns while preserving anchor prompts and active working memory. | `/compact` (or `/com`) |
| **DeepSeek Session Audit & IPC** | Structured JSONL session event logs + JSON-RPC 2.0 socket IPC + YAML skill frontmatter overlays inspired by [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness). | `.agent/session.jsonl` |
| **Reasonix Cognitive Engine** | Real-time reasoning trace step extraction ([Reasonix](https://github.com/esengine/deepseek-reasonix)) + cognitive phase formatting inside thinking stream. | `/t [N\|show\|hide]` |
| **System Admin & Diagnostics** | Live health monitoring, AUR/security audits, system optimization, status routing, and git commit hooks. | [`tools/agentic/system/`](tools/agentic/system) |
| **Model Select TUI** | Real-time **[Cloud Connection](modules/Readme.md)** TUI, key toggles, and endpoint selector. | `model select` |
| **Interactive Textual PyTUI** | Full-screen **[Textual](modules/Readme.md)** TUI workspace with JSON-RPC 2.0 sub-agent socket IPC powered by a C-speed `uvloop` event loop. | `/tui` |
| **llama.cpp WebAgent Gateway** | Full autonomous agent tool execution (`list_dir`, `write_file`, AST graph) + Gemini multimodal vision for text-only local models. | `/webui` |

---

<h2 align="center">Core Capabilities</h2>

| Core Module | Capability | Description |
| :--- | :--- | :--- |
| **Engine** | **Zero-Daemon** | 0% idle CPU/RAM usage. Native Python standard-library execution. |
| **Providers** | **Active Provider** | Direct `.env` configuration: Custom Endpoints / HF, Gemini, OpenRouter, OpenAI, Claude, Grok, or Local GGUF. |
| **Multi-Agent** | **Subagents** | [Vercel Eve](https://github.com/vercel/eve)-style sub-agents with [herdr](https://github.com/ogulcancelik/herdr) multiplexing (`-save`/`-load`) + in-kernel `delegate("goal")` sub-loops. |
| **Safety** | **Zero-Trust Gates** | Mandatory approval prompts for commands and out-of-bounds file access. |
| **Integrity** | **Type-Safe & AST Guard** | [Pydantic AI](https://github.com/pydantic/pydantic-ai) schemas + [OpenAI Agents](https://github.com/openai/openai-agents-python)-style self-correcting `.py`/`.json` file writes. |
| **Resilience** | **Self-Healing Tool Calls** | [Unsloth](https://github.com/unslothai/unsloth)-inspired heuristic parser fixing malformed JSON/XML arguments on the fly before tool execution. |
| **Optimization** | **Token-Slasher** | Custom [`tools/`](tools/) and [`skills/`](skills/) integration built for minimal token consumption. |
| **Grounding** | **Web Search Engine** | Real-time factual search retrieval (`/gnd`) with Gemini Grounding and DuckDuckGo safety fallback in CLI, TUI & WEB/PYC. |
| **Voice-to-Text** | **Tablet/Phone Bridge** | Zero-latency HTTPS voice bridge with Gemini cloud transcription and native Wayland virtual typing (`wtype`) directly into PyCode IDE and CLI (`/v [auto]`). |
| **Text-to-Speech** | **Neural Kokoro TTS** | Local PipeWire audio reader (`/tts`) using `koko` with silent code block and thinking tag filtering. |

---

<h2 align="center">CLI Launch Interface</h2>

> Customize box themes with `/box [1-5]`. For detailed multi-agent workflows, read the [**Workspace Manual**](projects/Readme.md).

#### 1. Interactive Multi-Turn Chat (`ai`)
    
```console
~ ❯ ai
╭─  ∿ Py Agent  ────────────────────╮
│     model:  Qwen3.6-35B-A3B.gguf  │
│ directory:  ~                     │
│     skill:  chat                  │
│  database:  stateless             │
╰────────────────── Ctrl+C to exit ─╯
 Startup context: 103 tokens
❯ 
```

---

<h2 align="center">Plugin Extensions</h2>

<div align="center">
  <table>
    <tr>
      <td align="center" width="33%" valign="top">
        <b>React Desktop IDE (<a href="https://github.com/j5onrf/pycode">PyCode</a>)</b><br>
        <code>/pyc</code> · <code>/pyc web</code><br><br>
        <a href="https://github.com/user-attachments/assets/08a1358b-fca1-4fb4-b43e-2b96aaed6e42" target="_blank">
          <kbd>
            <img src="https://github.com/user-attachments/assets/08a1358b-fca1-4fb4-b43e-2b96aaed6e42" alt="PyCode Desktop App" width="100%" />
          </kbd>
        </a>
      </td>
      <td align="center" width="33%" valign="top">
        <b>Textual PyTUI</b><br>
        <code>/tui</code><br><br>
        <a href="https://github.com/user-attachments/assets/1cfcd26a-c7f9-482d-9624-24193ce7b5c2" target="_blank">
          <kbd>
            <img src="https://github.com/user-attachments/assets/1cfcd26a-c7f9-482d-9624-24193ce7b5c2" alt="Py Agent Textual TUI" width="100%" />
          </kbd>
        </a>
      </td>
      <td align="center" width="33%" valign="top">
        <b>Web Assistant (<a href="https://github.com/CopilotKit/OpenBot">PyBot</a>)</b><br>
        <code>/pybot</code> <i>(Coming Soon)</i><br><br>
      </td>
    </tr>
    <tr>
      <td align="center" width="33%" valign="top">
        <b>llama.cpp WebAgent</b><br>
        <code>/webui</code> · <code>/web</code><br><br>
        <a href="https://github.com/user-attachments/assets/39760d51-75f0-4b01-b385-6c5d99282a42" target="_blank">
          <kbd>
            <img src="https://github.com/user-attachments/assets/39760d51-75f0-4b01-b385-6c5d99282a42" alt="llama.cpp WebAgent" width="100%" />
          </kbd>
        </a>
      </td>
      <td align="center" width="33%" valign="top">
        <!-- Reserved Slot -->
      </td>
      <td align="center" width="33%" valign="top">
        <!-- Reserved Slot -->
      </td>
    </tr>
  </table>
</div>

---

<h2 align="center">Setup & Installation</h2>

### 1. Install py-agent

```bash
# 1. Install system dependencies & clone
sudo pacman -S python-rich python-requests
git clone https://github.com/j5onrf/py-agent.git ~/.config/py-agent

# 2. Register shell hook (bash / zsh)
echo '[ -f "$HOME/.config/py-agent/ai-hook.sh" ] && \
source "$HOME/.config/py-agent/ai-hook.sh"' >> ~/.bashrc
source ~/.bashrc
```

---

### 2. Configure Providers (`.env`)

Configure providers automatically via the interactive selector or copy the template:

```bash
# Option A: Interactive TUI Selector
model select

# Option B: Manual Configuration
cp ~/.config/py-agent/.env.example ~/.config/py-agent/.env
nano ~/.config/py-agent/.env
```

<details>
<summary><b>📋 View Example <code>~/.config/py-agent/.env</code> (Click to Expand)</b></summary>

```env
# ==============================================================================
# Py-Agent Environment Configuration Template
# Top-Down Priority: The first active (uncommented) provider key is used.
# ==============================================================================

# ── 1. Custom Endpoints / Hugging Face Router ─────────────────────────────────
# Get a free read token at: https://huggingface.co/settings/tokens
# CUSTOM_API_KEY="hf_YourHuggingFaceTokenHere"
CUSTOM_URL="https://router.huggingface.co/hf-inference/v1/chat/completions"
CUSTOM_MODEL="Qwen/Qwen3.8-27B"

# ── 2. Google Gemini ─────────────────────────────────────────────────────────
# Get key at: https://aistudio.google.com/app/apikey
# GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"
GEMINI_MODEL="gemini-3.7-flash"

# ── 3. OpenRouter (Free & Paid Catalog) ───────────────────────────────────────
# Get key at: https://openrouter.ai/keys
# OPENROUTER_API_KEY="sk-or-v1-YourOpenRouterKeyHere"
OPENROUTER_MODEL="openrouter/free"

# ── 4. Anthropic Claude ──────────────────────────────────────────────────────
# CLAUDE_API_KEY="sk-ant-YourClaudeKeyHere"
CLAUDE_MODEL="claude-Fable"

# ── 5. OpenAI ────────────────────────────────────────────────────────────────
# OPENAI_API_KEY="sk-YourOpenAIKeyHere"
OPENAI_MODEL="gpt-luna"

# ── 6. x.AI Grok ─────────────────────────────────────────────────────────────
# XAI_API_KEY="xai-YourGrokKeyHere"
XAI_MODEL="grok-5.6"

# ── Google Search Grounding (/gnd) ───────────────────────────────────────────
# GND_KEY="AIzaSyYourGeminiApiKeyHere"
# GND_MODEL="gemini-2.5-flash"

# ── Voice Bridge Transcription (Optional) ────────────────────────────────────
# GEM_VOICE="AIzaSyYourGeminiApiKeyHere"
# GEM_MODEL="gemini-3.5-flash-lite"

# ── Multimodal for text only models (Optional) ───────────────────────────────
# IMG_VOICE="your-api-key-here"
# IMG_MODEL="gemini-3.5-flash-lite"

# ── Context Window Budget ────────────────────────────────────────────────────
AI_MAX_TOKENS="8192"
```

</details>

---

### 3. Optional Client Surfaces

| Surface | Installation Command | Requirement |
| :--- | :--- | :--- |
| **Desktop IDE (<a href="https://github.com/j5onrf/pycode">PyCode</a>)** | `install pycode`<br><sub>(or `~/.config/py-agent/plugins/pycode/setup.sh`)</sub> | Node.js 20+, pnpm |
| **Textual PyTUI** | `sudo pacman -S python-textual python-uvloop && yay -S python-sqlite-vec` | uvloop & sqlite-vec |


---

<h2 align="center">Roadmap to v1.0.0</h2>

- [x] **Core Engine Optimization:** Production pass on streaming, token counting, and sub-agent concurrency.
- [x] **Thinking UI Controls:** Real-time thinking TPS metrics and `/t show|hide` panel toggles.
- [x] **Modular Agent Personas & Tool Loop:** Interactive profile selector on `ai init` (`pi`, `claude`, `hermes`) with automated path-healing file editing & YOLO execution loops.
- [x] **Textual Async PyTUI:** Sub-millisecond `uvloop` event loop integration, Unix socket sub-agent hub, and live workspace watchers.
- [x] **Reasonix Cognitive Step:** Real-time reasoning cognitive transition extraction, real-time thinking step formatting, and stream interception.
- [x] **Ralph Autonomous Task Loop:** On-demand `while` loop engine (`/task`, `TASK.md`) with automated completion verification.
- [x] **Voice to Text:** Low-latency HTTPS tablet or phone voice bridge, Gemini cloud transcription, and non-blocking stdin injection loop (`/v [auto]`).
- [x] **Kokoro Neural Text-to-Speech:** Real-time local neural voice reader (`/tts`), PipeWire audio integration, and automatic thinking/code block filtering.
- [x] **NOOA IPython Kernel Harness:** Single-tool Python kernel execution engine (`/py`) with NVIDIA NOOA bounded previews (`preview()`), model-callable `memory`/`graph` APIs, in-kernel `delegate()` sub-agents, AST safety gates, and stateful context token conservation.
- [x] **DeepSeek Session Audit & IPC:** Real-time JSONL event logging (`.agent/session.jsonl`), JSON-RPC 2.0 sub-agent socket IPC, and YAML skill profile frontmatter headers.
- [x] **Self-Healing Tool Parser:** Unsloth-inspired resilient JSON argument healer auto-balancing brackets, stripping leaked XML tokens, and repairing unescaped newlines for small local models.
- [x] **Scaffold-Model Fit & Surgical Edits:** Exact string replacements (`edit_file`), accidental overwrite protection on `write_file`, line-windowed reading, and read-before-edit invariants inspired by [little-coder](https://github.com/itayinbarr/little-coder).
- [x] **3-Zone Context Compactor & Universal Stream Interceptor:** Mario Zechner's [Pi](https://pi.dev)-inspired context compaction (`/com`) + zero-overhead stream interceptors for Hermes XML and Liquid/DeepSeek DSML.
- [x] **[PyCode](https://github.com/j5onrf/pycode) Cross-Platform GUI (T3 Fork):** Local-first React desktop and WebUI workspace connected via ACP (Agent Client Protocol) stdio JSON-RPC bridge (`/pyc`, `/pyc web`)—featuring real-time token/thought streaming, custom vector branding, theme-reactive ambient aurora glow toggle, and automatic workspace AST indexing.
- [x] **llama.cpp WebAgent Gateway:** Real-time tool execution (`list_dir`, `write_file`, AST index maps), Gemini vision pre-processing, and streaming proxy for the official `llama.cpp` WebUI (`/webui`).
- [x] **Google Search Grounding (/gnd):** Live web grounding via Gemini Search tool (`/gnd [budget]`) with automatic DuckDuckGo keyless fallback for real-time facts across CLI, TUI, WebUI, and PyCode.
- [ ] **PyBot Integration ([OpenBot](https://github.com/CopilotKit/OpenBot) Plugin):** Embedded web assistant & customizable agent widget plugin to bring `py-agent` intelligence to browser overlays and multi-surface chat bots.
- [ ] **Context Stress Testing:** Continuous context-window pressure tests across quantized local engines.
- [ ] **Automated File Containment Validation:** Zero-trust security verification on traversal boundaries.
- [ ] **v1.0.0 Production Release Tag!**

---

<h2 align="center">License</h2>

* **License**: Licensed under the permissive [MODIFIED MIT LICENSE](LICENSE).
* **Community:** Contributions are always welcome!



