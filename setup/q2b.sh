#!/usr/bin/env bash

# ==========================================
# Configuration & Hardware Tuning
# ==========================================
PORT=8080
HOST="127.0.0.1"
MODEL_PATH="/home/user/models/Qwen3.5-2B-Claude.gguf"
LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/server.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

mkdir -p "$LOG_DIR"

# 1. Clean up lingering instances on the port
if command -v lsof >/dev/null 2>&1; then
    TARGET_PID=$(lsof -t -i :"$PORT")
    if [ -n "$TARGET_PID" ]; then
        kill -15 "$TARGET_PID" 2>/dev/null || kill -9 "$TARGET_PID" 2>/dev/null
        sleep 0.5
    fi
fi

# 2. Extract Physical Core IDs (bypasses SMT / Hyper-Threading)
PHYSICAL_CORES=$(lscpu -p=CPU,CORE | grep -v '^#' | sort -u -k2,2 -t, | cut -d, -f1 | paste -sd, -)

# 3. Allocator and Thread Binding (CachyOS x86-64-v4 mimalloc)
if [ -f /usr/lib/libmimalloc.so ]; then
    export LD_PRELOAD=/usr/lib/libmimalloc.so
fi
export OMP_PROC_BIND=CLOSE
export OMP_PLACES=cores

# 4. Remove memory locking ceiling
ulimit -l unlimited 2>/dev/null

# 5. Launch wrapped in UWSM (Optimized Native AVX-512 / VNNI Engine)
exec uwsm app -- taskset -c "$PHYSICAL_CORES" "$LLAMA_SERVER_BIN" \
  -m "$MODEL_PATH" \
  --alias "Qwen3.5-2B-Claude" \
  --host "$HOST" \
  --port "$PORT" \
  -c 8192 \
  -np 1 \
  -t 6 \
  -tb 6 \
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
  --temp 0.15 \
  --min-p 0.05 \
  --repeat-penalty 1.15 \
  --repeat-last-n 256 \
  --presence-penalty 0.15 >> "$LOG_FILE" 2>&1
