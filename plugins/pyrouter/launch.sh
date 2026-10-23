#!/usr/bin/env bash
# ==============================================================================
# PyRouter Minimal Daemon Manager (Zero External Dependencies)
# ==============================================================================

PORT=20128
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$HOME/.config/py-agent/.pyrouter.pid"
LOG_FILE="$HOME/.config/py-agent/.pyrouter.log"
ROUTER_PY="$DIR/pyrouter.py"
PYTHON_BIN="${_AI_PY:-/usr/bin/python3}"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "\033[1;33m[pyrouter] Already running (PID: $(cat "$PID_FILE")) on port $PORT\033[0m"
        return 0
    fi

    echo -e "\033[1;32m[pyrouter] Starting gateway on http://127.0.0.1:$PORT...\033[0m"
    nohup "$PYTHON_BIN" "$ROUTER_PY" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 0.5

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "\033[1;32m✓ [pyrouter] Active on port $PORT (PID: $(cat "$PID_FILE"))\033[0m"
    else
        echo -e "\033[1;31m✗ [pyrouter] Failed to start. Check $LOG_FILE\033[0m"
        cat "$LOG_FILE"
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            rm -f "$PID_FILE"
            echo -e "\033[1;33m[pyrouter] Stopped process $PID.\033[0m"
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    local fpid
    fpid=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$fpid" ]; then
        kill -9 "$fpid" 2>/dev/null
        echo -e "\033[1;33m[pyrouter] Killed process on port $PORT ($fpid)\033[0m"
    else
        echo -e "\033[2m[pyrouter] Not running.\033[0m"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "\033[1;32m● [pyrouter] Running (PID: $(cat "$PID_FILE")) on http://127.0.0.1:$PORT\033[0m"
    else
        echo -e "\033[1;31m○ [pyrouter] Inactive\033[0m"
    fi
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 0.5; start ;;
    status)  status ;;
    log)     tail -f "$LOG_FILE" ;;
    *)       start ;;
esac
