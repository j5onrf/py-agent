# PhotoCraft MCP Integration

Headless and live-bridge image editing engine for Py-Agent via the Model Context Protocol (MCP). Built on [PhotoCraft](https://github.com/storytold/photocraft).

---

## 1. Installation

Install PhotoCraft and `photocraft-cli`:

### Arch Linux / CachyOS (AUR)
```bash
paru -S photocraft
# or
yay -S photocraft
```

### Build from Source (Cargo)
```bash
git clone https://github.com/storytold/photocraft.git /tmp/photocraft
cd /tmp/photocraft
cargo build --release -p photocraft -p photocraft-cli
install -m 755 target/release/photocraft target/release/photocraft-cli ~/.local/bin/
cd ~ && rm -rf /tmp/photocraft
```

---

## 2. Authentication Token Setup

PhotoCraft requires a 64-character hex control token for socket authentication:

```bash
mkdir -p ~/.config/photocraft
openssl rand -hex 32 > ~/.config/photocraft/control.token
chmod 600 ~/.config/photocraft/control.token
```

---

## 3. Configuration

Add the server definition to `~/.config/py-agent/plugins/mcp/servers.json`:

```json
{
  "servers": {
    "photocraft": {
      "command": "photocraft-cli",
      "args": [
        "mcp",
        "--bridge",
        "127.0.0.1:7878",
        "--control-token-file",
        "${HOME}/.config/photocraft/control.token",
        "--automation-read-root",
        "${HOME}",
        "--automation-write-root",
        "${HOME}"
      ],
      "env": {}
    }
  }
}
```

> **Headless Mode:** To run purely in the background without launching a desktop GUI, omit the `--bridge` and `--control-token-file` arguments.

---

## 4. Launch Desktop GUI (For Live Bridge)

To watch changes execute on screen, launch the desktop interface with control listening enabled:

```bash
photocraft --control 7878 \
  --control-token-file "$HOME/.config/photocraft/control.token" \
  --automation-read-root "$HOME" \
  --automation-write-root "$HOME"
```

---

## 5. Verification

Verify that Py-Agent detects the live tools:

```bash
python3 ~/.config/py-agent/plugins/mcp/mcp_client.py list photocraft
```

Expected output:
```text
Server: photocraft (20 tools)
  - doc_new
  - doc_open
  - doc_save
  - doc_inspect
  - command_run
  - ui_set
  ...
```

---

## 6. Agent Usage

Use the dedicated `photocraft-gem` profile for automated workflows:

```bash
ai init ~/your-workspace
```
Select **Photocraft Gem** as the profile, and instruct the agent to inspect, invert, or adjust open documents.

