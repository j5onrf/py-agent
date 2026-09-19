<br>

<div align="center">
  <img alt="py-agent" src="logo.svg" height="120" />
  <h1>py-agent</h1>

  <p>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/version-v0.9.9.35.svg?variant=secondary" alt="Version"></a>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/Python.svg?variant=branded&brand=python" alt="Language"></a>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/C%2B%2B.svg?variant=branded&brand=cplusplus" alt="C++"></a>
    <a href="https://github.com/j5onrf/py-agent/blob/main/LICENSE"><img src="https://shieldcn.dev/badge/license-MIT-green.svg" alt="License"></a>
    <a href="https://shieldcn.dev/badge/status-beta-blue.svg"><img src="https://shieldcn.dev/badge/status-beta-blue.svg" alt="Status"></a>
  </p>

  <p>
    <code>gguf</code> &nbsp;•&nbsp; <code>llama.cpp</code> &nbsp;•&nbsp; <code>gemini</code> &nbsp;•&nbsp; <code>huggingface</code> &nbsp;•&nbsp; <code>openrouter</code>
  </p>

  <p>
    <b>Lightweight Python orchestration (<code>rich</code> + <code>requests</code>) driving a high-throughput C++ <code>llama-server</code> backend.</b><br>
    <sub>Stateful in-memory Python batching (<code>/py</code>), self-healing tool adapters (<code>/adp</code>), and sub-millisecond local execution.</sub>
  </p>

  <br>

  <table>
    <tr>
      <td align="center" width="50%" valign="top">
        <h3>Sub-27B Compact (SLM)</h3>
        <p><sub>Ultra-fast tool calling, shell triage & single-turn code edits</sub></p>
        <code>Ling-3.0-tiny*</code> &nbsp;•&nbsp; <code>LFM2.5-8B</code><br>
        <code>MiniCPM5-2B</code> &nbsp;•&nbsp; <code>Qwen3.5-2B+</code>
      </td>
      <td align="center" width="50%" valign="top">
        <h3>27B+ Autonomous (LLM)</h3>
        <p><sub>Deep reasoning, multi-file refactoring & recursive sub-agents</sub></p>
        <code>Occamy-1.0*</code> &nbsp;•&nbsp; <code>Nex-N2.5-mini</code><br>
        <code>KAT-Coder-V2.5</code> &nbsp;•&nbsp; <code>Qwen3.8-27B</code><br>
        <code>Qwen3.6-35B</code> &nbsp;•&nbsp; <code>Ornith/Tiel</code><br>
        <code>Qwen3.8-Flash-Next</code> &nbsp;•&nbsp; <code>DeepSeek&#8209;V4.1</code>
      </td>
    </tr>
  </table>
  
  <p>
    <sub>* Recommended benchmark baselines &nbsp;•&nbsp; Run <code>model select</code> in your terminal to switch models</sub>
  </p>

  <p>
    <sub><b>Cloud & Community Spaces:</b> Official <a href="https://huggingface.co">Hugging Face Router</a> endpoints<br>(<a href="https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash"><code>DeepSeek-V4.1-Flash</code></a>, <a href="https://huggingface.co/zai-org/GLM-5.3-Flash"><code>GLM-5.3-Flash</code></a>, <a href="https://huggingface.co/inclusionAI/Ling-3.0-flash-VL"><code>Ling-3.0-flash-VL</code></a>, and <a href="https://huggingface.co/moonshotai/Kimi-K3"><code>Kimi-K3</code></a>).</sub>
  </p>
</div>

<br>

---

```console
~ ❯ ai
╭─  Py Agent  ─────────────╮
│     model:  Occamy-1.0   │
│ directory:  ~            │
│   profile:  chat         │
│  database:  stateless    │
╰───────── Ctrl+C to exit ─╯

❯ █
```

<div align="center">
  <p><sub>Customize box themes with <code>/box [1-8]</code>. For detailed workflows, read the <a href="projects/Readme.md"><b>Workspace Manual</b></a>.</sub></p>
</div>

<br>

---

<h2 align="center">Execution Surfaces</h2>

<div align="center">

| Command | Mode | Operational Scope |
| :--- | :--- | :--- |
| `<space> [query]` | **Direct Shell** | Sub-millisecond intent matching via [`ai-context.md`](ai-context.md) |
| `ai "<query>"` | **Single Query** | Single-shot command execution and streamed response |
| `ai` | **Interactive** | Multi-turn chat session with persistent memory and profile routing |
| `ai init [path]` | **Workspace Agent** | Codebase index-map, surgical diffing (`edit_file`), and task loops |
| `eval-stack` | **Agentic Benchmark** | 7-test decision-grade suite measuring tool par and accuracy |
| `/webui` | **Web Gateway** | Autonomous tool reverse proxy for official `llama-server` UI |

