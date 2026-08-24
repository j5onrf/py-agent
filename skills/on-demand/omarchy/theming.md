---
name: theming
description: Switch themes, background wallpapers, custom color overlays, and desktop fonts.
---

# Theming & Appearance Directives

## Theme Commands:
- `omarchy theme list` -> List available themes
- `omarchy theme current` -> Show active theme
- `omarchy theme set <name>` -> Apply theme (e.g. `tokyo-night`, `catppuccin`)
- `omarchy theme bg next` -> Cycle wallpapers
- `omarchy theme install <git-url>` -> Install theme from repo

## Custom Theme Overlay (DO NOT edit `/usr/share/omarchy/themes/`):
To customize a stock theme without losing changes on updates:
```bash
mkdir -p ~/.config/omarchy/themes/<theme-slug>
cp /usr/share/omarchy/themes/<theme-slug>/colors.toml ~/.config/omarchy/themes/<theme-slug>/
# Edit ~/.config/omarchy/themes/<theme-slug>/colors.toml, then apply:
omarchy theme set <theme-slug>
```
- User wallpapers go in: `~/.config/omarchy/backgrounds/<theme-slug>/`

## Font Commands:
- `omarchy font list` -> List installed system fonts
- `omarchy font current` -> Show active font
- `omarchy font set <name>` -> Change desktop font
