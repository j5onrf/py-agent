<br>

<div align="center">
  <img alt="py-agent" src="logo.svg" height="130" />
  <h1>Py Agent</h1>

  <p>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/version-v0.9.9.53.svg?variant=secondary" alt="Version"></a>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/Python.svg?variant=branded&brand=python" alt="Language"></a>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/C%2B%2B.svg?variant=branded&brand=cplusplus" alt="C++"></a>
    <a href="https://github.com/j5onrf/py-agent/blob/main/LICENSE"><img src="https://shieldcn.dev/badge/license-MIT-green.svg" alt="License"></a>
    <a href="https://shieldcn.dev/badge/status-beta-blue.svg"><img src="https://shieldcn.dev/badge/status-beta-blue.svg" alt="Status"></a>
  </p>

  <p>
    <code>gguf</code> &nbsp;•&nbsp; <code>llama.cpp</code> &nbsp;•&nbsp; <code>gemini</code> &nbsp;•&nbsp; <code>huggingface</code> &nbsp;•&nbsp; <code>openrouter</code>
  </p>

  <p>
    <b>Python runtime (<code>rich</code> + <code>requests</code>) driving a local C++ <code>llama-server</code> backend or cloud APIs.</b><br>
    <sub>In-memory Python execution (<code>/py</code>), argument repair adapters (<code>/adp</code>), and instant startup.</sub>
  </p>

  <br>

  <table>
    <tr>
      <td align="center" width="50%" valign="top">
        <h3>Sub-27B (SLM)</h3>
        <p><sub>Tool calling, shell triage, and single-turn code edits</sub></p>
        <code>Ling-3.0-tiny*</code> &nbsp;•&nbsp; <code>LFM2.5-8B</code><br>
        <code>MiniCPM5-2B</code> &nbsp;•&nbsp; <code>Qwen3.5-2B+</code>
      </td>
      <td align="center" width="50%" valign="top">
        <h3>27B+ (LLM)</h3>
        <p><sub>Reasoning, multi-file refactoring, and sub-agents</sub></p>
        <code>Qwen3.8-35B-D*</code> &nbsp;•&nbsp; <code>Ornith-1.5</code><br>
        <code>KAT-Coder-V2.5</code> &nbsp;•&nbsp; <code>Tiel-Coder-35B</code><br>
        <code>Occamy-1.0</code> &nbsp;•&nbsp; <code>Nex-N2.5-mini</code><br>
        <code>Qwen3.8-27B</code> &nbsp;•&nbsp; <code>Qwen3.8-Flash</code><br>
        <code>DeepSeek&#8209;V4.1</code>
      </td>
    </tr>
  </table>
  
  <p>
    * Benchmark baselines &nbsp;•&nbsp; Run <code>model select</code> in your terminal to switch models
  </p>

  <p>
    <sub><b>Cloud Endpoints:</b> <a href="https://huggingface.co">Hugging Face Router</a>, <a href="https://tokenharbor.ai">TokenHarbor</a>, and <a href="https://openrouter.ai">OpenRouter</a><br>
    <b>Hugging Face:</b> <a href="https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash"><code>DeepSeek-V4.1-Flash</code></a>, <a href="https://huggingface.co/zai-org/GLM-5.3-Flash"><code>GLM-5.3-Flash</code></a>, <a href="https://huggingface.co/inclusionAI/Ling-3.0-flash-VL"><code>Ling-3.0-flash-VL</code></a>, and <a href="https://huggingface.co/moonshotai/Kimi-K3"><code>Kimi-K3</code></a><br><br>
    <b>Free Endpoints:</b> <a href="https://tokenharbor.ai"><code>mimo-v2.6-flash:free</code></a>, <a href="https://tokenharbor.ai"><code>deepseek-v4.1-flash:free</code></a> (TokenHarbor) &nbsp;•&nbsp; <a href="https://openrouter.ai/models?variant=free"><code>inclusionai/ling-3.1-flash</code></a> (OpenRouter)</sub>
  </p>
</div>

<br>

---

