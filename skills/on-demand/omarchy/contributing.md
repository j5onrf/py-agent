---
name: contributing
description: Generate diagnostics, report Omarchy bugs, and submit upstream pull requests.
---

# Bug Reporting & Upstream Directives

## Diagnostics Collection (MANDATORY flags):
```bash
omarchy version
# Generate diagnostic report (writes to /tmp/omarchy-debug.log without hanging terminal)
omarchy debug --no-sudo --print
