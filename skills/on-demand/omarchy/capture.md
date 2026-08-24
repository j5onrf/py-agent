---
name: capture
description: Screenshots, screen recordings, OCR text grab, LocalSend, and Taildrop sharing.
---

# Screen Capture & Sharing Directives

## Screenshots:
- Interactive: `omarchy screenshot`
- Region select: `omarchy capture screenshot region`
- Window select: `omarchy capture screenshot windows`
- Fullscreen straight to disk: `omarchy capture screenshot fullscreen save`
- Directory override: `export OMARCHY_SCREENSHOT_DIR="path"`

## Screen Recording:
- Start full screen: `omarchy screenrecord --fullscreen`
- Stop recording: `omarchy screenrecord --stop-recording` (outputs saved path)
- Flags: `--with-desktop-audio`, `--with-microphone-audio`, `--with-webcam`, `--resolution=<size>`
- Resize live webcam overlay: `omarchy capture webcam resize <smaller|larger|reset|small|medium|large>`
- Debug log: `OMARCHY_SCREENRECORD_DEBUG=true` (logs to `/tmp/omarchy-screenrecord.log`)
- Directory override: `export OMARCHY_SCREENRECORD_DIR="path"`

## OCR & File Sharing:
- **OCR Text Extraction:** `omarchy capture text` (extracts region text to clipboard)
- **LocalSend Sharing:** `omarchy share file <paths...>` | `omarchy share folder <path>` | `omarchy share clipboard`
- **Taildrop Sharing:** `omarchy tailscale send <machine> <file...>` | `omarchy tailscale receive [dir]`
- **Transcode Media:** `omarchy transcode <input> [format] [resolution]`
