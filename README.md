<br> 
 
<div align="center">
  <img alt="py-agent" src="logo.svg" height="125" />
  <h1>py-agent</h1>

  <p>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/version-v0.9.9.33.svg?variant=secondary" alt="Version"></a>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/Python.svg?variant=branded&brand=python" alt="Language"></a>
    <a href="https://github.com/j5onrf/py-agent"><img src="https://shieldcn.dev/badge/C%2B%2B.svg?variant=branded&brand=cplusplus" alt="C++"></a>
    <a href="https://github.com/j5onrf/py-agent/blob/main/LICENSE"><img src="https://shieldcn.dev/badge/license-MIT-green.svg" alt="License"></a>
    <a href="https://shieldcn.dev/badge/status-beta-blue.svg"><img src="https://shieldcn.dev/badge/status-beta-blue.svg" alt="Status"></a>
  </p>

<br>

---

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
        <code>Nex-N2.5-mini</code> &nbsp;•&nbsp; <code>KAT-Coder-V2.5</code><br>
        <code>Qwen3.8-27B</code> &nbsp;•&nbsp; <code>Qwen3.6-35B*</code><br> <code>Ornith/Tiel</code> &nbsp;•&nbsp;
        <code>Qwen3.8-Flash-Next</code> <br> <code>DeepSeek&#8209;V4.1</code>
      </td>
    </tr>
  </table>
  
  <p>
    <sub>* Models &nbsp;•&nbsp; Run <code>model select</code> in your terminal to switch models</sub>
  </p>

  <br>

  <p>
    <sub><b>Cloud & Community Spaces:</b> Official <a href="https://huggingface.co">Hugging Face Router</a> endpoints<br>(<a href="https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash"><code>DeepSeek-V4.1-Flash</code></a>, <a href="https://huggingface.co/zai-org/GLM-5.3-Flash"><code>GLM-5.3-Flash</code></a>, <a href="https://huggingface.co/inclusionAI/Ling-3.0-flash-VL"><code>Ling-3.0-flash-VL</code></a>, and <a href="https://huggingface.co/moonshotai/Kimi-K3"><code>Kimi-K3</code></a>).</sub>
  </p>
</div>

<br>

---

<h2 align="center">Execution Surfaces</h2>

<div align="center">
  <table>
    <thead>
      <tr>
        <th align="left">Mode</th>
        <th align="center">Command</th>
        <th align="left">Operational Scope & Capabilities</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>⚡ <b>Direct Shell</b></td>
        <td align="center"><code>&lt;shortcut&gt;</code></td>
        <td>Sub-millisecond intent matching <a href="ai-context.md"><code>ai-context.md</code></a>.</td>
      </tr>
      <tr>
        <td>💬 <b>Single Query</b></td>
        <td align="center"><code>ai "&lt;query&gt;"</code></td>
        <td>Fast Single Response/Call streamed directly.</td>
      </tr>
      <tr>
        <td>🧠 <b>Multi-Turn Chat</b></td>
        <td align="center"><code>ai</code></td>
        <td>Interactive chat with persistent memory.</td>
      </tr>
      <tr>
        <td>🛠️ <b>Workspace Agent</b></td>
        <td align="center"><code>ai init [path]</code></td>
        <td>Codebase index-map, file editing (<code>edit_file</code>), tools and loops.</td>
      </tr>
      <tr>
        <td>🌐 <b>llama.cpp WebAgent</b></td>
        <td align="center"><code>/webui</code></td>
        <td>Tool-enabled web gateway on official <code>llama-server</code> UI. </td>
      </tr>
    </tbody>
  </table>
</div>

<br>

---

<h2 align="center">Sub-27B Model Tuning</h2>

<div align="center">
  <p>
    <b>Scope to Single Tasks:</b> Focus on 1 file or objective per turn for maximum accuracy.<br>
    <b>Use Native Tools (<code>Py: OFF</code>):</b> Small models are fastest with the 6 native tools (<code>SMOL_TOOLS</code>).
  </p>

  <br>

  <table>
    <thead>
      <tr>
        <th align="left">Benchmark Challenge</th>
        <th align="center">Without Adapters</th>
        <th align="center">With <code>/adp</code> Active</th>
        <th align="left">Efficiency Gain</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><b>AG-03 (Surgical Edit & Test)</b></td>
        <td align="center">16 turns</td>
        <td align="center"><b>6 turns</b></td>
        <td><b>62% fewer turns</b> (eliminates diff-retry loops)</td>
      </tr>
      <tr>
        <td><b>AG-07 (In-Memory Batch Loop)</b></td>
        <td align="center">14 turns</td>
        <td align="center"><b>2 turns</b></td>
        <td><b>85% fewer turns</b> (executes batch script on Turn 1)</td>
      </tr>
      <tr>
        <td><b>Full Suite Pass Rate</b></td>
        <td align="center">Retries / Failures</td>
        <td align="center"><b>100% (7/7)</b></td>
        <td><b>Zero unhandled syntax or format failures</b></td>
      </tr>
    </tbody>
  </table>

  <br>

  <p>
    <sub><b>Why it matters:</b> Sub-27B models often emit malformed JSON, markdown code blocks, or broken import syntax.<br>
    <code>/adp</code> heals these out-of-band, preventing wasted multi-turn recovery cycles.</sub>
  </p>
</div>

<br>

---

<h2 align="center">Efficiency Benchmark: Py-Agent & DeepSeek (dsh)</h2>

