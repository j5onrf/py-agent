# YT Transcript to Clipboard

A lightweight, privacy-focused browser extension that extracts YouTube video transcripts on-demand and copies them straight to your Wayland clipboard.

## Features
- **Zero Background Footprint:** Entirely dormant while browsing YouTube; makes zero network requests or DOM injections until you explicitly open the popup or press the hotkey.
- **PoToken Bypass:** Automatically handles modern YouTube caption structures (`json3`, `srv3`, and legacy XML) using internal client fallbacks.
- **Multiple Formats:** Instant options for continuous clean text or timestamped line-by-line blocks, complete with word count and file size diagnostics.

---

## Setup & Installation

1. Open **Brave** (or any Chromium-based browser) and navigate to:
   ```text
   brave://extensions
   ```
2. Enable **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button in the top-left corner.
4. Select your plugin directory:
   ```text
   ~/.config/py-agent/plugins/yt-transcript
   ```

---

## Usage

1. Open any YouTube video or Short.
2. Press **`Alt + Y`** (or click the extension icon in your toolbar).
3. Click either **"Copy Clean Text"** or **"Copy with Timestamps"**.
4. Paste (`Ctrl + V`) anywhere on your system (fully compatible with Wayland via `wl-clipboard`).

