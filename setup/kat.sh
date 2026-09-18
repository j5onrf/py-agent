#!/usr/bin/env bash

# ==============================================================================
# KAT-Coder-V2.5-Dev APEX-I (Dual Preset: Agent vs. Creative)
# Launched exclusively via model-select-local.py
# ==============================================================================

# --- Hardware & Path Configuration ---
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="/home/user/models/KAT-Coder-V2.5-Dev-APEX-I-Compact.gguf"
ALIAS="KAT-Coder-V2.5-Dev"

LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/kat-server.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

# ==============================================================================
# Static Toggles (Edit directly here)
# ==============================================================================
ENABLE_NGRAM=false   # true: enable N-gram acceleration | false: pure decode
ENABLE_LOG=false     # true: write to kat-server.log   | false: live output

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
fi
export OMP_PROC_BIND=CLOSE
export OMP_PLACES=cores

# 4. Remove memory locking ceiling
ulimit -l unlimited 2>/dev/null

# ==============================================================================
# 5. Server Launch Arguments
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

  # ── Mode 1: Agent & Coding (Optimized for Local CPU) ──
  --reasoning on
  --reasoning-format auto
  --reasoning-preserve
  --temp 0.2
  --top-p 0.95
  --top-k 40
  --min-p 0.05
  --repeat-penalty 1.0

  # ── Mode 2: Chat & Creative / Unconstrained (Official Text Baseline) ──
  # (To enable: comment out Mode 1 above and uncomment the lines below)
  # --reasoning off                      # Disables chain-of-thought for direct chat
  # --temp 1.0                          # Higher entropy for creative diversity
  # --top-p 0.95
  # --top-k 20
  # --presence-penalty 1.5              # Kwaipilot's recommended chat penalty
  # --repeat-penalty 1.0
)

# Attach N-Gram Speculation if statically enabled
if [ "$ENABLE_NGRAM" = "true" ]; then
    SERVER_ARGS+=(
      --spec-type ngram-mod
      --spec-draft-n-max 3
    )
fi

# ==============================================================================
# 6. Execution
# ==============================================================================
LAUNCH_PREFIX=""
if command -v uwsm >/dev/null 2>&1; then
    LAUNCH_PREFIX="uwsm app --"
fi

if [ "$ENABLE_LOG" = "true" ]; then
    mkdir -p "$LOG_DIR"
    exec $LAUNCH_PREFIX $PIN_CMD "$LLAMA_SERVER_BIN" "${SERVER_ARGS[@]}" >> "$LOG_FILE" 2>&1
else
    exec $LAUNCH_PREFIX $PIN_CMD "$LLAMA_SERVER_BIN" "${SERVER_ARGS[@]}"
fi
