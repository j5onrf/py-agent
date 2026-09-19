#!/usr/bin/env bash

# ==============================================================================
# Tini-Cybersec-8B-A1B High-Throughput CPU Launcher (LFM 8B-A1B MoE)
# Launched exclusively via model-select-local.py
# ==============================================================================

# --- Hardware & Path Configuration ---
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="${MODEL_PATH:-/home/user/models/iselabvn_Tini-Cybersec-8B-A1B-Q5_K_M.gguf}"
ALIAS="Tini-Cybersec-8B-A1B"

LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/server_tini.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

# ==============================================================================
# Static Toggles (Edit directly here)
# ==============================================================================
ENABLE_NGRAM=false   # true: enable N-gram acceleration | false: pure decode
ENABLE_LOG=false     # true: write to server_tini.log   | false: live output

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
# 5. Server Launch Arguments (LFM 8B-A1B Architecture)
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

  # ── System Suite: Deterministic Security & Diagnostic Triage ──
  --reasoning on
  --reasoning-format auto
  --reasoning-preserve
  --temp 0.15                   # Hyper-low temperature: zero hallucination, strict factual verdicts
  --top-p 0.90
  --top-k 30
  --min-p 0.05
  --repeat-penalty 1.0          # Preserves exact log lines, paths, and JSON triage schemas

  # ── Mode 2: Fast Unconstrained Triage ──
  # (To enable: comment out Mode 1 above and uncomment the lines below)
  # --reasoning off
  # --temp 0.6
  # --top-p 0.95
  # --top-k 50
  # --repeat-penalty 1.05
)

# Attach N-Gram Speculation if statically enabled
if [ "$ENABLE_NGRAM" = "true" ]; then
    SERVER_ARGS+=(
      --spec-type ngram-mod
      --spec-draft-n-max 3
    )
fi

# ==============================================================================
# 6. Launch with Desktop Session Wrapper
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
