# OpenBot Integration

Native ACP (Agent Client Protocol) Desktop GUI surface for Py-Agent.
https://github.com/nightly-labs/openbot

OpenBot connects directly to Py-Agent over standard I/O (JSON-RPC 2.0).
No background HTTP servers or port bridges are required.

---

## One-Time Setup

### 1. Permissions
Ensure the ACP adapter and OpenBot binary are executable:

```bash
chmod +x ~/.config/py-agent/plugins/openbot/pyagent_acp.py
chmod +x ~/.local/bin/openbot
```

### 2. Configure Py-Agent in OpenBot
1. Launch OpenBot (`openbot`).
2. Go to **Settings (Gear icon) → Providers**.
3. Under **Other providers**, select **ACP (Custom Agent)**:
   * **Name:** `py-agent`
   * **Command:** `/home/j5/.config/py-agent/plugins/openbot/pyagent_acp.py`
4. Click **Connect / Save**.
5. Set **Default provider** at the top of the screen to **`py-agent`**.

---

## How to Use

* **From an active CLI session (`ai` or `ai init`):**
  ```text
  /bot
  ```
* **Directly from terminal:**
  ```bash
  openbot
  ```

---

## Features
* **Zero OpenCode Overhead:** Py-Agent is the native execution engine; tools run directly on your filesystem.
* **Native OpenBot Formatting:** Thinking blocks render in the collapsible thought drawer; file edits and commands render as native step cards.
* **Model Agnostic:** Driven entirely by your active Py-Agent configuration (`llama-server` or `.env` cloud providers).
