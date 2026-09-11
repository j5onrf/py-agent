#!/usr/bin/env bash

# ==============================================================================
# Ling-3.0-tiny High-Throughput CPU Launcher (7.9B-A1.3B MoE)
# ==============================================================================
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="${MODEL_PATH:-/home/user/models/Ling-3.0-tiny-abliterated-APEX-I-Compact.gguf}"
ALIAS="Ling-3.0-tiny"

LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/server_ling.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

mkdir -p "$LOG_DIR"

# 1. Clean up lingering server instances
pkill -9 -x llama-server 2>/dev/null
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null
elif command -v lsof >/dev/null 2>&1; then
    TARGET_PID=$(lsof -t -i :"$PORT")
    [ -n "$TARGET_PID" ] && kill -9 "$TARGET_PID" 2>/dev/null
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

# ==============================================================================
# 5. Server Launch
# ==============================================================================
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
  --temp 0.3
  --top-p 0.90
  --min-p 0.05
  --repeat-penalty 1.05
)

# Launch wrapped in UWSM with physical core affinity
exec uwsm app -- $PIN_CMD "$LLAMA_SERVER_BIN" "${SERVER_ARGS[@]}" >> "$LOG_FILE" 2>&1