```console
~ ❯ ai
╭─ ∿ Py Agent ──────────────────────╮
│     model:  Qwen3.8-35B-Distill   │
│ directory:  ~                     │
│   profile:  chat                  │
│  database:  stateless             │
╰───────────────────────────────────╯

❯ █
```

<div align="center">
  <p><sub>Select box themes with <code>/box [1-7]</code>. Workspace details in the <a href="projects/Readme.md"><b>Workspace Manual</b></a>.</sub></p>
</div>

<br>

---

<h2 align="center">Execution Surfaces</h2>

<div align="center">

| Command | Mode | Scope |
| :--- | :---: | :---: |
| `[query]` | **Shell Intercept** | Intent matching via [`ai-context.md`](ai-context.md) |
| `ai "<query>"` | **Single Query** | Direct prompt response |
| `ai` | **Interactive Chat** | Multi-turn chat session |
| `ai init [path]` | **Workspace Agent** | Project workspace session |

</div>

<p align="center">
  <sub><code>/yolo</code> &nbsp;•&nbsp; <code>/py</code> repl &nbsp;•&nbsp; <code>/adp</code> adapters &nbsp;•&nbsp; <code>/t</code> reasoning &nbsp;•&nbsp; <code>/task</code> loop goal &nbsp;•&nbsp; <code>/s</code> skills &nbsp;•&nbsp; <code>/a</code> all meta &nbsp;•&nbsp; <code>/md</code> markdown</sub><br>
  <sub><code>/m</code> map &nbsp;•&nbsp; <code>file</code> load &nbsp;•&nbsp; <code>/mem</code> memory &nbsp;•&nbsp; <code>/com</code> compact &nbsp;•&nbsp; <code>/gnd</code> search &nbsp;•&nbsp; <code>/hs</code> hindsight &nbsp;•&nbsp; <code>/tok</code> tokens &nbsp;•&nbsp; <code>/sync</code> map</sub><br>
  <sub><code>/tui</code> &nbsp;•&nbsp; <code>/pyc</code> &nbsp;•&nbsp; <code>/dsh</code> &nbsp;•&nbsp; <code>/zed</code> &nbsp;•&nbsp; <code>/webui</code> &nbsp;•&nbsp; <code>/calm</code> &nbsp;•&nbsp; <code>/v</code> &nbsp;•&nbsp; <code>/tts</code> &nbsp;•&nbsp; <code>/box</code> &nbsp;•&nbsp; <code>/stats</code> &nbsp;•&nbsp; <code>-save</code> / <code>-load</code> &nbsp;•&nbsp; <code>/c</code> &nbsp;•&nbsp; <code>/r</code></sub>
</p>

<br>

---

<h2 align="center">Runtime Architecture</h2>

* **Security Kernel (`agent_security.py`):** Interactive `[y/N]` confirmation gates for system commands (`sudo`, `pacman`, `pip`, `systemctl`) and out-of-bounds file access, enforced even in YOLO mode.
* **Workspace Memory:** Global rules (`skills/system_instructions.md`) and project directives (`.agent/memory/*.md`) stored as plaintext Markdown.
* **Tool Adapters (`/adp`):** Out-of-band argument normalizer repairing malformed JSON, markdown fences, and parameter aliases.

<br>

---

<h2 align="center">Benchmarks</h2>

<div align="center">

### Agent Evaluation (`eval-stack`)

| Rank | Model | Par Eff | Agent Index |
| :---: | :--- | :---: | :---: |
| **1** | **Qwen3.8-35B-Distill** *(MTP)* | **136.4%** | **92.2 (A)** |
| **2** | **KAT-Coder-V2.5-Dev** | **90.9%** | **89.8 (A)** |
| **3** | **Ornith-1.5-35B-A3B** | **88.2%** | **89.3 (A)** |
| **4** | **Tiel-Coder-35B-A3B** | **90.9%** | **87.6 (B)** |
| **5** | **Occamy-1.0** | **90.9%** | **87.0 (B)** |
| **6** | **Qwen3.8-35B-Distill** *(Pure)* | **90.9%** | **86.4 (B)** |
| **7** | **Nex-N2.5-mini** | **88.2%** | **85.8 (B)** |
| **—** | **Ling-3.0-tiny** *(SLM)* | **104.0%** | **100.0 (A+)** |

