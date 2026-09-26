#!/usr/bin/env bash
# ==============================================================================
# PyCode Launcher (Cross-Platform Desktop App by Default / Browser Tab with 'web')
# ==============================================================================

set -eo pipefail

PLUGIN_DIR="$HOME/.config/py-agent/plugins/pycode"
PYCODE_DIR="$HOME/.config/pycode"
BRIDGE_PY="$PLUGIN_DIR/bridge.py"

SERVER_BIN="$PYCODE_DIR/apps/server/dist/bin.mjs"
DESKTOP_SCRIPT="$PYCODE_DIR/apps/desktop/scripts/start-electron.mjs"

show_help() {
    cat <<EOF
Usage: pycode [options] [workspace_dir]
       pycode [workspace_dir] [options]

Modes:
  (default)            Launch native desktop Electron app
  web, --web, --browser Launch headless server and open in browser

Options:
  -h, --help           Show this help message and exit

Environment Variables:
  AI_WORKSPACE_PATH    Override active workspace root directory
EOF
    exit 0
}

# ── 1. Parse Arguments ────────────────────────────────────────────────────────
MODE="desktop"
WORKSPACE_ARG=""

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            ;;
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

# ── 2. Environment & Dependency Pre-flight ───────────────────────────────────
if ! command -v node &>/dev/null; then
    echo -e "\033[1;31m[pycode]\033[0m Error: Node.js ('node') is required but not found in PATH." >&2
    exit 1
fi

# ── 3. Auto-bootstrap if PyCode is Missing or Incomplete ─────────────────────
if [[ ! -d "$PYCODE_DIR" || ! -f "$SERVER_BIN" || ! -f "$DESKTOP_SCRIPT" ]]; then
    if [[ ! -f "$PLUGIN_DIR/setup.sh" ]]; then
        echo -e "\033[1;31m[pycode]\033[0m Error: setup script not found at '$PLUGIN_DIR/setup.sh'" >&2
        exit 1
    fi
    echo -e "\033[1;36m[pycode]\033[0m PyCode installation not found or not built. Running setup..."
    if ! bash "$PLUGIN_DIR/setup.sh"; then
        echo -e "\033[1;31m[pycode]\033[0m Error: Setup failed. Check the output above or retry with: bash $PLUGIN_DIR/setup.sh" >&2
        exit 1
    fi
fi

# ── 4. Resolve Absolute Target Workspace ──────────────────────────────────────
RAW_WORKSPACE="${WORKSPACE_ARG:-${AI_WORKSPACE_PATH:-$PWD}}"
if ! TARGET_WORKSPACE=$(cd "$RAW_WORKSPACE" 2>/dev/null && pwd -P); then
    echo -e "\033[1;31m[pycode]\033[0m Error: workspace directory does not exist or is inaccessible: '$RAW_WORKSPACE'" >&2
    exit 1
fi

# ── 5. Bridge Verification & Execution Permissions ───────────────────────────
if [[ ! -f "$BRIDGE_PY" ]]; then
    echo -e "\033[1;31m[pycode]\033[0m Error: bridge script not found at '$BRIDGE_PY'" >&2
    exit 1
fi

if ! chmod +x "$BRIDGE_PY" 2>/dev/null; then
    echo -e "\033[1;33m[pycode] warning:\033[0m Could not set execute permission on '$BRIDGE_PY'" >&2
fi

# ── 6. Isolate Runtime Data & Configuration ──────────────────────────────────
export AI_WORKSPACE_PATH="$TARGET_WORKSPACE"
export PYAGENT_BRIDGE="$BRIDGE_PY"
export T3CODE_HOME="$HOME/.pycode"
export T3CODE_AUTO_BOOTSTRAP_PROJECT_FROM_CWD="true"
export T3_AUTO_BOOTSTRAP_PROJECT_FROM_CWD="true"

mkdir -p "$T3CODE_HOME/userdata"
cd "$TARGET_WORKSPACE"

# ── 7. Dispatch Execution ────────────────────────────────────────────────────
if [[ "$MODE" == "web" ]]; then
    if [[ ! -f "$SERVER_BIN" ]]; then
        echo -e "\033[1;31m[pycode]\033[0m Error: server entrypoint not found at '$SERVER_BIN'" >&2
        exit 1
    fi
    echo -e "\033[1;36m[pycode]\033[0m Starting server in browser mode for: $TARGET_WORKSPACE"
    exec node "$SERVER_BIN" start --mode=web "$TARGET_WORKSPACE"
else
    if [[ ! -f "$DESKTOP_SCRIPT" ]]; then
        echo -e "\033[1;31m[pycode]\033[0m Error: desktop entrypoint not found at '$DESKTOP_SCRIPT'" >&2
        exit 1
    fi
    echo -e "\033[1;36m[pycode]\033[0m Launching PyCode Desktop App for: $TARGET_WORKSPACE"
    exec node "$DESKTOP_SCRIPT" "$TARGET_WORKSPACE"
fi
