# Local Server Configuration & Model Selector (CPU & GPU Ready)

* **Verified Backend:** `llama.cpp` (Build `10852+` / Native Master)
* **Compilation Targets:** Native Host Vector Extensions (AVX2 / AVX-512 / FMA) | GPU (`CUDA` / `Vulkan` / `ROCm`)
* **Memory Allocator:** Thread-local allocator (`mimalloc` on CachyOS x86-64-v4 / `jemalloc`)

---

## 1. Model Fleet & Agent Reliability Tiers

> **Core Philosophy:** Smaller models are designated for interactive conversational queries, intent routing, and single-shot execution. Autonomous engineering agents with test-execution loops and self-correction require larger dense or MoE architectures.

| Tier | Example Models | Reliability & Use Case | Recommended Hardware Target |
| :--- | :--- | :--- | :--- |
| **Interactive & Chat (< 27B)** | `MiniCPM5-2B`<br>`Qwen3.5-2B`<br>`LFM2.5-8B-A1B` | **Interactive Chat & Fast Routing:** Rapid queries, shell formatting, intent routing, conversational Q&A. *Not recommended for multi-step agent loops.* | 16–32 GB RAM or Entry GPU (8–12 GB VRAM) |
| **Developer Agent (≥ 27B / MoE)** | `Sage-A1.5-35B`<br>`Flint-40B-A2.5B`<br>`Qwen3.8-35B-Distill`<br>`KAT-Coder-V2.5`<br>`Tiel-Coder-35B` | **Autonomous Engineering Agents:** Multi-file code inspection, test suites, surgical diffing (`edit_file`), closed-loop verification. | 32–64+ GB RAM or 16–24 GB VRAM GPU |

---

## 2. Universal Server Launcher (`server-launch.sh`)

This script handles process cleanup, physical core pinning (`taskset`), memory locking ceiling removal (`mlock`), non-deprecated reasoning arguments, clean GPU layer offload toggling, and context n-gram / MTP acceleration.

```bash
#!/usr/bin/env bash

# ==========================================
# 1. Configuration & Mode Selection
# ==========================================
PORT=8080
HOST="127.0.0.1"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
MODEL_PATH="${MODEL_PATH:-$MODELS_DIR/model.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-local-model}"
LOG_DIR="${LOG_DIR:-$MODELS_DIR/serv}"
LOG_FILE="$LOG_DIR/server.log"
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-$HOME/llama.cpp/build/bin/llama-server}"

# --- Hardware Target ---
# Set to 0 for pure CPU RAM execution.
# Set to 99 (or layer count) for full/partial GPU offload.
GPU_LAYERS=0

# Speculative Acceleration Options:
# - "mtp": Native or external draft head speculation
# - "ngram": Context-based n-gram acceleration
# - "none": Standard non-speculative inference
SPEC_MODE="${SPEC_MODE:-none}"
MTP_DRAFT_PATH="${MTP_DRAFT_PATH:-$MODELS_DIR/mtp-draft.gguf}"

mkdir -p "$LOG_DIR"

# ==========================================
# 2. Process Cleanup
# ==========================================
pkill -9 -x llama-server 2>/dev/null
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null
elif command -v lsof >/dev/null 2>&1; then
    TARGET_PID=$(lsof -t -i :"$PORT")
    [ -n "$TARGET_PID" ] && kill -9 "$TARGET_PID" 2>/dev/null
fi
sleep 0.5

# ==========================================
# 3. CPU Core & Memory Optimization
# ==========================================
# Isolate physical cores to avoid logical hyper-threading (SMT) contention
PHYSICAL_CORES=$(lscpu -p=CPU,CORE 2>/dev/null | grep -v '^#' | sort -u -k2,2 -t, | cut -d, -f1 | paste -sd, -)
if [ -n "$PHYSICAL_CORES" ]; then
    CORE_COUNT=$(echo "$PHYSICAL_CORES" | tr ',' '\n' | wc -l)
    PIN_CMD="taskset -c $PHYSICAL_CORES"
else
    CORE_COUNT=$(nproc)
    PIN_CMD=""
fi

# Preload thread-local allocator if available (CachyOS x86-64-v4)
if [ -f /usr/lib/libmimalloc.so ]; then
    export LD_PRELOAD=/usr/lib/libmimalloc.so
elif [ -f /usr/lib/libjemalloc.so ]; then
    export LD_PRELOAD=/usr/lib/libjemalloc.so
fi

export OMP_PROC_BIND=CLOSE
export OMP_PLACES=cores

# Remove memory locking ceiling for physical RAM pinning
ulimit -l unlimited 2>/dev/null

# ==========================================
# 4. Server Arguments
# ==========================================
SERVER_ARGS=(
  -m "$MODEL_PATH"
  --alias "$MODEL_ALIAS"
  --host "$HOST"
  --port "$PORT"
  -c 8192
  -np 1
  -t "$CORE_COUNT"
  -tb "$CORE_COUNT"
  -b 512
  -ub 256
  --flash-attn on
  --load-mode mlock
  --warmup
  --no-ui
  --context-shift
  --jinja
  --reasoning on
  --reasoning-format auto
  --reasoning-preserve
  --temp 0.2
  --top-p 0.95
  --top-k 40
  --min-p 0.05
  --repeat-penalty 1.0
)

# Optional GPU offloading: Appends -ngl only if GPU_LAYERS is > 0
if [ "$GPU_LAYERS" -gt 0 ]; then
  SERVER_ARGS+=(-ngl "$GPU_LAYERS")
fi

# Speculative Decoding Configuration
case "$SPEC_MODE" in
  mtp)
    if [ -f "$MTP_DRAFT_PATH" ]; then
      SERVER_ARGS+=(-md "$MTP_DRAFT_PATH" --spec-draft-n-max 2)
    else
      # Integrated MTP self-decoding (e.g. Sage-A1.5 blk.40)
      SERVER_ARGS+=(--draft-max 2)
    fi
    ;;
  ngram)
    SERVER_ARGS+=(
      --spec-type ngram-mod
      --spec-draft-n-max 3
    )
    ;;
esac

# ==========================================
# 5. Launch llama-server
# ==========================================
LAUNCH_PREFIX=""
if command -v uwsm >/dev/null 2>&1; then
    LAUNCH_PREFIX="uwsm app --"
fi

exec $LAUNCH_PREFIX $PIN_CMD "$LLAMA_SERVER_BIN" "${SERVER_ARGS[@]}" >> "$LOG_FILE" 2>&1
```

