# Py-Agent Zed Integration

Connects `py-agent` to Zed's Agent Panel (via ACP - Agent Client Protocol) and enables autonomous tool execution, file editing, and in-editor inline transformations.

---

## 1. Configure Zed

Add the Agent Server and local model definitions to `~/.config/zed/settings.json`:

```json
{
  "agent": {
    "sidebar_side": "left",
    "dock": "right",
    "inline_assistant_model": {
      "provider": "openai",
      "model": "Ling-3.0-tiny"
    }
  },
  "language_models": {
    "openai": {
      "api_url": "http://127.0.0.1:8080/v1",
      "available_models": [
        {
          "name": "Ling-3.0-tiny",
          "max_tokens": 8192
        },
        {
          "name": "Qwen3.8-35B-Distill",
          "max_tokens": 8192
        },
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

> **Note on `AI_CONFIRM_GATES=0`:** Because Zed communicates over headless stdio without an interactive TTY, `AI_CONFIRM_GATES=0` is required to allow in-bounds workspace tool execution (`write_file`, `edit_file`, `run_command`) without blocking on CLI confirmation prompts.

---

## 2. Usage

### A. Autonomous Agent Panel (Multi-Turn & Tools)
1. Open the Agent panel on the right (`Ctrl-?` or click the panel icon).
2. Click `+` to open a new conversation thread.
3. Select `py-agent` from the agent server selector.
4. Enter your request (e.g., `write a python binary search tree with insert and search methods`).
5. The agent streams its thinking process, writes the files directly into your open workspace, runs verification commands, and fixes any errors in place.

### B. Inline Buffer Assistant (In-Place Code Edits)
1. Place the cursor on a line or highlight code in an editor buffer.
2. Press `Ctrl-Enter` (or `Cmd-Enter` on macOS).
3. Enter a code transformation instruction (e.g., `add type hints`, `refactor into a dataclass`) and press `Enter`.
4. Accept the inline diff (`Ctrl-Enter` or `Enter`) or reject it (`Escape`).

---

## 3. Troubleshooting

- **Tool shows a red X (`failed` / `[denied]`):** Ensure `AI_CONFIRM_GATES=0` is present in the `args` line and under `"env"` in your `settings.json`.
- **Local model offline:** Verify your local inference server (e.g., llama.cpp, vLLM, or Ollama) is running on `http://127.0.0.1:8080/v1`.
- **Debug output:** Review bridge output in Zed's logs or run `tail -f ~/.config/py-agent/.request_log`.

