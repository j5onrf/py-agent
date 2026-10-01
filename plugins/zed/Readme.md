# Py-Agent Zed Integration

Connects `py-agent` to Zed via the Agent Client Protocol (ACP) for autonomous tool execution and inline code transformations.

---

## 1. Configure Zed

Add the `local-model` and agent server definitions to `~/.config/zed/settings.json`:

```json
{
  "agent": {
    "sidebar_side": "left",
    "dock": "right",
    "inline_assistant_model": {
      "provider": "openai",
      "model": "local-model"
    }
  },
  "language_models": {
    "openai": {
      "api_url": "http://127.0.0.1:8080/v1",
      "available_models": [
        {
          "name": "local-model",
          "max_tokens": 8192
        }
      ]
    }
  },
  "agent_servers": {
    "py-agent": {
      "command": "sh",
      "args": [
        "-c",
        "exec env AI_CONFIRM_GATES=0 python3 ~/.config/py-agent/plugins/zed/gpui-bridge.py"
      ],
      "env": {
        "AI_CONFIRM_GATES": "0"
      },
      "type": "custom"
    }
  }
}
```

> **Note:** `local-model` automatically routes to whichever GGUF is currently loaded on `127.0.0.1:8080`. `AI_CONFIRM_GATES=0` allows in-bounds workspace tool execution over headless stdio without interactive TTY prompts.

---

## 2. Usage

### Launch from CLI
From any active workspace session, run:
```console
❯ /zed
```
This opens Zed on the current workspace and exports `AI_ACTIVE_SKILL` to sync the active profile.

### Agent Panel (Autonomous Tools)
1. Open the Agent panel on the right (`Ctrl-?`).
2. Select `py-agent` from the agent dropdown.
3. Enter requests (e.g., `write a python binary search tree with insert and search methods`). The agent runs tools, edits files, and verifies commands.

### Inline Buffer Assistant
1. Place the cursor on a line or highlight code in an editor buffer.
2. Press `Ctrl-Enter`.
3. Enter an instruction (e.g., `add type hints`) and press `Enter` to preview diffs.

---

## 3. Troubleshooting

- **Binary not found:** On Arch/CachyOS, verify if Zed is installed as `zeditor` (`which zeditor`).
- **Verify active profile:** Run `tail -n 30 ~/.local/share/zed/logs/Zed.log | grep zed-bridge` to confirm session initialization.
- **Tool shows a red X (`[denied]`):** Ensure `AI_CONFIRM_GATES=0` is present in `settings.json` under `"env"` and in the `"args"` line.
- **Local model offline:** Ensure your local server is running on `http://127.0.0.1:8080` (`curl http://localhost:8080/v1/models`).

