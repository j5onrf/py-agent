#!/usr/bin/env bash
# ==============================================================================
# T3 Code Launcher (Auto Project Handover & Workspace Sync) [CR.01]
# ==============================================================================

set -eo pipefail

PLUGIN_DIR="$HOME/.config/py-agent/plugins/t3code"
BRIDGE_PY="$PLUGIN_DIR/t3code-bridge.py"

T3_BIN="$(command -v t3code || command -v t3 || true)"
T3_CLI="$HOME/.t3/bin/t3"
[[ -x "$T3_CLI" ]] || T3_CLI="$(command -v t3 || true)"

if [[ -z "$T3_BIN" ]]; then
    echo -e "\033[1;31m[t3code]\033[0m Error: 't3code' binary not found in PATH." >&2
    exit 1
fi

# ── 1. Parse Arguments (Separate Mode Flags from Workspace Path) ──────────────
MODE="desktop"
WORKSPACE_ARG=""

for arg in "$@"; do
    case "$arg" in
        web|--web|--browser)
            MODE="web"
            ;;
        *)
            if [[ -z "$WORKSPACE_ARG" ]]; then
                WORKSPACE_ARG="$arg"
            fi
            ;;
    esac
done

# ── 2. Resolve Target Workspace ───────────────────────────────────────────────
RAW_WORKSPACE="${WORKSPACE_ARG:-${AI_WORKSPACE_PATH:-$PWD}}"
if ! TARGET_WORKSPACE=$(cd "$RAW_WORKSPACE" 2>/dev/null && pwd -P); then
    if [[ -n "$WORKSPACE_ARG" ]]; then
        echo -e "\033[1;31m[t3code]\033[0m Error: workspace '$RAW_WORKSPACE' is not a valid directory." >&2
        exit 1
    fi
    TARGET_WORKSPACE="$PWD"
fi

# Validate bridge file before applying permissions
if [[ -f "$BRIDGE_PY" && ! -L "$BRIDGE_PY" && -O "$BRIDGE_PY" ]]; then
    chmod +x "$BRIDGE_PY" 2>/dev/null || true
else
    echo -e "\033[1;33m[t3code]\033[0m Warning: bridge script '$BRIDGE_PY' missing, symlinked, or unowned." >&2
fi

# ── 3. Environment Setup ──────────────────────────────────────────────────────
export AI_WORKSPACE_PATH="$TARGET_WORKSPACE"
export PYAGENT_BRIDGE="$BRIDGE_PY"
export T3CODE_HOME="${T3CODE_HOME:-$HOME/.t3}"

cd "$TARGET_WORKSPACE"

# ── 4. Dispatch Web Mode or Desktop App ───────────────────────────────────────
if [[ "$MODE" == "web" ]]; then
    # In web mode, run the headless server and open browser
    if [[ -x "$T3_CLI" ]]; then
        exec "$T3_CLI" "$TARGET_WORKSPACE"
    else
        exec "$T3_BIN" --web "$TARGET_WORKSPACE"
    fi
fi

# ── 5. Desktop Mode: Check if T3 Code is Already Running ──────────────────────
T3_NAME="$(basename "$T3_BIN")"
if [[ -x "$T3_CLI" ]] && pgrep -x "$T3_NAME" &>/dev/null; then
    if "$T3_CLI" app "$TARGET_WORKSPACE" &>/dev/null; then
        echo -e "\033[1;32m[t3code]\033[0m Handed workspace '$TARGET_WORKSPACE' to active T3 Code window."
        exit 0
    fi
fi

# ── 6. Fresh Desktop Launch with Managed Handover & Scoped Lifecycle ──────────
T3_PID=""
HANDOVER_PID=""
_CLEANED=0

cleanup() {
    [[ "$_CLEANED" -eq 1 ]] && return 0
    _CLEANED=1

    [[ -n "$HANDOVER_PID" ]] && kill -TERM "$HANDOVER_PID" 2>/dev/null || true
    if [[ -n "$T3_PID" ]] && kill -0 "$T3_PID" 2>/dev/null; then
        kill -TERM "$T3_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

# Start T3 Code in background
"$T3_BIN" &
T3_PID=$!

# Wait for IPC socket, then hand over the workspace
if [[ -x "$T3_CLI" ]]; then
    (
        for _ in {1..30}; do
            sleep 0.2
            if "$T3_CLI" app "$TARGET_WORKSPACE" &>/dev/null; then
                break
            fi
        done
    ) &
    HANDOVER_PID=$!
fi

# Wait for T3 Code process to exit
wait "$T3_PID"
