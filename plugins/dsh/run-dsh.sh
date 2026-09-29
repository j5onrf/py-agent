#!/usr/bin/env bash
# ==============================================================================
# DSH Launcher (DeepSeek Harness for Py-Agent)
# ==============================================================================

set -eo pipefail

PLUGIN_DIR="$HOME/.config/py-agent/plugins/dsh"
BRIDGE_PY="$PLUGIN_DIR/dsh-bridge.py"
DSH_PROFILE_DIR="$HOME/.dsh/profiles/pyagent"
PATCH_FILE="$DSH_PROFILE_DIR/cordis.patch.yml"

# ── 1. Dependency Check ───────────────────────────────────────────────────────
if ! command -v dsh &>/dev/null; then
    echo -e "\033[1;31m[dsh]\033[0m Error: 'dsh' command not found in PATH." >&2
    exit 1
fi

# ── 2. Auto-Bootstrap Profile & Patch If Missing ──────────────────────────────
if [[ ! -d "$DSH_PROFILE_DIR" ]]; then
    echo -e "\033[1;36m[dsh]\033[0m Initializing 'pyagent' profile from web template..."
    dsh --profile pyagent --from-default-profile web --no-open 2>/dev/null || true
fi

mkdir -p "$DSH_PROFILE_DIR"
if [[ ! -f "$PATCH_FILE" ]]; then
    echo -e "\033[1;36m[dsh]\033[0m Registering ACP bridge patch..."
    cat << EOF > "$PATCH_FILE"
- id: subagent-acp
  name: '@deepseek-ai/dsh-subagent-acp'
  config:
    providerName: pyagent
    command: /usr/bin/python3
    args:
      - $BRIDGE_PY
    permission: allow
EOF
fi

# ── 3. Resolve Absolute Target Workspace ──────────────────────────────────────
RAW_WORKSPACE="${1:-${AI_WORKSPACE_PATH:-$PWD}}"
if ! TARGET_WORKSPACE=$(cd "$RAW_WORKSPACE" 2>/dev/null && pwd -P); then
    TARGET_WORKSPACE="$PWD"
fi

# ── 4. Verify Bridge Permissions ──────────────────────────────────────────────
if [[ ! -f "$BRIDGE_PY" ]]; then
    echo -e "\033[1;31m[dsh]\033[0m Error: bridge script not found at '$BRIDGE_PY'" >&2
    exit 1
fi
chmod +x "$BRIDGE_PY" 2>/dev/null || true

# ── 5. Cleanup Trap (Frees port 3080 and kills child workers on exit) ─────────
cleanup() {
    pkill -P $$ 2>/dev/null || true
    fuser -k 3080/tcp 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── 6. Dispatch Execution inside Workspace Root ───────────────────────────────
cd "$TARGET_WORKSPACE"
echo -e "\033[1;36m[dsh]\033[0m Launching DeepSeek Harness Web Cockpit for: $TARGET_WORKSPACE"
exec dsh --profile pyagent
