# Py-Agent Zed Integration

Connects `py-agent` to Zed's Agent Panel (via ACP) and enables in-editor Inline Buffer Transformations.

---

## 1. Configure Zed

Add both the Agent Server and Inline Assistant to `~/.config/zed/settings.json`:

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
        "exec python3 ~/.config/py-agent/plugins/zed/gpui-bridge.py"
      ],
      "type": "custom"
    }
  }
}
```

---

## 2. Usage

### A. Autonomous Agent Panel (Multi-Turn & Tools)
1. Open the Agent panel on the right.
2. Click **`+`** to open a fresh thread.
3. Select **`py-agent`** from the agent dropdown.
4. Prompt the agent (handles file creation, test execution, and thinking drawers).

### B. Inline Buffer Assistant (In-Place Code Edits)
1. Place the cursor on a line or highlight code in the editor buffer.
2. Press **`Ctrl-Enter`** (or `Super-Enter`).
3. Enter a code transformation instruction (e.g., `add a docstring`, `refactor to async`) and press **Enter**.
4. Accept the inline diff (`Ctrl-Enter` or `Enter`) or reject it (`Escape`).