---

## 3. Speculative Acceleration Strategies

### Strategy A: Multi-Token Prediction (`MTP`)
* **Use Case:** Models with integrated MTP layers (e.g., `Sage-A1.5`) or external companion draft heads (e.g., `Qwen3.8-35B-Distill`).
* **Mechanism:** Evaluates speculation heads directly to accelerate decode phases without full second-pass overhead.

### Strategy B: Context N-Gram (`ngram-mod`)
* **Use Case:** Coding tasks, structured diffs, JSON, and models without dedicated draft heads (e.g., `Flint-40B`).
* **Mechanism:** Uses a token hash table from existing context and history to propose recurring code syntax and keywords. Adds zero extra memory overhead and incurs no rejection penalty on mispredicts.

---

## 4. Execution Strategies & Hardware Tuning

### CPU Mode (`GPU_LAYERS=0`)
* **SMT Bypass (`taskset -c`):** Restricts worker threads to physical core IDs, ensuring threads never compete for vector registers (AVX-512/AVX2) and L1/L2 caches.
* **Flash Attention (`--flash-attn on`):** Evaluates attention in cache-resident blocks, reducing memory access overhead during prompt prefill.
* **Memory Locking (`--load-mode mlock`):** Locks model pages in physical RAM, preventing swapping under system memory pressure.

### GPU Mode (`GPU_LAYERS > 0`)
* **Layer Offloading (`-ngl`):** Set `GPU_LAYERS=99` to offload all transformer blocks to VRAM. For split/hybrid setups, specify the exact number of layers your VRAM can comfortably hold (e.g., `24` or `32`), leaving remaining layers to CPU RAM.
* **Flash Attention:** Utilizes native GPU tensor cores for attention calculation, significantly accelerating prefill on long contexts.

### Agent Repetition Strategy
* **Repetition Penalty for Coding Agents (`--repeat-penalty 1.0`):** Penalties above `1.02` degrade agent performance by penalizing valid repeated syntax, indentations, and tool tags (`<tool_call>`). Keep disabled or at `1.0`.

---

## 5. System Memory Locking Configuration (Linux)

To ensure `--load-mode mlock` operates without hitting ceilings:

```bash
# 1. Set PAM limits
sudo mkdir -p /etc/security/limits.d
sudo tee /etc/security/limits.d/99-memlock.conf << 'EOF'
* soft memlock unlimited
* hard memlock unlimited
EOF

# 2. Set systemd user manager session limits
sudo mkdir -p /etc/systemd/user.conf.d /etc/systemd/system.conf.d
sudo tee /etc/systemd/user.conf.d/memlock.conf /etc/systemd/system.conf.d/memlock.conf << 'EOF'
[Manager]
DefaultLimitMEMLOCK=infinity
EOF
```

---

## 6. Developer Agent Protocol (`~/.config/py-agent/skills/profiles/`)

Autonomous coding agent prompt for larger MoE models:

```markdown
---
description: "Universal Developer Agent (Anti-Loop / 5-Tool Whitelist)"
map: false
---
# Autonomous Engineering System Prompt
Lead software engineer operating directly on the local workspace.

## Allowed Tools:
- `read_file`: Inspect file contents.
- `list_dir`: List directory files.
- `write_file`: Create brand-new files only.
- `edit_file`: Surgically insert or modify code in existing files.
- `run_command`: Run shell commands, tests, or builds.
*Do NOT attempt to call unlisted tools.*

## Execution Rules:
1. **Modifications:** For existing files, ALWAYS use `edit_file` to apply minimal diffs. Do NOT overwrite entire files with `write_file`.
2. **Anti-Looping:** When a command or test suite succeeds, conclude the task and summarize the changes.
3. **Paths:** Always use relative paths from the workspace root (`.`, `src/app.py`).
4. **Imports:** When adding new functions, update corresponding imports and callers.
```

---

## 7. Verification Commands

```bash
# Verify unlimited memory locking ceiling
ulimit -l -H

# Check allocator attachment
cat /proc/$(pgrep -x llama-server)/maps | grep -E "mimalloc|jemalloc"

# Monitor memory usage
free -h

# Stream server activity
tail -f ~/models/serv/server.log
```

---

## 8. Client Controls (`ai`)

* `/t` — Toggle reasoning on/off for immediate responses.
* `/t [N]` — Set reasoning token budget (e.g., `/t 500`).
* `/t show` / `/t hide` — Toggle internal thinking trace display.
* `/clear` — Clear context cache and reset conversation state.
