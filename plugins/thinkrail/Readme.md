# ThinkRail Integration

Desktop IDE surface for Py-Agent.
https://github.com/JetBrains/thinkrail

---

## One-Time Setup

### 1. Permissions
Make the launch script and bridge executable:

```bash
chmod +x ~/.config/py-agent/plugins/thinkrail/launch.sh
chmod +x ~/.config/py-agent/plugins/thinkrail/thinkrail_bridge.py
```

### 2. How to Use

* **Directly from terminal:**
  ```bash
  ~/.config/py-agent/plugins/thinkrail/launch.sh /path/to/your/project
  ```
* **Inside Py-Agent session (`ai` or `ai init`):**
  Add `/rail` or `/tr` to `modules/agent_commands.py` pointing to `launch.sh`.

### 3. Model Selection in ThinkRail
In the bottom model bar of ThinkRail, select:
**`py-agent-rail / Local 8080 (Py-Agent Rail)`**

### 4. Customizing Prompt Directives
The bridge prioritizes `~/.config/py-agent/skills/profiles/thinkrail.md` if it exists.
Create this file if you want to customize directives specifically for ThinkRail!
