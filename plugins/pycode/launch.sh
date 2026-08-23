#!/usr/bin/env bash
# ==============================================================================
# PyCode Launcher (Cross-Platform Desktop App by Default / Browser Tab with 'web')
# ==============================================================================

set -eo pipefail

PLUGIN_DIR="$HOME/.config/py-agent/plugins/pycode"
PYCODE_DIR="$HOME/.config/pycode"
BRIDGE_PY="$PLUGIN_DIR/bridge.py"

# Resolve absolute target workspace
TARGET_WORKSPACE="${AI_WORKSPACE_PATH:-$(pwd)}"
TARGET_WORKSPACE=$(cd "$TARGET_WORKSPACE" 2>/dev/null && pwd -P || echo "$TARGET_WORKSPACE")

# Isolate all runtime data & configuration in ~/.pycode
export AI_WORKSPACE_PATH="$TARGET_WORKSPACE"
export PYAGENT_BRIDGE="$BRIDGE_PY"
export T3CODE_HOME="$HOME/.pycode"
export T3CODE_AUTO_BOOTSTRAP_PROJECT_FROM_CWD="true"
export T3_AUTO_BOOTSTRAP_PROJECT_FROM_CWD="true"

# Ensure runtime directories exist
mkdir -p "$T3CODE_HOME/userdata"

# Ensure bridge script is executable
chmod +x "$BRIDGE_PY" 2>/dev/null || true

# ── 1. Browser Mode (pycode web) ─────────────────────────────────────────────
if [[ "$1" == "web" || "$1" == "--web" || "$1" == "--browser" || "$2" == "web" || "$2" == "--web" ]]; then
    echo "[pycode] Starting server in browser mode for: $TARGET_WORKSPACE"
    cd "$TARGET_WORKSPACE"
    exec node "$PYCODE_DIR/apps/server/dist/bin.mjs" start --mode=web "$TARGET_WORKSPACE"
fi

# ── 2. Native Desktop App Mode (Default) ────────────────────────────────────
echo "[pycode] Launching PyCode Desktop App for: $TARGET_WORKSPACE"
cd "$TARGET_WORKSPACE"
exec node "$PYCODE_DIR/apps/desktop/scripts/start-electron.mjs" "$TARGET_WORKSPACE"
