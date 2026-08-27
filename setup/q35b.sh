#!/usr/bin/env bash

# Configuration
PORT=8080
MODEL_PATH="/home/user/models/Hermes3.6-35B-A3B.gguf"
LOG_DIR="/home/user/models/serv"
LOG_FILE="$LOG_DIR/server.log"

LLAMA_SERVER_BIN="/home/user/llama.cpp/build/bin/llama-server"
mkdir -p "$LOG_DIR"

if command -v lsof >/dev/null 2>&1; then
    TARGET_PID=$(lsof -t -i :$PORT)
    if [ -n "$TARGET_PID" ]; then
        kill -15 "$TARGET_PID" 2>/dev/null || kill -9 "$TARGET_PID" 2>/dev/null
        sleep 0.5
    fi
fi

# Launch wrapped in UWSM   --no-ui \
exec uwsm app -- "$LLAMA_SERVER_BIN" \
  -m "$MODEL_PATH" \
  -c 8192 \
  -np 1 \
  -t 6 \
  -b 512 \
  -ub 512 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --flash-attn on \
  --reasoning on \
  --reasoning-format auto \
  --reasoning-budget-message "\n" \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --context-shift \
  --jinja \
  --temp 0.6 \
  --top-k 20 \
  --top-p 0.95 \
  --min-p 0.05 \
  --repeat-penalty 1.05 \
  --repeat-last-n 128 \
  --port "$PORT" >> "$LOG_FILE" 2>&1
