#!/usr/bin/env bash
# ==============================================================================
# Py-Agent Official llama.cpp WebUI Gateway Launcher [Hardened Production Ready]
# ==============================================================================

set -eo pipefail

PORT="${PY_AGENT_WEB_PORT:-3000}"
WEBUI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PY="$WEBUI_DIR/server.py"

# ── 1. Input & Interpreter Validation ────────────────────────────────────────
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
    echo -e "\033[1;31m[webui]\033[0m Error: invalid PY_AGENT_WEB_PORT '$PORT' (must be 1-65535)." >&2
    exit 1
fi

_PY="$(command -v python3 || command -v python || true)"
if [[ -z "$_PY" ]]; then
    echo -e "\033[1;31m[webui]\033[0m Error: python3 or python interpreter not found in PATH." >&2
    exit 1
fi

if [[ ! -f "$SERVER_PY" ]]; then
    echo -e "\033[1;31m[webui]\033[0m Error: gateway server script not found at '$SERVER_PY'" >&2
    exit 1
fi

OPEN_BROWSER=true
for arg in "$@"; do
    case "$arg" in
        --no-browser|--headless)
            OPEN_BROWSER=false
            ;;
    esac
done

# ── 2. Port & Process Ownership Management ───────────────────────────────────
PID_DIR="${XDG_RUNTIME_DIR:-$HOME/.config/py-agent/.run}"
mkdir -p "$PID_DIR"
PID_FILE="$PID_DIR/webui-$PORT.pid"

is_port_listening() {
    (echo > "/dev/tcp/127.0.0.1/$PORT") >/dev/null 2>&1 && return 0
    if command -v curl >/dev/null 2>&1; then
        curl -s -o /dev/null -m 0.5 "http://127.0.0.1:$PORT/props" >/dev/null 2>&1 && return 0
    fi
    return 1
}

# Reclaim port only if held by our previous gateway instance
if [[ -f "$PID_FILE" ]]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        if ps -p "$OLD_PID" -o args= 2>/dev/null | grep -q "server.py"; then
            echo -e "\033[1;33m[webui]\033[0m Stopping existing gateway instance (PID: $OLD_PID)..."
            kill "$OLD_PID" 2>/dev/null || true
            for _ in $(seq 1 20); do
                if ! kill -0 "$OLD_PID" 2>/dev/null; then
                    break
                fi
                sleep 0.1
            done
            if kill -0 "$OLD_PID" 2>/dev/null; then
                kill -9 "$OLD_PID" 2>/dev/null || true
            fi
        fi
    fi
    rm -f "$PID_FILE" 2>/dev/null || true
fi

# Guard against foreign services on the same port
if is_port_listening; then
    echo -e "\033[1;31m[webui]\033[0m Error: Port $PORT is already in use by an external service." >&2
    echo -e "Please free the port or specify another: PY_AGENT_WEB_PORT=<port> $0" >&2
    exit 1
fi

# ── 3. Start Gateway Server ──────────────────────────────────────────────────
"$_PY" "$SERVER_PY" &
GATEWAY_PID=$!
echo "$GATEWAY_PID" > "$PID_FILE"

cleanup() {
    local rc=$?
    if [[ -n "${GATEWAY_PID:-}" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
        kill "$GATEWAY_PID" 2>/dev/null || true
        wait "$GATEWAY_PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE" 2>/dev/null || true
    exit "$rc"
}
trap cleanup EXIT INT TERM

# ── 4. Bounded Readiness Polling ─────────────────────────────────────────────
READY=false
for _ in $(seq 1 50); do # Poll for up to 5 seconds
    if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
        echo -e "\033[1;31m[webui]\033[0m Error: Gateway server exited unexpectedly during startup." >&2
        wait "$GATEWAY_PID"
        exit $?
    fi
    if is_port_listening; then
        READY=true
        break
    fi
    sleep 0.1
done

if [[ "$READY" != "true" ]]; then
    echo -e "\033[1;31m[webui]\033[0m Error: Gateway server failed to start within 5 seconds." >&2
    exit 1
fi

# ── 5. Open Browser (if enabled) ─────────────────────────────────────────────
if [[ "$OPEN_BROWSER" == "true" ]]; then
    TARGET_URL="http://127.0.0.1:$PORT"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$TARGET_URL" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
        open "$TARGET_URL" >/dev/null 2>&1 &
    fi
fi

# ── 6. Wait for Process & Propagate Exit Status ──────────────────────────────
wait "$GATEWAY_PID"
exit_code=$?
exit "$exit_code"
