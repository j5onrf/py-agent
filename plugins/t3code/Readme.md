# T3 Code Plugin (`plugins/t3code`)

ACP stdio bridge connecting T3 Code to Py-Agent for local tool execution, OKF memory, and model reasoning.

---

## 1. Installation

```bash
sudo pacman -S t3code-bin   # Arch / Omarchy
# or: yay -S t3code-bin
```

---

## 2. Headless Configuration (`~/.t3/userdata/settings.json`)

Add the provider block directly to configure without using the GUI:

```json
{
  "providerInstances": {
    "py-agent": {
      "driver": "acp",
      "name": "Py-Agent",
      "command": "/usr/bin/python3",
      "args": ["/home/j5/.config/py-agent/plugins/t3code/t3code-bridge.py"],
      "enabled": true
    }
  }
}
```

*(GUI Alternative: Settings `⚙` → Providers → Add Provider → Local Command).*

---

## 3. Usage

Inside Py-Agent:
```console
~ ❯ ling
❯ /t3        # Launch Desktop UI
❯ /t3 web    # Launch Browser UI
```

Direct from shell:
```bash
~/.config/py-agent/plugins/t3code/launch.sh [web]
```

---

## 4. Components

* **`t3code-bridge.py`**: ACP JSON-RPC stdio server handling sessions, streaming, and tool execution.
* **`launch.sh`**: Resolves workspace directory, frees port 3773 on dirty exits, and cleans child processes on exit.
