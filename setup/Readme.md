# Local Server Configuration & Model Selector (Universal CPU & GPU)

* **Verified Backend:** `llama.cpp` (Build `10300+` / Native Master with `draft-dspark` & `draft-dflash` support)
* **Compilation Targets:** Native Host Extensions (CPU) | `CUDA` / `ROCm` / `Metal` (GPU)
* **Memory Allocator:** Thread-local allocator (`mimalloc` / `jemalloc`)

---

## 1. Model Fleet & Agent Reliability Tiers

> **Core Philosophy:** Smaller models are designated for interactive conversational queries, intent routing, and single-shot execution. Autonomous engineering agents with test-execution loops and self-correction require larger dense or MoE architectures.

| Tier | Example Models | Reliability & Use Case | Recommended Hardware Target |
| :--- | :--- | :--- | :--- |
| **Interactive & Chat (< 27B)** | `MiniCPM5-2B`<br>`Qwen3.5-2B`<br>`LFM2.5-8B` | **Interactive Chat & Single Actions:** Rapid queries, shell formatting, intent routing, conversational Q&A. *Not recommended for multi-step agent loops.* | CPU or Entry GPU |
| **Developer Agent (≥ 27B / MoE)** | `Qwen3.8-27B`<br>`Qwen3.6-35B` | **Autonomous Engineering Agents:** Multi-file code inspection, test suites, surgical diffing (`edit_file`), closed-loop verification. | High-RAM CPU or High-VRAM GPU |

---

## 2. Universal Server Launcher (`server-launch.sh`)

This script handles process reclamation, physical core affinity (`taskset`), memory locking (`mlock`), non-deprecated reasoning arguments, and configurable speculative decoding.

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
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-llama-server}"

# Speculative Acceleration Options:
# - "dspark": Dedicated draft model
# - "ngram": Context-based n-gram acceleration
# - "none": Standard non-speculative inference
SPEC_MODE="${SPEC_MODE:-none}"
DRAFT_MODEL_PATH="${DRAFT_MODEL_PATH:-$MODELS_DIR/draft-model.gguf}"

# GPU Offload: 0 for CPU-only, or target layer count for GPU
GPU_LAYERS=0

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
# 3. Memory & Core Optimization
# ==========================================
# Isolate physical cores to avoid logical hyper-threading competition
PHYSICAL_CORES=$(lscpu -p=CPU,CORE 2>/dev/null | grep -v '^#' | sort -u -k2,2 -t, | cut -d, -f1 | paste -sd, -)
if [ -n "$PHYSICAL_CORES" ]; then
    CORE_COUNT=$(echo "$PHYSICAL_CORES" | tr ',' '\n' | wc -l)
    PIN_CMD="taskset -c $PHYSICAL_CORES"
else
    CORE_COUNT=$(nproc)
    PIN_CMD=""
fi

# Preload thread-local allocator if available
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
# 4. Server Arguments & Speculative Configuration
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
  --min-p 0.05
  --repeat-penalty 1.05
)

# Optional GPU offloading
if [ "$GPU_LAYERS" -gt 0 ]; then
  SERVER_ARGS+=(-ngl "$GPU_LAYERS")
fi

# Attach speculative decoding configuration
case "$SPEC_MODE" in
  dspark)
    SERVER_ARGS+=(
      -md "$DRAFT_MODEL_PATH"
      --spec-type draft-dspark
      --spec-draft-n-max 5
    )
    ;;
  ngram)
    SERVER_ARGS+=(
      --spec-type ngram-mod
      --spec-draft-n-max 10
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

## 3. Speculative Decoding Strategies

### Strategy A: Neural Drafting (`draft-dspark`)
* **Use Case:** Small, compatible model architectures paired with dedicated draft weights.
* **Mechanism:** A lightweight companion draft model predicts candidate tokens in advance. The base model evaluates these candidates in parallel during a single batched verification pass.
* **Configuration:** Set `--spec-draft-n-max` to match or stay below the model's trained draft window block size. Keep sampling penalties minimal to avoid distribution mismatches between the base and draft models.

### Strategy B: Context N-Gram (`ngram-mod`)
* **Use Case:** Coding tasks, structured formats (JSON/YAML), and large models where running a secondary draft model is inefficient.
* **Mechanism:** Uses a token hash table from prior context and prompt history to suggest recurring syntax patterns, keywords, and variable names.
* **Benefits:** Requires no additional model files or memory overhead. If no context match is found, it evaluates normally with no rejection penalty.

---

## 4. Execution Strategies

### CPU Optimization
* **SMT Bypass (`taskset -c`):** Limits execution to physical cores, preventing logical threads from competing for vector compute units and L1/L2 caches.
* **Flash Attention (`--flash-attn on`):** Computes attention in tiled chunks, reducing memory bandwidth pressure during context evaluation.
* **Memory Locking (`--load-mode mlock`):** Keeps active model weights pinned in physical memory to prevent OS page-swapping.
* **Reasoning Preservation (`--reasoning-preserve`):** Maintains thinking trace formatting across conversational turns without parsing errors.

### GPU Acceleration
To run fully or partially on GPU:
1. Set `GPU_LAYERS` to the target offload depth (or `99` for all layers).
2. For memory-constrained setups, compress the KV cache:
   ```bash
   --cache-type-k q8_0 \
   --cache-type-v q8_0
   ```

---

## 5. System Memory Locking Configuration (Linux)

To ensure `--load-mode mlock` succeeds without permission limits:

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

For autonomous coding workflows on larger models, use a focused tool whitelist:

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

## 7. Verification & Health Commands

```bash
# 1. Verify memory locking ceiling
ulimit -l -H
# Expected: unlimited

# 2. Check allocator integration
cat /proc/$(pgrep -x llama-server)/maps | grep -E "mimalloc|jemalloc"

# 3. Monitor memory usage and swap state
free -h

# 4. Follow server activity and generation logs
tail -f /path/to/server.log
```

---

## 8. Client Controls (`ai`)

* `/t` — Toggle reasoning on/off for instant conversational responses.
* `/t [N]` — Set reasoning token budget (e.g., `/t 500`).
* `/t show` / `/t hide` — Toggle internal thinking trace visibility in the output.
* `/clear` — Clear the active session history and reset context cache.
