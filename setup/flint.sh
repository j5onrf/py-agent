#!/usr/bin/env bash

# ==============================================================================
# Recursive Flint 40B-A2.5B APEX-I-MiniPlus-V2.1 (Coding Agent MoE)
# Launched exclusively via model-select-local.py
# ==============================================================================

# --- Hardware & Path Configuration ---
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="$HOME/models/Flint.APEX-I-MiniPlus-V2.1.gguf"
ALIAS="Flint-40B-A2.5B"

LOG_DIR="/$HOME/models/serv"
LOG_FILE="$LOG_DIR/flint-server.log"
LLAMA_SERVER_BIN="$HOME/llama.cpp/build/bin/llama-server"

# ==============================================================================
# Static Toggles (Edit directly here)
# ==============================================================================
ENABLE_MTP=false      # false: Flint has no external MTP draft head
ENABLE_NGRAM=false    # true: enable N-gram acceleration               | false: pure decode
ENABLE_LOG=false      # true: write to flint-server.log                | false: live output

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

  # Context & Concurrency
  # Hybrid sliding-window attention (35 SWA layers + 14 full-attention layers)
  -c 8192
  -np 1

  # Threading & Batching
  -t "$CORE_COUNT"
  -tb "$CORE_COUNT"
  -b 512
  -ub 256

  # Engine & Memory Strategy
  --flash-attn on
  --load-mode mlock
  --warmup
  --no-ui
  --context-shift

  # Template & Thinking Handling
  --jinja
  --reasoning on
  --reasoning-format auto
  --reasoning-preserve

  # ── Mode 1: Official Flint Recommended Sampling ──
  --temp 1.0
  --top-p 0.95
  --top-k 20
  --min-p 0.0
  --repeat-penalty 1.0

  # ── Mode 2: Low-Temperature Focused Coding ──
  # (To enable: comment out Mode 1 above and uncomment the lines below)
  # --temp 0.6
  # --top-p 0.95
  # --top-k 40
  # --min-p 0.05
  # --repeat-penalty 1.0
)

# Speculative decoding configuration
MTP_DRAFT="/home/j5/models/mtp-draft.gguf"

if [ "$ENABLE_MTP" = "true" ] && [ -f "$MTP_DRAFT" ]; then
    SERVER_ARGS+=(
      -md "$MTP_DRAFT"
      --spec-draft-n-max 2
    )
elif [ "$ENABLE_NGRAM" = "true" ]; then
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
