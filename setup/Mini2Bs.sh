#!/usr/bin/env bash

# ==========================================
# MiniCPM5-2B Speculative Decoding Engine (Tuned DSpark)
# ==========================================
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="/home/user/models/MiniCPM5-2B-Q4_K_M.gguf"
DRAFT_PATH="/home/user/models/MiniCPM5-2B-DSpark-Q8_0.gguf"
ALIAS="MiniCPM5-2B-DSpark"

LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/server.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

mkdir -p "$LOG_DIR"

# 1. Clean up lingering instances on port 8080
pkill -9 -x llama-server 2>/dev/null
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null
fi
sleep 0.5

# 2. Extract Physical Core IDs (bypasses SMT / Hyper-Threading)
PHYSICAL_CORES=$(lscpu -p=CPU,CORE 2>/dev/null | grep -v '^#' | sort -u -k2,2 -t, | cut -d, -f1 | paste -sd, -)
if [ -n "$PHYSICAL_CORES" ]; then
    PIN_CMD="taskset -c $PHYSICAL_CORES"
    CORE_COUNT=$(echo "$PHYSICAL_CORES" | tr ',' '\n' | wc -l)
else
    PIN_CMD=""
    CORE_COUNT=$(nproc)
fi

# 3. Allocator and Thread Binding (CachyOS x86-64-v4 mimalloc)
if [ -f /usr/lib/libmimalloc.so ]; then
    export LD_PRELOAD=/usr/lib/libmimalloc.so
fi
export OMP_PROC_BIND=CLOSE
export OMP_PLACES=cores

# 4. Remove memory locking ceiling
ulimit -l unlimited 2>/dev/null

# ==========================================
# 5. Server & Speculative Engine Launch
# ==========================================
SERVER_ARGS=(
  -m "$MODEL_PATH"
  --alias "$ALIAS"
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
  --reasoning-preserve
  --reasoning on
  --reasoning-format auto

  # --- Sampler Alignment for Speculative Decoding ---
  # Remove heavy presence/repeat penalties that cause draft mismatches
  --temp 0.2
  --top-p 0.95
  --repeat-penalty 1.05

  # --- DSpark Speculative Settings ---
  -md "$DRAFT_PATH"
  --spec-type draft-dspark
  --spec-draft-n-max 5
)

# Launch wrapped in UWSM with physical core affinity
exec uwsm app -- $PIN_CMD "$LLAMA_SERVER_BIN" "${SERVER_ARGS[@]}" >> "$LOG_FILE" 2>&1
