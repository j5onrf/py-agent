# Kokoro Neural Text-to-Speech & Selection Speaker Plugin

Ultra-low-latency local neural text-to-speech for `py-agent` and Wayland desktops (Hyprland / Sway) using Kokoro in RAM-disk (`/dev/shm`).

---

## 1. Using in Py-Agent (CLI / TUI)

Inside active `ai` chat or Textual TUI (`/tui`):

* **Toggle TTS ON/OFF:** `/tts`
* **Change Voice Speed:** `/tts 1.25` (accepts `0.5` – `2.5`)
* **Reset to Default Speed:** `/tts reset` (resets to `1.15x`)
* **Stop Speech Immediately:** Say or type `stop talking`, `stop speech`, or `kill tts`

*Responses are read aloud via PipeWire, automatically filtering out code blocks and `<think>` reasoning tags.*

---

## 2. Desktop Selection Speaker (Hyprland / Wayland)

The bundled script (`koko-speak.sh`) allows you to highlight any text anywhere on your screen (browser, PDF, code editor) and hear it read aloud using the exact same voice and speed settings.

#### Hyprland Lua:
```lua
hl.bind("SUPER + SHIFT + R", hl.dsp.exec_cmd(home .. "/.config/py-agent/plugins/audio/koko-speak.sh"))
hl.bind("SUPER + SHIFT + X", hl.dsp.exec_cmd('pkill -9 -f "pw-play|koko"'))
```

---

## 3. Dependencies (Arch Linux)

```bash
yay -S koko-bin pw-play wl-clipboard
```