<br>

| Benchmark Challenge | Without Adapters | With `/adp` Active | Efficiency Gain |
| :--- | :---: | :---: | :--- |
| **AG-03 (Surgical Edit & Test)** | 16 turns | **6 turns** | **62% fewer turns** (avoids diff-retry loops) |
| **AG-07 (In-Memory Batch Loop)** | 14 turns | **2 turns** | **85% fewer turns** (executes batch script on Turn 1) |
| **Full Suite Pass Rate** | Retries / Failures | **100% (7/7)** | **Zero unhandled syntax or format failures** |

<br>

| AG-03 Benchmark (`Ling-3.0-tiny`) | Py-Agent (`/adp`) | Pi (`pi-tool-repair`) |
| :--- | :---: | :---: |
| **Pass Rate** | **100%** (Turn 1) | **100%** (Turn 1) |
| **Output Spend** | **48 tokens** | 363 tokens |
| **Reasoning Spend** | **21 tokens** | 4,900 tokens |
| **Latency** | **1.7s** | ~4.5s |

<br>

| Operational Tier | Py-Agent | DeepSeek (`dsh`) |
| :--- | :---: | :---: |
| **Pure Chat** | **211 tokens** (`ai`) | ~450+ tokens |
| **Pure Bash** | **~110 tokens** (`PUREBASH_TOOLS` · 167% Par, A+) | — |
| **Native Core** | **~680 tokens** (`SMOL_TOOLS`) | ~632 tokens |
| **Dual Mode** | **~760 tokens** (`python + native`) | ~1,200+ tokens |
| **Full Graph** | **~1,100 tokens** (12 tools + AST) | 2,500–4,000+ tokens |
| **Idle Overhead** | **0% CPU / 0 MB RAM** | Node.js Active |

</div>

<br>

---

<h2 align="center">Client Surfaces</h2>

<div align="center">
  <table>
    <tr>
      <td align="center" width="210" valign="top">
        <br>
        <h3><a href="https://github.com/j5onrf/pycode">PyCode IDE</a></h3>
        <p><code>/pyc</code> · <code>/pyc web</code></p>
        <sub>React desktop workspace using ACP JSON-RPC 2.0.</sub>
        <br><br>
      </td>
      <td align="center" width="210" valign="top">
        <br>
        <h3>Textual PyTUI</h3>
        <p><code>/tui</code></p>
        <sub>Terminal workspace built with Textual and <code>uvloop</code>.</sub>
        <br><br>
      </td>
      <td align="center" width="210" valign="top">
        <br>
        <h3>llama.cpp WebAgent</h3>
        <p><code>/webui</code> · <code>/web</code></p>
        <sub>Tool reverse proxy for <code>llama-server</code>.</sub>
        <br><br>
      </td>
    </tr>
  </table>

  <p>
    <sub><code>/v</code> Voice-to-Text (<code>:9999</code>) &nbsp;•&nbsp; <code>/tts</code> Neural Kokoro Audio &nbsp;•&nbsp; <code>/dsh</code> DeepSeek Harness &nbsp;•&nbsp; <code>/zed</code> Editor</sub>
  </p>
</div>

<br>

---

<h2 align="center">Installation</h2>

### 1. Install py-agent

```bash
# 1. Install dependencies (Arch/CachyOS or pip)
sudo pacman -S python-rich python-requests

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
```

<details>
<summary><b>View Example (<code>~/.config/py-agent/.env.example</code>)</b></summary>

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

# ── 2. Custom 2 / Generic Endpoint (DeepSeek, OpenAI, TokenHarbor, etc.) ──────
# CUSTOM2_API_KEY="sk-your-key-here"
CUSTOM2_URL="https://tokenharbor.ai/v1/chat/completions"
CUSTOM2_MODEL="qwen3.8-flash:free"

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

<h2 align="center">Documentation & License</h2>

* **<a href="projects/Readme.md">Workspace Manual</a>**
* **<a href="modules/Readme.md">System Architecture</a>**
* Licensed under the **[MODIFIED MIT LICENSE](LICENSE)**

