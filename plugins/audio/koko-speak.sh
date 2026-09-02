#!/usr/bin/env bash
# High-Performance Kokoro Selection Speaker (RAM-disk execution)

# 1. Ensure full PATH is available when launched from Hyprland
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.local/share/mise/shims:/usr/local/bin:$PATH"

# 2. Grab text: try primary highlight first, then fallback to clipboard
TEXT=$(wl-paste --primary 2>/dev/null)
[ -z "$TEXT" ] && TEXT=$(wl-paste 2>/dev/null)

# Sanitize text
TEXT=$(echo "$TEXT" | sed -E "s/^[0-9]+:[0-9]+(:[0-9]+)?//g; s/:/, /g" | tr -d '`*#')
[ -z "$TEXT" ] && exit 0

# 3. Get voice & speed preferences (defaults to am_echo and 1.15)
VOICE=$(cat "$HOME/.config/koko_current_voice" 2>/dev/null || echo "am_echo")
SPEED=$(cat "$HOME/.config/koko_speed" 2>/dev/null || echo "1.15")

# 4. Kill previous playback (EXACT match only, so it does not kill this script)
pkill -9 -x pw-play 2>/dev/null
pkill -9 -x koko 2>/dev/null

# 5. Generate into RAM disk (/dev/shm) and play
if command -v koko >/dev/null 2>&1; then
    nice -n -5 env OMP_NUM_THREADS=6 OMP_WAIT_POLICY=PASSIVE koko --style "$VOICE" --speed "$SPEED" text "$TEXT" -o /dev/shm/tts.wav 2>/dev/null && pw-play /dev/shm/tts.wav
else
    notify-send -u critical "TTS Error" "koko command not found in PATH"
fi
