#!/usr/bin/env bash
# ==============================================================================
# Py-Agent OpenBot Surface Launcher (Workspace & Mode Aware)
# ==============================================================================

set -eo pipefail

PLUGIN_DIR="$HOME/.config/py-agent/plugins/openbot"
BRIDGE_PY="$PLUGIN_DIR/openbot_bridge.py"
WORKSPACE_DIR="${AI_WORKSPACE_PATH:-${1:-$HOME/workspace/openbot}}"

mkdir -p "$WORKSPACE_DIR"

# Ensure bridge is running on port 8765
if ! pgrep -f "openbot_bridge.py" >/dev/null 2>&1; then
    python3 "$BRIDGE_PY" &
    sleep 0.3
fi

cd "$WORKSPACE_DIR"
OPENBOT_BIN="$(command -v openbot 2>/dev/null || echo "$HOME/.local/share/openbot/openbot.AppImage")"
exec "$OPENBOT_BIN" "$@"
