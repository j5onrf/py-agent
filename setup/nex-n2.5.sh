#!/usr/bin/env bash

# ==========================================
# Nex-N2.5-mini APEX-I-Compact (Agent Config)
# ==========================================
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="/home/user/models/Nex-N2.5-mini-APEX-I-Compact.gguf"
ALIAS="Nex-N2.5-mini"
LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/server.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

# --- Logging Toggle ---
# Set to 'true' to enable server.log, 'false' to discard output to /dev/null
ENABLE_LOG="${ENABLE_LOG:-true}"

if [ "$ENABLE_LOG" = true ]; then
    mkdir -p "$LOG_DIR"
    LOG_TARGET="$LOG_FILE"
else
    LOG_TARGET="/dev/null"
fi

# Optional Vision Projector (uncomment if downloaded for multimodal agent tasks)
# MMPROJ_PATH="/home/user/models/mmproj-Nex-N2.5-mini-Q8_0.gguf"

# 1. Clean up lingering port processes
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
elif [ -f /usr/lib/libjemalloc.so ]; then
    export LD_PRELOAD=/usr/lib/libjemalloc.so
fi
export OMP_PROC_BIND=CLOSE
export OMP_PLACES=cores

# 4. Remove memory locking ceiling
ulimit -l unlimited 2>/dev/null

# ==========================================
# 5. Launch llama-server
# ==========================================
SERVER_ARGS=(
  -m "$MODEL_PATH"
  --alias "$ALIAS"
  --host "$HOST"
  --port "$PORT"
  
  # Context & Concurrency
  # Hybrid 3:1 SSM/Attention uses 75% less KV cache; 16k is safe on RAM
  -c 16384
  -np 1
  
  # Threading & Batching
  -t "$CORE_COUNT"
  -tb "$CORE_COUNT"
  -b 512
  -ub 256
  
  # Engine & Memory Strategy (Native f16 KV cache for full CPU SIMD speed)
  --flash-attn on
  --load-mode mlock
  --warmup
  --no-ui
  
  # Agent Template & Adaptive Reasoning
  --jinja
  --chat-template-kwargs '{"reasoning_effort":"medium"}'
  --reasoning on
  --reasoning-format auto
  --reasoning-preserve
  
  # Official Nex-AGI Agent Baseline Sampling
  --temp 0.7
  --top-p 0.95
  --top-k 40
  --min-p 0.05
  --repeat-penalty 1.0
)

# Attach vision projector if present
if [ -n "$MMPROJ_PATH" ] && [ -f "$MMPROJ_PATH" ]; then
  SERVER_ARGS+=(--mmproj "$MMPROJ_PATH")
fi

LAUNCH_PREFIX=""
if command -v uwsm >/dev/null 2>&1; then
    LAUNCH_PREFIX="uwsm app --"
fi

exec $LAUNCH_PREFIX $PIN_CMD "$LLAMA_SERVER_BIN" "${SERVER_ARGS[@]}" >> "$LOG_TARGET" 2>&1
