#!/usr/bin/env bash
# ==============================================================================
# Py-Agent ThinkRail Surface Launcher (Workspace & Mode Aware)
# ==============================================================================

set -eo pipefail

PLUGIN_DIR="$HOME/.config/py-agent/plugins/thinkrail"
BRIDGE_PY="$PLUGIN_DIR/thinkrail_bridge.py"
WORKSPACE_DIR="${AI_WORKSPACE_PATH:-${1:-$PWD}}"
PI_CONFIG_DIR="$HOME/.pi/agent"
PI_MODELS_JSON="$PI_CONFIG_DIR/models.json"
BRIDGE_PORT="${THINKRAIL_BRIDGE_PORT:-8766}"

mkdir -p "$WORKSPACE_DIR"
mkdir -p "$PI_CONFIG_DIR"

# 1. Ensure the dedicated ThinkRail bridge is running on port 8766
if ! pgrep -f "thinkrail_bridge.py" >/dev/null 2>&1; then
    python3 "$BRIDGE_PY" &
    sleep 0.4
fi

# 2. Automatically register the py-agent-rail provider in ~/.pi/agent/models.json
# Safely merges into existing models.json without destroying other providers
python3 - <<EOF
import json, os

path = "$PI_MODELS_JSON"
data = {"providers": {}}

if os.path.isfile(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"providers": {}}

if "providers" not in data:
    data["providers"] = {}

data["providers"]["py-agent-rail"] = {
    "baseUrl": "http://127.0.0.1:$BRIDGE_PORT/v1",
    "api": "openai-completions",
    "apiKey": "py-agent",
    "models": [
        {
            "id": "local-8080",
            "name": "Local 8080 (Py-Agent Rail)",
            "contextWindow": 8192,
            "maxTokens": 2048
        },
        {
            "id": "gemini-3.5-flash-lite",
            "name": "Gemini 3.5 Flash Lite (Py-Agent Cloud)",
            "contextWindow": 65536,
            "maxTokens": 4096
        }
    ]
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
EOF

cd "$WORKSPACE_DIR"
THINKRAIL_BIN="$(command -v thinkrail 2>/dev/null || echo "/usr/bin/thinkrail")"

echo "🚀 Launching ThinkRail in $WORKSPACE_DIR..."
exec "$THINKRAIL_BIN" "$WORKSPACE_DIR"