<div align="center">
  <table>
    <thead>
      <tr>
        <th align="left">Operational Tier</th>
        <th align="center">Py-Agent</th>
        <th align="center">DeepSeek (<code>dsh</code>)</th>
        <th align="left">Comparison & Capabilities</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><b>Pure Chat</b></td>
        <td align="center"><b>211 tokens</b> (<code>ai</code>)</td>
        <td align="center">~450+ tokens</td>
        <td>Conversational Q&A with confirmation cmd gates.</td>
      </tr>
      <tr>
        <td><b>Native Core</b></td>
        <td align="center"><b>~680 tokens</b> (<code>SMOL_TOOLS</code>)</td>
        <td align="center">~632 tokens</td>
        <td><b>True parity.</b> Surgical file edits, code search & shell verification.</td>
      </tr>
      <tr>
        <td><b>Dual Mode</b></td>
        <td align="center"><b>~760 tokens</b> (<code>python + native</code>)</td>
        <td align="center">~1,200+ tokens</td>
        <td><b>~40% fewer tokens.</b> In-memory testing + deterministic edits with <b>~95% cache hits</b>.</td>
      </tr>
      <tr>
        <td><b>Full Graph</b></td>
        <td align="center"><b>~1,100 tokens</b> (11 tools + AST)</td>
        <td align="center">2,500–4,000+ tokens</td>
        <td><b>Up to 3x fewer tokens.</b> Complete relational SQLite FTS5 symbol & impact graph.</td>
      </tr>
      <tr>
        <td><b>Idle Footprint</b></td>
        <td align="center"><b>0% CPU / 0 MB RAM</b></td>
        <td align="center">Node.js Active</td>
        <td>Standard Python execution; no background daemons or idle processes.</td>
      </tr>
    </tbody>
  </table>

  <br>

  <p>
    <sub><b>Tiers:</b> Pure Chat (<code>ai</code>, 211t) • Native Mode (6 tools, ~680t) • Dual Mode (7 tools, ~760t) • Index-Map (11 tools, ~1.1kt) <br> OKF Memory (<code>.agent/memory/*.md</code>) 1-shot <code>/hs</code> retrospective audits.</sub>
  </p>
</div>

<br>

---

<h2 align="center">CLI Launch Interface</h2>

<div align="center">
  <p><sub>Customize box themes with <code>/box [1-8]</code>. For detailed workflows, read the <a href="projects/Readme.md"><b>Workspace Manual</b></a>.</sub></p>
</div>

```console
~ ❯ ai
╭─  ∿ Py Agent  ────────────────────╮
│     model:  Qwen3.6-35B-A3B.gguf  │
│ directory:  ~                     │
│   profile:  chat                  │
│  database:  stateless             │
╰────────────────── Ctrl+C to exit ─╯

❯ █
```

<br>

---

<h2 align="center">Client Surfaces & Environments</h2>

<p align="center">
  Py-Agent is surface-agnostic. Switch seamlessly between the terminal, web gateway, and desktop IDE:
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
# 1. Install system dependencies & clone
sudo pacman -S python-rich python-requests
git clone https://github.com/j5onrf/py-agent.git ~/.config/py-agent

# 2. Register shell hook (bash / zsh)
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

### 3. Optional Client Surfaces

<div align="center">
  <table>
    <thead>
      <tr>
        <th align="left">Surface</th>
        <th align="center">Setup / Command</th>
        <th align="left">System Requirements</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><b>Desktop IDE (<a href="https://github.com/j5onrf/pycode">PyCode</a>)</b></td>
        <td align="center"><code>install-pycode</code></td>
        <td>Node.js 20+, pnpm</td>
      </tr>
      <tr>
        <td><b>Textual PyTUI</b></td>
        <td align="center"><code>sudo pacman -S python-textual python-uvloop</code></td>
        <td>uvloop (zero C-extension RAG dependencies)</td>
      </tr>
      <tr>
        <td><b>Voice-to-Text Bridge</b></td>
        <td align="center"><code>/v</code> (or <code>/v auto</code> on <code>:9999</code>)</td>
        <td><code>wtype</code>, <code>openssl</code>, and <code>GEM_VOICE</code> in <code>.env</code></td>
      </tr>
      <tr>
        <td><b>Neural Kokoro TTS</b></td>
        <td align="center"><code>/tts</code></td>
        <td><code>yay -S koko-bin pw-play wl-clipboard</code></td>
      </tr>
    </tbody>
  </table>
</div>

<br>

---

<h2 align="center">Roadmap to v1.0.0</h2>

- [x] **Modular Sub-27B Adapters & Self-Healing Parser:** Dedicated `agent_adapters.py` handling Hermes XML, DSML, Mistral, and raw function call extraction (`/adp`) for small quantized models.
- [x] **3-Zone Context Compactor with Progress Anchor:** Pi-inspired context compaction (`/com`) preserving completed milestone summaries across context purges.
- [x] **Google Search Grounding (/gnd):** Live web grounding via Gemini Search tool with automatic DuckDuckGo keyless fallback across CLI, TUI, WebUI, and PyCode.
- [x] **Zero-Trust Hardened Containment:** Non-bypassable interactive `[Y/n]` fallback gate for out-of-bounds access and package management tools (`pip`, `pacman`, `sudo`).
- [x] **Full-Stack Agentic Benchmark Suite:** 7-test `eval-stack` measuring tool accuracy, AST resilience, and turn efficiency (Par).
- [ ] **PyBot Integration ([AkeruBot](https://github.com/opencoredev/akeru-bot) Plugin):** Embedded web assistant & customizable agent widget plugin.
- [ ] **v1.0.0 Production Release Tag!**

<br>

---

<h2 align="center">Documentation & License</h2>

* **<a href="projects/Readme.md">Workspace & Session Manual</a>**
* **<a href="modules/Readme.md">System Architecture</a>**
* **License**: Licensed under the permissive [MODIFIED MIT LICENSE](LICENSE)
* **Community:** Contributions are always welcome!


