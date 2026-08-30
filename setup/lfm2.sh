#!/usr/bin/env bash

# Configuration
PORT=8080
MODEL_PATH="/home/user/models/LFM2.5-8B-A1B.gguf"
LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/server.log"
LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"

mkdir -p "$LOG_DIR"

# 1. Clean up lingering port processes
if command -v lsof >/dev/null 2>&1; then
    TARGET_PID=$(lsof -t -i :"$PORT")
    if [ -n "$TARGET_PID" ]; then
        kill -15 "$TARGET_PID" 2>/dev/null || kill -9 "$TARGET_PID" 2>/dev/null
        sleep 0.5
    fi
fi

# 2. Extract Physical Core IDs (bypasses SMT / Hyper-Threading)
PHYSICAL_CORES=$(lscpu -p=CPU,CORE | grep -v '^#' | sort -u -k2,2 -t, | cut -d, -f1 | paste -sd, -)

# 3. Allocator and Thread Binding
if [ -f /usr/lib/libmimalloc.so ]; then
    export LD_PRELOAD=/usr/lib/libmimalloc.so
fi
export OMP_PROC_BIND=CLOSE
export OMP_PLACES=cores

# 4. Launch wrapped in UWSM
exec uwsm app -- taskset -c "$PHYSICAL_CORES" "$LLAMA_SERVER_BIN" \
  -m "$MODEL_PATH" \
  --alias "LFM2.5-8B-A1B" \
  -c 8192 \
  -np 1 \
  -t 6 \
  -tb 6 \
  -b 512 \
  -ub 512 \
  --flash-attn on \
  --mlock \
  --warmup \
  --jinja \
  --temp 0.2 \
  --top-k 80 \
  --top-p 0.90 \
  --min-p 0.05 \
  --repeat-penalty 1.05 \
  --presence-penalty 0.1 \
  --repeat-last-n -1 \
  --no-ui \
  --port "$PORT" >> "$LOG_FILE" 2>&1
