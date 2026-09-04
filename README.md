<div align="center">
  <img alt="py-agent" src="logo.svg" height="130" />
</div>

<h1 align="center">Py Agent <img src="https://shieldcn.dev/badge/version-v0.9.9.16.svg?variant=secondary" alt="Version"><a href="https://github.com/j5onrf/py-agent"></a></h1>

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

Lightweight Python orchestration (`rich` + `requests` + `sqlite-vec` + `uvloop`) controlling a C++ backend `llama-server`. Optimized for fine-tuned quantized local models (`Qwen3.5-2B+` / `LFM2.5-8B+` for chat & fast single-task tool execution, `Qwen3.8-27B` / `Qwen3.6-35B` for full autonomous agents) and cloud providers—supporting native JSON tool calling, and IPython kernel (`/py`).

🟢 **Active:** Official `Hugging Face` Router endpoints ([`Qwen/Qwen3.8-27B`](https://huggingface.co/Qwen/Qwen3.8-27B), [`moonshotai/Kimi-K3`](https://huggingface.co/moonshotai/Kimi-K3), [`zai-org/GLM-5.3-Flash`](https://huggingface.co/zai-org/GLM-5.3-Flash), [`DeepSeek-V4-Flash-0731`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731), [`Qwen/Qwen3.8-2.4T-A95B`](https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B)).
> 💡 *Use `model select` to auto-configure free community HF Spaces.*

- **Direct Shell (`<plugins>`):** Sub-millisecond intent routing for shortcuts and diagnostic tools in [`ai-context.md`](ai-context.md).
- **Single-Turn Query (`ai <query>`):** Instant response piped directly back to the active shell prompt.
- **Multi-Turn Chat (`ai`):** Interactive terminal session with persistent memory context.
- **Workspace Agent (`ai init <path>`):** Full codebase graph indexing, surgical AST file editing, and sub-agent concurrency.
- **llama.cpp WebAgent (`/webui`):** Autonomous tool-enabled web gateway on official `llama-server` UI (`:3000`) with Gemini search grounding and vision image-processing for text-only local models.
---

<h2 align="center">Key Systems & Integrations</h2>

| Feature System | Foundation & Architectural Roots | Interface Command / Link |
| :--- | :--- | :--- |
| **PyCode Desktop IDE** | Customized [T3 Code](https://github.com/pingdotgg/t3code) fork connected via Agent Client Protocol (ACP) over stdio JSON-RPC 2.0 with live token & thought streaming. | `/pyc` (or `/pyc web`) |
| **Temporal Personality Memory (TPM)** | Reconciles personal identity & workspace habits using [Weaviate Engram](https://github.com/weaviate/engram-python-sdk) concepts + [Noema](https://github.com/Fail-Safe/Noema) Markdown files. | `.agent/tpm.md` |
| **Codebase Graph & Relational Index** | Structural codebase maps ([Graphify](https://github.com/Graphify-Labs/graphify)) + relational queries ([codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)) + [sqlite-vec](https://github.com/asg017/sqlite-vec) vector RAG. | `index-map <dir>` |
| **Ralph Autonomous Task Loop** | Self-directed iteration loop ([Ralph Wiggum](https://github.com/ghuntley/how-to-ralph-wiggum)) executing tasks against project specs (`TASK.md`) with failure decomposition. | `/task [goal]` |
| **NOOA IPython Kernel Harness** | NVIDIA Object-Oriented Agent ([NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents) + [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent)) stateful Python kernel with bounded previews (`preview()`), model-callable `memory`/`graph` APIs, and in-kernel `delegate()` sub-agents. | `/py` |
| **SmallCoder Surgical Edits** | Whitespace-tolerant replacements (`edit_file`) + AST skeleton guards (>250 lines) + overwrite protection (`write_file`) inspired by [SmallCoder](https://github.com/Doorman11991/smallcode). | `edit_file <path>` |
| **3-Zone Context Compactor** | Token preservation compactor inspired by [Pi Coding Agent](https://pi.dev)—condenses older tool outputs while preserving completed task progress anchors. | `/compact` (or `/com`) |
| **Modular Sub-27B Adapters** | Dedicated self-healing parser (`agent_adapters.py`) resolving Hermes XML, DSML, Mistral, and raw Python tool syntax out-of-band. | `modules/agent_adapters.py` |
| **DeepSeek Session Audit & IPC** | Structured JSONL session event logs + JSON-RPC 2.0 socket IPC + YAML skill frontmatter overlays inspired by [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness). | `.agent/session.jsonl` |
| **Reasonix Cognitive Engine** | Real-time reasoning trace step extraction ([Reasonix](https://github.com/esengine/deepseek-reasonix)) + cognitive phase formatting inside thinking stream. | `/t [N\|show\|hide]` |
| **System Admin & Diagnostics** | Live health monitoring, AUR/security audits, system optimization, status routing, and git commit hooks. | [`tools/agentic/system/`](tools/agentic/system) |
| **Model Select TUI** | Real-time **[Cloud Connection](modules/Readme.md)** TUI, key toggles, and endpoint selector. | `model select` |
| **Interactive Textual PyTUI** | Full-screen **[Textual](modules/Readme.md)** TUI workspace with JSON-RPC 2.0 socket IPC powered by a C-speed `uvloop` event loop. | `/tui` |
| **llama.cpp WebAgent Gateway** | Full autonomous agent tool execution (`list_dir`, `write_file`, AST graph) + Gemini multimodal vision for text-only local models. | `/webui` |
| **Adapters** | **Sub-27B Healer** | Self-healing tool format adapters (`agent_adapters.py`) resolving Hermes XML, DSML, Mistral, and raw planning JSON out-of-band for 2B–8B models. |

---

<h2 align="center">Core Capabilities</h2>

| Core Module | Capability | Description |
| :--- | :--- | :--- |
| **Engine** | **Zero-Daemon** | 0% idle CPU/RAM usage. Native Python standard-library execution. |
| **Providers** | **Active Provider** | Direct `.env` configuration: Custom Endpoints / HF, Gemini, OpenRouter, OpenAI, Claude, Grok, or Local GGUF. |
| **Multi-Agent** | **Subagents** | [Vercel Eve](https://github.com/vercel/eve)-style sub-agents with [herdr](https://github.com/ogulcancelik/herdr) multiplexing (`-save`/`-load`) + in-kernel `delegate("goal")` sandboxes. |
| **Safety** | **Zero-Trust Fallback** | Mandatory non-bypassable `[Y/n]` confirmation for out-of-bounds paths and package managers (`pip`, `pacman`, `sudo`). |
| **Integrity** | **Type-Safe & AST Guard** | [Pydantic AI](https://github.com/pydantic/pydantic-ai) schemas + AST-validated Python file writes with live diff previews. |
| **Resilience** | **Self-Healing Tools** | Unsloth-inspired JSON argument healer re-serializing valid schemas to prevent server `HTTP 500` errors. |
| **Optimization** | **Token-Slasher** | Custom [`tools/`](tools/) and [`skills/`](skills/) integration built for minimal token consumption. |
| **Grounding** | **Web Search Engine** | Real-time factual search retrieval (`/gnd`) with Gemini Grounding and DuckDuckGo safety fallback in CLI, TUI & WEB/PYC. |
| **Voice-to-Text** | **Tablet/Phone Bridge** | Zero-latency HTTPS voice bridge with Gemini cloud transcription and native Wayland virtual typing (`wtype`) directly into PyCode IDE and CLI (`/v [auto]`). |
| **Text-to-Speech** | **Neural Kokoro TTS** | Local PipeWire audio reader (`/tts`) using `koko` with silent code/thinking filtering and concise status announcements. |

---

<h2 align="center">CLI Launch Interface</h2>

> Customize box themes with `/box [1-8]`. For detailed multi-agent workflows, read the [**Workspace Manual**](projects/Readme.md).

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

<h2 align="center">Client Surfaces & Environments</h2>

<p align="center">
  Py-Agent is surface-agnostic. Switch seamlessly between the terminal, web gateway, and desktop IDE:
</p>

<div align="center">
  <table>
    <tr>
      <td align="center" width="33%" valign="top">
        <h3><a href="https://github.com/j5onrf/pycode">PyCode Desktop IDE</a></h3>
        <code>/pyc</code> · <code>/pyc web</code><br><br>
        <a href="https://github.com/user-attachments/assets/08a1358b-fca1-4fb4-b43e-2b96aaed6e42" target="_blank">
          <kbd>
            <img src="https://github.com/user-attachments/assets/08a1358b-fca1-4fb4-b43e-2b96aaed6e42" alt="PyCode Desktop App" width="100%" />
          </kbd>
        </a><br><br>
        <sub>Local-first React IDE with ACP stdio JSON-RPC 2.0, live thought streaming & ambient aurora glow.</sub>
      </td>
      <td align="center" width="33%" valign="top">
        <h3>Textual PyTUI</h3>
        <code>/tui</code><br><br>
        <a href="https://github.com/user-attachments/assets/1cfcd26a-c7f9-482d-9624-24193ce7b5c2" target="_blank">
          <kbd>
            <img src="https://github.com/user-attachments/assets/1cfcd26a-c7f9-482d-9624-24193ce7b5c2" alt="Py Agent Textual TUI" width="100%" />
          </kbd>
        </a><br><br>
        <sub>Full-screen terminal interface with <code>uvloop</code> async event loop, socket IPC & live reasoning steps.</sub>
      </td>
      <td align="center" width="33%" valign="top">
        <h3>llama.cpp WebAgent</h3>
        <code>/webui</code> · <code>/web</code><br><br>
        <a href="https://github.com/user-attachments/assets/39760d51-75f0-4b01-b385-6c5d99282a42" target="_blank">
          <kbd>
            <img src="https://github.com/user-attachments/assets/39760d51-75f0-4b01-b385-6c5d99282a42" alt="llama.cpp WebAgent" width="100%" />
          </kbd>
        </a><br><br>
        <sub>Autonomous tool reverse proxy for official <code>llama-server</code> (:3000) with Gemini Flash vision.</sub>
      </td>
    </tr>
  </table>

  <p align="center">
    <code>/v</code> <b>Voice-to-Text (:9999)</b> &nbsp;•&nbsp; 
    <code>/tts</code> <b>Neural Kokoro Audio</b> &nbsp;•&nbsp; 
    <code>/pybot</code> <b>Web Assistant (Roadmap)</b>
  </p>
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
# CUSTOM_API_KEY="hf_YourHuggingFaceTokenHere"
CUSTOM_URL="https://router.huggingface.co/hf-inference/v1/chat/completions"
CUSTOM_MODEL="Qwen/Qwen3.8-27B"

# ── 2. Google Gemini ─────────────────────────────────────────────────────────
# GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"
GEMINI_MODEL="gemini-3.7-flash"

# ── 3. OpenRouter (Free & Paid Catalog) ───────────────────────────────────────
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

# ── Context Window Budget ────────────────────────────────────────────────────
AI_MAX_TOKENS="8192"
```

</details>

---

### 3. Optional Client Surfaces

| Surface | Setup / Command | Requirements |
| :--- | :--- | :--- |
| **Desktop IDE ([PyCode](https://github.com/j5onrf/pycode))** | `install-pycode`<br><sub>(or `~/.config/py-agent/plugins/pycode/setup.sh`)</sub> | Node.js 20+, pnpm |
| **Textual PyTUI** | `sudo pacman -S python-textual python-uvloop && yay -S python-sqlite-vec` | uvloop & sqlite-vec |
| **Voice-to-Text Bridge** | `/v` (or `/v auto` on `:9999`) | `sudo pacman -S wtype openssl` & `GEM_VOICE` in `.env` |
| **Neural Kokoro TTS** | `/tts`<br><sub>(or [Audio Plugin](plugins/audio))</sub> | `yay -S koko-bin pw-play wl-clipboard` |

---

<h2 align="center">Roadmap to v1.0.0</h2>

- [x] **Core Engine Optimization:** Production pass on streaming, token counting, and sub-agent concurrency.
- [x] **Thinking UI Controls:** Real-time thinking TPS metrics and `/t show|hide` panel toggles.
- [x] **Modular Agent Personas & Tool Loop:** Interactive profile selector on `ai init` (`pi`, `claude`, `hermes`) with automated path-healing file editing & YOLO execution loops.
- [x] **Textual Async PyTUI:** Sub-millisecond `uvloop` event loop integration, Unix socket sub-agent hub, and live workspace watchers.
- [x] **Reasonix Cognitive Step:** Real-time reasoning cognitive transition extraction and streaming step formatting.
- [x] **Ralph Autonomous Task Loop:** Self-directed iteration engine (`/task`, `TASK.md`) with failure-state decomposition.
- [x] **Voice to Text:** Low-latency HTTPS voice bridge, Gemini transcription, and non-blocking stdin injection loop (`/v [auto]`).
- [x] **Kokoro Neural Text-to-Speech:** Real-time local neural voice reader (`/tts`), PipeWire audio integration, and automatic thinking/code block filtering.
- [x] **NOOA IPython Kernel Harness:** Single-tool Python kernel execution engine (`/py`) with NVIDIA NOOA bounded previews (`preview()`), model-callable `memory`/`graph` APIs, in-kernel `delegate()` sub-agents, AST safety gates, and stateful context conservation.
- [x] **DeepSeek Session Audit & IPC:** Real-time JSONL event logging (`.agent/session.jsonl`), JSON-RPC 2.0 socket IPC, and YAML skill profile frontmatter headers.
- [x] **Modular Sub-27B Adapters & Self-Healing Parser:** Dedicated `agent_adapters.py` handling Hermes XML, DSML, Mistral, and raw function call extraction for small quantized models.
- [x] **SmallCoder Surgical Edits & AST Skeleton:** Whitespace/indentation tolerance in `edit_file`, overwrite protection on `write_file`, and AST outline reading for large files (>250 lines).
- [x] **3-Zone Context Compactor with Progress Anchor:** Pi-inspired context compaction (`/com`) preserving completed milestone summaries across context purges.
- [x] **PyCode Cross-Platform GUI (T3 Fork):** Local-first React desktop and WebUI workspace connected via ACP stdio JSON-RPC bridge (`/pyc`, `/pyc web`).
- [x] **llama.cpp WebAgent Gateway:** Real-time tool execution, Gemini vision pre-processing, and streaming proxy for the official `llama.cpp` WebUI (`/webui`).
- [x] **Google Search Grounding (/gnd):** Live web grounding via Gemini Search tool with automatic DuckDuckGo keyless fallback across CLI, TUI, WebUI, and PyCode.
- [x] **Zero-Trust Hardened Containment:** Non-bypassable interactive `[Y/n]` fallback gate for out-of-bounds access and package management tools (`pip`, `pacman`, `sudo`).
- [ ] **PyBot Integration ([OpenBot](https://github.com/CopilotKit/OpenBot) Plugin):** Embedded web assistant & customizable agent widget plugin.
- [ ] **v1.0.0 Production Release Tag!**

---

<h2 align="center">License</h2>

* **License**: Licensed under the permissive [MODIFIED MIT LICENSE](LICENSE).
* **Community:** Contributions are always welcome!
