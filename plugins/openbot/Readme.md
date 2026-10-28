# OpenBot Integration

Desktop GUI surface for Py-Agent.

---

## One-Time Setup

### 1. Permissions
Make the launch scripts and your OpenBot AppImage executable:

```bash
chmod +x ~/.config/py-agent/plugins/openbot/launch.sh
chmod +x ~/.config/py-agent/plugins/openbot/openbot_bridge.py
chmod +x ~/.local/share/openbot/openbot.AppImage 2>/dev/null || true
```

### 2. Add Py-Agent in OpenBot
1. Open OpenBot and click **Settings (Gear icon) → Providers → Add Provider**.
2. Enter:
   * **Provider Name / ID:** `py-agent`
   * **Base URL:** `http://127.0.0.1:8765/v1`
   * **Models:** `local-8080`, `gemini-3.5-flash-lite`

---

## How to Use

* **Inside a Py-Agent session (`ai` or `ai init`):**
  ```text
  /bot
  ```
* **Directly from terminal:**
  ```bash
  ~/.config/py-agent/plugins/openbot/launch.sh
  ```

Select **`py-agent/local-8080`** from OpenBot's top-right model dropdown.

