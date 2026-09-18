# Plugins: `plugins/`

User extension directory for adding standalone scripts and custom Model Context Protocol (MCP) servers without modifying core agent files.

---

## 1. Adding Custom Scripts

1. **Create Executable:** Place your script (`.py`, `.sh`, or binary) in `plugins/` and make it executable:
   ```bash
   chmod +x ~/.config/py-agent/plugins/my-script
   ```

2. **Map Trigger in `ai-context.md`:** Register a keyword trigger in `~/.config/py-agent/ai-context.md`:
   ```properties
   [TOOL] ~/.config/py-agent/plugins/my-script --cat ---> my tool, run script
   ```

---

## 2. Adding Custom MCP Servers

1. **Store API Keys in `.env`:** `~/.config/py-agent/.env`:
   ```env
   MY_SERVICE_API_KEY="secret-key-here"
   ```

2. **Register Server in `servers.json`:** Add the server configuration to `~/.config/py-agent/plugins/mcp/servers.json` and reference the variable with `${VAR_NAME}`:
   ```json
   "my-server": {
     "command": "npx",
     "args": ["-y", "mcp-server-pkg"],
     "env": {
       "API_KEY": "${MY_SERVICE_API_KEY}"
     }
   }
   ```

3. **Test & Route:** Run `mcp list` to inspect discovered tools, or map shortcuts to `ai-context.md`:
   ```properties
   [TOOL] ~/.config/py-agent/plugins/mcp/mcp_client.py call my-server my-tool ---> my mcp tool
   ```
