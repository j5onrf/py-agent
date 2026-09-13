#!/usr/bin/env bash
# ==============================================================================
# Py-Agent Official llama.cpp WebUI Gateway Launcher [Production Ready]
# ==============================================================================

set -eo pipefail

PORT="${PY_AGENT_WEB_PORT:-3000}"
WEBUI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PY="$WEBUI_DIR/server.py"
_PY="$(command -v python3 || command -v python)"

# Force kill any stale processes holding the gateway port
if command -v fuser >/dev/null 2>&1; then
    fuser -k "$PORT/tcp" >/dev/null 2>&1 || true
elif command -v lsof >/dev/null 2>&1; then
    lsof -t -i :"$PORT" | xargs -r kill -9 2>/dev/null || true
fi
sleep 0.2

# Launch web gateway in background
"$_PY" "$SERVER_PY" &
GATEWAY_PID=$!
trap 'kill "$GATEWAY_PID" 2>/dev/null || true' EXIT INT TERM
sleep 0.8

# Open in browser
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:$PORT" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:$PORT" >/dev/null 2>&1 &
fi

wait "$GATEWAY_PID" 2>/dev/null || true
