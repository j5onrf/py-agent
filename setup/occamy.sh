#!/usr/bin/env bash

# ==============================================================================
# Occamy-1.0 APEX-I-MiniPlus-V2.1 (CPU-Only 32GB DDR4 Optimized)
# Accio-Lab Agentic Co-Work & Multimodal MoE
# ==============================================================================

# --- Hardware & Path Configuration ---
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="/home/user/models/Occamy-1.0.APEX-I-MiniPlus-V2.1.gguf"
MMPROJ_PATH="/home/user/models/mmproj-Accio-Lab_occamy-1.0-Q8_0.gguf"
ALIAS="Occamy-1.0"

LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/occamy-server.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

# ==============================================================================
# Static Toggles (Edit directly here)
# ==============================================================================
ENABLE_VISION=false  # true: load mmproj for OCR/images | false: text-only mode
ENABLE_NGRAM=false   # true: speculative n-gram speedup | false: pure decode
ENABLE_LOG=false     # true: write to occamy-server.log | false: live output

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

# 3. Allocator and Thread Binding (CachyOS / Arch x86-64-v4 mimalloc)
if [ -f /usr/lib/libmimalloc.so ]; then
    export LD_PRELOAD=/usr/lib/libmimalloc.so
fi
export OMP_PROC_BIND=CLOSE
export OMP_PLACES=cores

# 4. Remove memory locking ceiling for mlock
ulimit -l unlimited 2>/dev/null

# ==============================================================================
# 5. Server Launch Arguments
# ==============================================================================
SERVER_ARGS=(
  -m "$MODEL_PATH"
  --alias "$ALIAS"
  --host "$HOST"
  --port "$PORT"
  -ngl 0                     # CPU execution: zero layers offloaded to GPU
  -c 16384                   # 16k context (Optimal RAM & CPU prompt processing sweet spot)
  -np 1                      # 1 slot dedicated to max memory/compute efficiency
  -t "$CORE_COUNT"           # Thread count pinned to physical cores
  -tb "$CORE_COUNT"          # Batch threads
  -b 512                     # Prompt processing batch size
  -ub 256                    # Physical micro-batch size
  --flash-attn on            # Flash Attention for linear memory scaling
  --load-mode mlock          # Lock model into RAM to prevent disk swapping
  --warmup
  --no-ui
  --context-shift
  --jinja

  # ── Mode 1: Agent & Co-Work (Accio-Lab Recommended for Claw / Hermes / Tools) ──
  --reasoning on
  --reasoning-format auto
  --reasoning-preserve
  --temp 0.6                 # Accio-Lab agentic sweet spot (balances stability & creativity)
  --top-p 0.95
  --top-k 20
  --min-p 0.05
  --repeat-penalty 1.05

  # ── Mode 2: Chat & Creative / Unconstrained (Official Card Baseline) ──
  # (To enable: comment out Mode 1 above and uncomment the lines below)
  # --reasoning off
  # --temp 1.0
  # --top-p 0.95
  # --top-k 20
  # --presence-penalty 1.5   # Accio-Lab's recommended diversity penalty
  # --repeat-penalty 1.0
)

# Attach Vision Projector if enabled and exists
if [ "$ENABLE_VISION" = "true" ] && [ -f "$MMPROJ_PATH" ]; then
    SERVER_ARGS+=(--mmproj "$MMPROJ_PATH")
fi

# Attach N-Gram Speculation if enabled
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
