# Local Server Configuration (Reasoning & Tool Models)

* **Verified Backend:** `llama.cpp` (Build `10125` / Commit `720d7fa40`)
* **Compilation Target:** Native CachyOS `x86-64-v4` (AVX-512, VNNI, F16C) via `GNU 16.1.1`
* **Supported Models:** Qwen Base GGUF Series (2B, 35B)

This directory contains deployment scripts and process management tools for `llama-server`. The configuration supports dynamic, per-request thinking toggles (`/t <tokens>`) without splitting VRAM or restarting server instances.

---

## 1. Server Configuration (`example-server.sh`)

To support client-side reasoning overrides (`/t`) while keeping background tools and standard queries instant, launch `llama-server` with the following flag combination:

```bash
  --reasoning on \
  --reasoning-format auto \
  --reasoning-budget-message "\n" \
  --chat-template-kwargs '{"enable_thinking":false}' \
```

### Flag Explanations
* **`--reasoning on`**: Enables the internal reasoning pipeline inside `llama-server`.
* **`--reasoning-format auto`**: Allows `llama-server` to automatically detect `<think>...</think>` tags for Qwen and DeepSeek models without forcing incorrect template parsers.
* **`--reasoning-budget-message "\n"`**: Injects a clean newline transition when a client's thinking token budget is reached. This prevents text leaks into chat output and stops reasoning loops.
* **`--chat-template-kwargs '{"enable_thinking":false}'`**: **(Critical)** Sets the default server state to **Thinking OFF**. Standard queries, skills, and background agent tools (`read_file`, `write_file`, `run_command`) execute immediately with zero latency.
* *Note on `--reasoning-budget`*: Hardcoded server budgets are omitted so that client API payloads dynamically control token limits (e.g., `/t 500` or `/t off`).

---

## 2. GPU Acceleration & WebUI Setup

### GPU Layer Offloading
To offload computation to an NVIDIA GPU via CUDA, add the `-ngl` (number of GPU layers) parameter:
```bash
  -ngl 99 \  # Offloads all model layers to VRAM
```

### Accessing the Web UI
To use the embedded `llama.cpp` web interface in your browser, **remove** the following line from your server launcher script:
```bash
  --no-ui \
```
Once removed, access the web playground at `http://localhost:8080`.

---

## 3. Interactive TUI Selector (`model-select-local.py`)

A terminal interface used to switch active local GGUF models, flush system memory, and launch backend server scripts.

### Features
* **Active Status Detection:** Scans port 8080 processes to report which model is currently loaded.
* **Process Cleanup:** Gracefully terminates active instances (`SIGTERM` / `SIGKILL`) and flushes system memory.
* **Detached Execution:** Spawns `llama-server` in independent process groups (`start_new_session=True`), keeping the backend running after exiting the selector.

### Configuration
Update the paths inside `model-select-local.py` to match your local setup:

```python
MODELS_DIR = "/home/user/models"
SERV_DIR = "/home/user/models/serv"

LOCAL_MODELS = [
    {"name": "Qwen 3.5 2B", "file": "Qwen3.5-2B.gguf", "script": "q2b.sh"},
    {"name": "Qwen 3.6 35B", "file": "Qwen3.6-35B.gguf", "script": "q35b.sh"},
]
```

---

## 4. Two-Layer Harness & Small Model Optimization (`ai-context.md`)

Pairing the Python agent harness and its intent blueprint (`ai-context.md`) with lightweight 1B/2B models (e.g., `minicpm5-1b-agentic-tooluse.gguf` or `Qwen3.5-2B.gguf`) enables **sub-second desktop automation** (`0.14s – 0.5s`) with zero tool hallucination.

### Architecture Division
* **Layer 1 (Smart Harness):** The Python client uses `ai-context.md` to deterministically map plain-English intents (`"---> weather"`, `"---> system health"`, `"---> time"`) directly to local bash scripts and system utilities.
* **Layer 2 (Lightweight LLM Engine):** Small 1B/2B models serve as rapid, low-overhead decision formatters that process harness tool outputs at **40–165+ tokens/sec**.

> **Workflow Rule:** Lightweight 1B/2B models remain always-on in the background for sub-second system automation, while heavy models (35B) are loaded on-demand via `model-select-local.py` for complex architecture and deep reasoning (`/t`).

---

## 5. Quickstart

1. **Launch the TUI Model Selector:**
   ```bash
   ./model-select-local.py
   ```
   * Use **▲/▼ Arrows** to select a model and press **Enter** to launch.
   * Select **Unload All Local Models** to completely free system RAM/VRAM.

2. **Control Thinking in Agent Terminal (`ai`):**
   * `/t 500` - Enable deep reasoning with a 500-token thinking budget.
   * `/t off` - Disable reasoning for instant tool execution and fast chat.
