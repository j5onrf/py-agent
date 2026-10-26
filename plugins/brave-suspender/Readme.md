# Tab Hibernate & Resume (Brave Suspender)

Lightweight tab suspender extension that frees memory by hibernating idle background tabs and intelligently remembers exact YouTube playback timestamps when resumed.

## Features
- **Auto-Hibernation:** Automatically suspends background tabs idle for more than 10 minutes (checked every 2 minutes).
- **YouTube Resume:** Captures current video playback time before suspension and appends `?t=Xs` so videos resume right where you left off.
- **Dimmed Real Favicons:** Pulls exact site favicons via Chrome internal API and dims them to 40% opacity on the suspension screen.
- **Context Menus & One-Click Toolbar Action:** Right-click anywhere to suspend current or background tabs, or click the toolbar button to hibernate all background tabs instantly.

---

## Setup & Installation

1. Open **Brave** (or any Chromium-based browser) and navigate to:
   ```text
   brave://extensions
   ```
2. Enable **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button in the top-left corner.
4. Select your plugin folder:
   ```text
   ~/.config/py-agent/plugins/brave-suspender
   ```
5. Pin the extension to your toolbar if desired. It will immediately begin monitoring and managing idle background tabs.

