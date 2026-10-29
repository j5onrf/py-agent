#!/usr/bin/env bash
set -e

# Clear any lingering GPU crash locks
rm -f "$HOME/.config/OpenBot/gpu-crash.json"

# Launch OpenBot with native Wayland/Ozone support
if [ -f "$HOME/.local/share/openbot/openbot.AppImage" ]; then
    exec env OPENBOT_DISABLE_GPU=0 "$HOME/.local/share/openbot/openbot.AppImage" --ozone-platform-hint=auto "$@"
elif command -v openbot >/dev/null 2>&1; then
    exec openbot "$@"
else
    echo "[error] OpenBot not found in ~/.local/share/openbot/ or PATH" >&2
    exit 1
fi
