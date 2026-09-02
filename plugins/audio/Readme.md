# Kokoro Neural Selection Speaker Plugin

Ultra-low-latency desktop text-to-speech reader for Wayland (Hyprland / Sway) using Kokoro in RAM-disk (`/dev/shm`).

## Features
* **Zero-Disk I/O:** Synthesizes `.wav` directly into `/dev/shm/tts.wav` for instant playback via PipeWire.
* **Unified Preferences:** Shares voice (`~/.config/koko_current_voice`) and speed (`~/.config/koko_speed`) with `py-agent` (`/tts`).
* **Instant Cancellation:** Kill switch stops audio output immediately.

---

## Dependencies (Arch Linux)

```bash
yay -S koko-bin pw-play wl-clipboard
```

---

## Hyprland Integration

Add to your `hyprland.conf` (or Hyprland Lua config):

```ini
# Speak highlighted text on screen
bind = SUPER SHIFT, R, exec, ~/.config/py-agent/plugins/audio/koko-speak.sh

# Emergency Stop Speech
bind = SUPER SHIFT, X, exec, pkill -9 -f "pw-play|koko"
```

#### Lua (Hyprland / Hyprload):
```lua
hl.bind("SUPER + SHIFT + R", hl.dsp.exec_cmd(home .. "/.config/py-agent/plugins/audio/koko-speak.sh"))
hl.bind("SUPER + SHIFT + X", hl.dsp.exec_cmd('pkill -9 -f "pw-play|koko"'))
```

---

## Usage
1. Highlight any text in your browser, editor, or terminal.
2. Press **`SUPER + SHIFT + R`** to hear it read aloud.
3. Press **`SUPER + SHIFT + X`** to stop playback anytime.
