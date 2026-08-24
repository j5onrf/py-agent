#!/usr/bin/env bash
PORT=3000
WEBUI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PY="$WEBUI_DIR/server.py"

# Force kill any stale processes holding port 3000
if command -v fuser >/dev/null 2>&1; then
    fuser -k "$PORT/tcp" >/dev/null 2>&1
elif command -v lsof >/dev/null 2>&1; then
    lsof -t -i :"$PORT" | xargs -r kill -9 2>/dev/null
fi
sleep 0.3

# Launch web gateway in background
python3 "$SERVER_PY" &
GATEWAY_PID=$!
sleep 0.8

# Open in browser
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:$PORT" >/dev/null 2>&1 &
fi

wait "$GATEWAY_PID" 2>/dev/null
