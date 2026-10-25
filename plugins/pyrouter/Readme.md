# OpenCode + PyRouter Setup

### 1. Install OpenCode
```bash
sudo pacman -S opencode
# or: curl -fsSL https://opencode.ai/install | bash
```

### 2. Configure `~/.config/opencode/opencode.json`
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "pyrouter": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "PyRouter",
      "options": {
        "baseURL": "http://127.0.0.1:20128/v1",
        "apiKey": "local"
      }
    }
  }
}
```

### 3. Configure `~/.config/py-agent/.env`
```env
# ── 3. Custom 3 / PyRouter Gateway (Port 20128) ──────────────────────────────
CUSTOM3_API_KEY="not-needed"
CUSTOM3_URL="http://127.0.0.1:20128/v1/chat/completions"
CUSTOM3_MODEL="big-pickle"
```

### 4. Run
Toggle PyRouter to `RUNNING` in `model select` (under Auxiliary Services), then launch:
```bash
workspace
```