</div>

<p align="center">
  <sub><b>Session Hotkeys:</b> <code>/compact</code> 3-zone context prune &nbsp;•&nbsp; <code>/adp</code> toggle adapters &nbsp;•&nbsp; <code>/py</code> in-memory REPL &nbsp;•&nbsp; <code>/gnd</code> search grounding &nbsp;•&nbsp; <code>/hs</code> memory audit</sub>
</p>

<br>

---

<h2 align="center">Runtime Architecture</h2>

* **Hardened Containment:** Non-bypassable `[y/N]` confirmation gates for system-mutating commands (`sudo`, `pacman`, `pip`, `systemctl`) and out-of-bounds file access—even in YOLO mode.
* **Git-Native Memory:** Plain Markdown directives in `.agent/memory/*.md` loaded in `<0.1ms`. Fully auditable and human-editable in `nvim` or `code` with zero database overhead.
* **Self-Healing Adapters (`/adp`):** Out-of-band argument normalizer repairing malformed JSON and bracket syntax on small models without burning turn retries or polluting context prompts.
* **Deterministic Diffing:** 3-stage resilient replacement (`Exact` &rarr; `Whitespace` &rarr; `88% Fuzzy`) verified by Python AST syntax guards before disk writes to eliminate corruption.

<br>

---

<h2 align="center">Benchmark & Efficiency</h2>

<p align="center">
  <sub>Synthesizing battle-tested patterns from <b>Pi</b> (3-zone context compaction), <b>SmallCoder</b> (resilient 3-stage AST diffs),<br>
  <b>Unsloth AI</b> (out-of-band schema healing), and <b>OKF</b> (git-native persistent memory).</sub>
</p>

| Sub-27B Challenge | Without Adapters | With `/adp` Active | Efficiency Gain |
| :--- | :---: | :---: | :--- |
| **AG-03 (Surgical Edit & Test)** | 16 turns | **6 turns** | **62% fewer turns** (eliminates diff-retry loops) |
| **AG-07 (In-Memory Batch Loop)** | 14 turns | **2 turns** | **85% fewer turns** (executes batch script on Turn 1) |
| **Full Suite Pass Rate** | Retries / Failures | **100% (7/7)** | **Zero unhandled syntax or format failures** |

<br>

| Operational Tier | Py-Agent | DeepSeek (`dsh`) | Comparison & Capabilities |
| :--- | :---: | :---: | :--- |
| **Pure Chat** | **211 tokens** (`ai`) | ~450+ tokens | Conversational Q&A with confirmation command gates |
| **Native Core** | **~680 tokens** (`SMOL_TOOLS`) | ~632 tokens | Surgical file edits, code search & shell verification |
| **Dual Mode** | **~760 tokens** (`python + native`) | ~1,200+ tokens | **~40% fewer tokens.** In-memory testing with **~95% cache hits** |
| **Full Graph** | **~1,100 tokens** (11 tools + AST) | 2,500–4,000+ tokens | **Up to 3x fewer tokens.** Complete relational SQLite FTS5 symbol graph |
| **Idle Overhead** | **0% CPU / 0 MB RAM** | Node.js Active | Direct process lifecycle; zero persistent background services |

<br>

---

<h2 align="center">Client Surfaces & Environments</h2>

<p align="center">
  Py-Agent is surface-agnostic. Switch seamlessly between terminal, web gateway, and desktop IDE:
</p>

<div align="center">
  <table>
    <tr>
      <td align="center" width="210" valign="top">
        <br>
        <h3><a href="https://github.com/j5onrf/pycode">PyCode IDE</a></h3>
        <p><code>/pyc</code> · <code>/pyc web</code></p>
        <sub>Local-first React desktop workspace with ACP JSON-RPC 2.0.</sub>
        <br><br>
      </td>
      <td align="center" width="210" valign="top">
        <br>
        <h3>Textual PyTUI</h3>
        <p><code>/tui</code></p>
        <sub>Full-screen reactive terminal workspace with <code>uvloop</code>, socket IPC.</sub>
        <br><br>
      </td>
      <td align="center" width="210" valign="top">
        <br>
        <h3>llama.cpp WebAgent</h3>
        <p><code>/webui</code> · <code>/web</code></p>
        <sub>Autonomous tool reverse proxy for official <code>llama-server</code>.</sub>
        <br><br>
      </td>
    </tr>
  </table>

  <p>
    <sub><code>/v</code> Voice-to-Text (<code>:9999</code>) &nbsp;•&nbsp; <code>/tts</code> Neural Kokoro Audio &nbsp;•&nbsp; <code>/pybot</code> Web Assistant</sub>
  </p>
