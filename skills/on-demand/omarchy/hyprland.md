---
name: hyprland
description: Hyprland Lua configuration: keybindings, monitors, look & feel, and window rules.
---

# Hyprland Config Directives

## Configuration Files (`~/.config/hypr/`):
- `bindings.lua` -> Keybindings
- `monitors.lua` -> Display outputs & scaling
- `looknfeel.lua` -> Gaps, borders, animations, blur
- `input.lua` -> Keyboard layout & mouse sensitivity
- `autostart.lua` -> Startup applications
- `hyprsunset.conf` -> Blue light filter (`omarchy restart hyprsunset` / `omarchy refresh hyprsunset`)

## Mandatory Validation Rule:
- After ANY `.lua` edit, you MUST execute: `hyprctl reload && hyprctl configerrors`
- Fix any reported syntax errors immediately. Reset defaults if corrupted: `omarchy refresh hyprland`

## Keybinding Protocol (`bindings.lua`):
1. View active bindings: `omarchy menu keybindings --print`
2. **Re-binding Rule:** If key exists, call `hl.unbind("<KEY>")` BEFORE `o.bind(...)`.
   ```lua
   hl.unbind("SUPER + F")
   o.bind("SUPER + F", "File Manager", { launch = "nautilus" })
   ```
3. Inform the user what the key was previously bound to.

## Monitor Configuration (`monitors.lua`):
- Inspect outputs: `hyprctl monitors all`
- Syntax: `hl.monitor({ output = "eDP-1", mode = "1920x1080@60", position = "0x0", scale = 1 })`

## Window Rules (`hyprland.lua`):
- Use Omarchy helper: `o.window(match, rules)` (see `$OMARCHY_PATH/default/hypr/windows.lua`).
