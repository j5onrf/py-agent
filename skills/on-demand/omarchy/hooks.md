---
name: hooks
description: Create and install automated system event hooks in Omarchy.
---

# Automation Hooks Directives

## Hook Location & Installation:
- **Hook Folders:** `~/.config/omarchy/hooks/<event-name>.d/` (or flat script `~/.config/omarchy/hooks/<event-name>`)
- **Install Command:** `omarchy hook install <event-name> <path/to/script>` (auto-sets `chmod +x`)

## Available Event Triggers:
- `theme-set.d/` -> Runs after theme change (`$1` = theme slug)
- `font-set.d/` -> Runs after font change (`$1` = font name)
- `battery-low.d/` -> Low battery warning (`$1` = percentage)
- `post-boot.d/` -> Runs on desktop startup
- `post-update.d/` -> Runs during `omarchy update` after packages/migrations
- `pre-refresh-pacman.d/` -> Runs before `omarchy refresh pacman`