</div>

<br>

---

<h2 align="center">Setup & Installation</h2>

### 1. Install py-agent

```bash
# 1. Install dependencies (Arch/CachyOS or generic pip)
sudo pacman -S python-rich python-requests || pip install rich requests

# 2. Clone repository
git clone https://github.com/j5onrf/py-agent.git ~/.config/py-agent

# 3. Register shell hook (bash / zsh)
echo '[ -f "$HOME/.config/py-agent/ai-hook.sh" ] && \
source "$HOME/.config/py-agent/ai-hook.sh"' >> ~/.bashrc
source ~/.bashrc
```

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
# Py-Agent Environment Configuration (.env.example)
#
# RULES:
# 1. Top-Down: First uncommented key is active.
# 2. Toggle: Add '#' to disable; remove '#' to enable.
# 3. Add More: Define CUSTOM3_*, CUSTOM4_*, etc. anywhere.
# 4. Fallback: If all keys have '#', routes to local server (:8080).
# 5. TUI Config: Run 'model select' to configure everything interactively.
# ==============================================================================

# ── 1. Custom 1 / Hugging Face Router ─────────────────────────────────────────
# CUSTOM_API_KEY="hugging-face-api-key"
CUSTOM_URL="https://router.huggingface.co/v1/chat/completions"
CUSTOM_MODEL="Qwen/Qwen3.8-27B"

# ── 2. Custom 2 / Generic Endpoint (DeepSeek, OpenAI, etc.) ───────────────────
# CUSTOM2_API_KEY="sk-your-key-here"
CUSTOM2_URL="https://api.deepseek.com/chat/completions"
CUSTOM2_MODEL="deepseek-chat"

# ── 3. Google Gemini (Free daily tier via Google AI Studio) ───────────────────
# GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"
GEMINI_MODEL="gemini-3.5-flash-lite"

# ── 4. OpenRouter (Free community models & Universal paid gateway) ────────────
# OPENROUTER_API_KEY="sk-or-v1-YourOpenRouterKeyHere"
OPENROUTER_MODEL="openrouter/free"

# ── Auxiliary Services (Independent Toggles) (Optional) ───────────────────────

# Google Search Grounding (/gnd)
# GND_KEY="AIzaSyYourGeminiApiKeyHere"
# GND_MODEL="gemini-2.5-flash"

# Voice Bridge Transcription (Speech-to-Text on :9999)
# GEM_VOICE="AIzaSyYourGeminiApiKeyHere"
# GEM_MODEL="gemini-3.5-flash-lite"

# Multimodal Vision OCR (Pre-processor for text-only local models)
# IMG_VOICE="AIzaSyYourGeminiApiKeyHere"
# IMG_MODEL="gemini-3.5-flash-lite"

# ── Model Context Protocol (MCP) (Optional) ───────────────────────────────────

# Firecrawl Scrape & Search
# FIRECRAWL_API_KEY="fc-your-actual-api-key"

# ── Context Window Budget ─────────────────────────────────────────────────────
AI_MAX_TOKENS="8192"
```

</details>

<br>

---

<h2 align="center">Roadmap to v1.0.0</h2>

* **Modular Sub-27B adapters:**  (`/adp`), 3-zone context compactor with progress anchors (`/com`), live web grounding (`/gnd`), zero-trust containment gates, and 7-test decision-grade agentic benchmark (`eval-stack`).
* **Possible Horizons:** Embedded PyBot ([AkeruBot](https://github.com/opencoredev/akeru-bot)) Embedded AkeruBot agent widget and web gateway.
* **Adaptive Context Slicing:**</b> Automated tool schema reduction for small windows</sub><br>
* **v1.0.0 Production Release Tag**

<br>

---

<h2 align="center">Documentation & License</h2>

* **<a href="projects/Readme.md">Workspace & Session Manual</a>**
* **<a href="modules/Readme.md">System Architecture & Lineage</a>**
* **License**: Licensed under the permissive [MODIFIED MIT LICENSE](LICENSE)
* **Community:** Contributions are always welcome!

