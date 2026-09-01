#!/usr/bin/env bash
# ==============================================================================
# PyCode Automated Setup & Build Script for Py-Agent
# ==============================================================================

set -eo pipefail

PYAGENT_DIR="${HOME}/.config/py-agent"
PYCODE_DIR="${HOME}/.config/pycode"
REPO_URL="https://github.com/j5onrf/pycode.git"

# Interactive Confirmation Gate (explicitly binds to /dev/tty for shell hook execution)
if [[ "$1" != "-y" && "$1" != "--yes" ]]; then
    echo -e "\n\033[1;36m[pycode-setup]\033[0m PyCode React Desktop & Web IDE Installer"
    echo -e "Target path: \033[1;33m${PYCODE_DIR}\033[0m"
    echo -e "This will download dependencies and build the PyCode workspace (~200MB).\n"

    if [ -e /dev/tty ]; then
        read -rp "Do you want to proceed with the installation? [y/N]: " confirm < /dev/tty
    else
        read -rp "Do you want to proceed with the installation? [y/N]: " confirm
    fi

    if [[ ! "$confirm" =~ ^[yY]([eE][sS])?$ ]]; then
        echo -e "\n\033[1;33m[pycode-setup]\033[0m Installation cancelled by user.\n"
        exit 0
    fi
    echo ""
fi

echo -e "\033[1;36m[pycode-setup]\033[0m Checking prerequisites..."

# 1. Check Node.js
if ! command -v node &>/dev/null; then
    echo -e "\033[1;31m[error]\033[0m Node.js is required. Please install Node.js 20+ (e.g. 'sudo pacman -S nodejs')."
    exit 1
fi

# 2. Check / Enable pnpm
if ! command -v pnpm &>/dev/null; then
    echo -e "\033[1;33m[pycode-setup]\033[0m pnpm not found. Enabling via corepack..."
    corepack enable || npm install -g pnpm
fi

# 3. Setup ~/.pycode directory and default settings.json
echo -e "\033[1;36m[pycode-setup]\033[0m Preparing PyCode data directory..."
mkdir -p "${HOME}/.pycode/userdata"
export T3CODE_HOME="${HOME}/.pycode"

SETTINGS_FILE="${HOME}/.pycode/userdata/settings.json"
if [ ! -f "$SETTINGS_FILE" ]; then
    echo -e "\033[1;36m[pycode-setup]\033[0m Pre-seeding default settings.json..."
    cat << 'EOF' > "$SETTINGS_FILE"
{
  "chatGlow": true,
  "enableLegacyTokenStreaming": true,
  "enableProviderUpdateChecks": false,
  "providerInstances": {
    "claudeAgent": {
      "driver": "claudeAgent",
      "enabled": false,
      "config": {
        "binaryPath": "claude",
        "homePath": "",
        "customModels": [],
        "launchArgs": ""
      }
    },
    "codex": {
      "driver": "codex",
      "enabled": false,
      "config": {
        "binaryPath": "codex",
        "homePath": "",
        "shadowHomePath": "",
        "launchArgs": "",
        "customModels": []
      }
    }
  }
}
EOF
fi

# 4. Clone or Update PyCode repo
if [ ! -d "$PYCODE_DIR" ]; then
    echo -e "\033[1;36m[pycode-setup]\033[0m Cloning PyCode into $PYCODE_DIR..."
    git clone --depth 1 "$REPO_URL" "$PYCODE_DIR"
else
    echo -e "\033[1;36m[pycode-setup]\033[0m Existing PyCode installation found at $PYCODE_DIR."
fi

# 5. Install & Build
echo -e "\033[1;36m[pycode-setup]\033[0m Installing dependencies..."
cd "$PYCODE_DIR"
pnpm install

echo -e "\033[1;36m[pycode-setup]\033[0m Building PyCode frontend and server..."
pnpm build

# 6. Ensure scripts are executable
chmod +x "$PYAGENT_DIR/plugins/pycode/launch.sh" 2>/dev/null || true
chmod +x "$PYAGENT_DIR/plugins/pycode/bridge.py" 2>/dev/null || true

echo -e "\n\033[1;32m✔ PyCode installation complete!\033[0m"
echo -e "You can now launch the GUI from your terminal by running:\n"
echo -e "  \033[1;37mai\033[0m  ──►  \033[1;36m/pycode\033[0m (or \033[1;36m/pycode web\033[0m for browser mode)\n"
