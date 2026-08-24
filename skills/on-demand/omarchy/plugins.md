---
name: plugins
description: Configure Omarchy status bar layout, Quickshell widgets, idle timeout, and lockscreen.
---

# Shell, Bar & Plugins Directives

## Configuration Files:
- `~/.config/omarchy/shell.json` -> Bar layout, active widgets, and idle rules (auto-reloads on save)
- `~/.config/omarchy/extensions/omarchy-menu.jsonc` -> Launcher menu layout
- Reset defaults: `omarchy refresh shell` | Restart process: `omarchy restart shell`

## Status Bar Management:
- Move widget: `omarchy bar move <plugin_id> --section <left|center|right>` (e.g. `omarchy bar move omarchy.clock --section right`)

## Customizing Built-In Widgets (DO NOT edit `/usr/share/omarchy/`):
```bash
omarchy plugin clone <plugin_id>
# Edits in ~/.config/omarchy/plugins/<user>.<plugin_id>/ auto-reload on save.
# Force rescan if needed: omarchy-shell shell rescanPlugins
```

## Idle & Lockscreen (`shell.json`):
Set timers in seconds:
- `idle.screensaver`: Seconds until display screensaver triggers.
- `idle.lock`: Seconds until lockscreen engages (e.g., 10 minutes = `600`).
