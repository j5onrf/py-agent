# Local Server Configuration & Model Selector (Universal CPU & GPU)

* **Verified Backend:** `llama.cpp` (Build `10125` / Commit `720d7fa40`)
* **Compilation Targets:** Native `x86-64-v4` / `AVX-512` / `AVX2` (CPU) | `CUDA` / `ROCm` / `Metal` (GPU)

---

## 1. Model Fleet & Agent Reliability Tiers

> **Core Philosophy:** Models under **27B** parameters are strictly designated for instant interactive chat, intent classification, or single-shot tool execution. Autonomous, multi-step developer agents with self-correction and test loops require **27B+ dense** or **35B+ MoE** architectures.

| Tier | Example Models | Reliability & Use Case | Recommended Hardware Target |
| :--- | :--- | :--- | :--- |
| **Chat & Single-Task (< 27B)** | `Qwen3.5-2B+`<br>`LFM2.5-8B-A1B` | **Instant Chat & Single Actions:** Sub-second queries, quick shell formatting, fast intent routing, conversational Q&A. *Not recommended for multi-step agent loops.* | CPU (Low-Power / Chill) or Entry GPU |
| **Developer Agent (≥ 27B / MoE)** | `Qwen3.8-27B`<br>`Qwen3.6-35B-A3B` | **Autonomous Engineering Agents:** Multi-file code inspection, test suites, surgical diffing (`edit_file`), and closed-loop verification. | High-RAM CPU (Physical Cores) or 16GB+ VRAM GPU |

---

## 2. Universal Server Launcher (`server-launch.sh`)

This universal script handles dynamic physical core detection, preloads thread-local memory allocators (`mimalloc`), unlocks kernel memory pinning, and provides a single toggle between **CPU-only** and **GPU offloading**.

```bash
#!/usr/bin/env bash

# ==========================================
# 1. Configuration & Mode Selection
# ==========================================
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="${MODEL_PATH:-$HOME/models/model.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-local-model}"
LOG_DIR="${LOG_DIR:-$HOME/models/serv}"
LOG_FILE="$LOG_DIR/server.log"
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-$HOME/llama.cpp/build/bin/llama-server}"

# GPU Offload: Set to 0 for CPU-only, or 99 (or layer count) for GPU
GPU_LAYERS=0

mkdir -p "$LOG_DIR"

# ==========================================
# 2. Process Cleanup
# ==========================================
if command -v lsof >/dev/null 2>&1; then
    TARGET_PID=$(lsof -t -i :"$PORT")
    if [ -n "$TARGET_PID" ]; then
        kill -15 "$TARGET_PID" 2>/dev/null || kill -9 "$TARGET_PID" 2>/dev/null
        sleep 0.5
    fi
fi

# ==========================================
# 3. Dynamic Hardware & Memory Optimization
# ==========================================
# Extract physical CPU cores (bypasses SMT / Hyper-Threading to eliminate cache thrashing)
PHYSICAL_CORES=$(lscpu -p=CPU,CORE 2>/dev/null | grep -v '^#' | sort -u -k2,2 -t, | cut -d, -f1 | paste -sd, -)
if [ -n "$PHYSICAL_CORES" ]; then
    CORE_COUNT=$(echo "$PHYSICAL_CORES" | tr ',' '\n' | wc -l)
    PIN_CMD="taskset -c $PHYSICAL_CORES"
else
    CORE_COUNT=$(nproc)
    PIN_CMD=""
fi

# Preload mimalloc or jemalloc if installed (drastically cuts allocation latency)
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
# 4. Launch llama-server
# ==========================================
exec $PIN_CMD "$LLAMA_SERVER_BIN" \
  -m "$MODEL_PATH" \
  --alias "$MODEL_ALIAS" \
  --host "$HOST" \
  --port "$PORT" \
  -ngl "$GPU_LAYERS" \
  -c 8192 \
  -np 1 \
  -t "$CORE_COUNT" \
  -tb "$CORE_COUNT" \
  -b 512 \
  -ub 512 \
  --flash-attn on \
  --load-mode mlock \
  --warmup \
  --no-ui \
  --reasoning on \
  --reasoning-format auto \
  --reasoning-budget-message "\n" \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --context-shift \
  --jinja \
  --temp 0.2 \
  --top-k 80 \
  --top-p 0.90 \
  --min-p 0.05 \
  --repeat-penalty 1.05 \
  --presence-penalty 0.1 \
  --repeat-last-n -1 >> "$LOG_FILE" 2>&1
```

---

## 3. Hardware Execution Strategies

### CPU-Only High-Throughput Mode
* **SMT Bypass (`taskset`):** Prevents hyper-threaded logical cores from competing for vector ALUs and L1/L2 caches.
* **Flash Attention (`--flash-attn on`):** Tiled attention in vector registers (AVX-512 / AVX2) reduces RAM read/write traffic during prompt prefill.
* **Native `f16` KV Cache:** When sufficient RAM is available, native `f16` avoids the runtime CPU dequantization latency of `q8_0`.
* **Zero-Swap Physical RAM Locking (`--load-mode mlock`):** Ensures large 27B–35B models stay pinned in memory with zero kernel page-swapping.

### GPU Acceleration Mode
To run fully or partially on GPU:
1. Set `GPU_LAYERS=99` in the launcher script.
2. For memory-constrained GPUs, quantize the KV cache to fit large context windows:
   ```bash
   --cache-type-k q8_0 \
   --cache-type-v q8_0 \
   ```

---

## 4. System Memory Locking Configuration (Linux)

To ensure `--load-mode mlock` succeeds without permission errors:

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
*(Apply by logging out and back in, or rebooting).*

---

## 5. Developer Agent Protocol (`~/.config/py-agent/skills/profiles/`)

For autonomous developer workflows running on 27B+ models, use this standardized 5-tool lean profile:

```markdown
---
description: "Universal Developer Agent (Anti-Loop / 5-Tool Whitelist)"
map: false
---
# Autonomous Engineering System Prompt
Lead software engineer operating directly on the local workspace.

## Allowed Tools (Strict 5-Tool Whitelist):
- `read_file`: Inspect file contents.
- `list_dir`: List directory files.
- `write_file`: Create BRAND NEW files only.
- `edit_file`: Surgically insert or modify code in existing files.
- `run_command`: Run shell commands, tests, or builds.
*Do NOT attempt to call unlisted tools.*

## Execution Rules:
1. **Modifications:** For existing files, ALWAYS use `edit_file` to apply small diffs. Do NOT dump entire files into `write_file`.
2. **Anti-Looping:** When a command or test suite succeeds (`OK`, `exit 0`), NEVER rerun it. Stop immediately and output the final summary.
3. **Paths:** Always use relative paths from the workspace root (`.`, `src/app.py`).
4. **Imports:** When adding new functions, update test and caller `import` statements.
```

---

## 6. Verification & Health Commands

```bash
# 1. Verify memory locking ceiling
ulimit -l -H
# Expected: unlimited

# 2. Check if mimalloc is actively managing heap allocations
cat /proc/$(pgrep -x llama-server)/maps | grep -E "mimalloc|jemalloc"

# 3. Check memory headroom and swap status
free -h

# 4. View real-time server throughput and prefix cache hits
tail -f /path/to/server.log
```

---

## 7. Client Controls (`ai`)

* `/t [N]` — Set reasoning token budget (e.g., `/t 500` for deep architectural planning).
* `/t` — Toggle deep reasoning on/off for instant conversational responses.
* `/t show` / `/t hide` — Toggle internal thinking trace visibility in the terminal.
* `/clear` — Clear the active session context.
