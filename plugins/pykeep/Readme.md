# PyKeep

Lightweight, zero-daemon KeePass (`.kdbx`) TUI and on-demand Chromium/Brave autofill extension.

## Features
- **TUI (`pykeep.py`):** Fast Textual interface with live TOTP ticking, password generation, entry editing/deletion, and manual backups (`b`).
- **Browser Extension (`pykeep-browser`):** Zero-storage DOM autofill via native messaging. No background servers or open ports.

---

## 1. Requirements (Arch Linux)
```bash
sudo pacman -S python-pykeepass python-pyotp python-textual wl-clipboard libnotify
```

---

## 2. TUI Setup

1. Create a `config.ini` file inside `pykeep/`:
   ```ini
   [pykeep]
   database = ~/passwords.kdbx
   keyfile = 
   clipboard_timeout = 30
   ```

2. **Hyprland Keybinding:**
   Add this to your Hyprland configuration so **`SUPER + K`** opens PyKeep in a floating window:
   ```lua
   hl.bind("SUPER + K", hl.dsp.exec_cmd("uwsm app -- kitty --class pykeep_modal -e python3 ~/.config/py-agent/plugins/pykeep/pykeep/pykeep.py"))
   ```

### Keybindings
| Key | Action |
| :--- | :--- |
| `Enter` (search bar) | Jump focus to account list |
| `Ctrl + N` / `a` | Add new account (with password generator `Ctrl + G`) |
| `e` | Edit selected account (Title, User, Pass, URL, 2FA) |
| `d` / `Delete` | Delete selected account (confirmation prompt) |
| `p` / `u` | Copy Password / Username to clipboard |
| `t` | Copy 2FA code (auto-prompts setup if unconfigured) |
| `s` | Configure/Update 2FA secret |
| `b` | Create timestamped `.kdbx` backup snapshot |
| `Esc` | Back to search / clear search / quit |
| `q` | Quit immediately |

---

## 3. Browser Extension Setup (Brave / Chromium)

### Step A: Load the Extension
1. Open `brave://extensions` (or `chrome://extensions`).
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** and select:
   `~/.config/py-agent/plugins/pykeep/pykeep-browser`
4. Copy the generated 32-letter **Extension ID**.

### Step B: Configure Native Messaging Host
1. Open `pykeep_host.json` in the root of this plugin folder and update it with your absolute path and 32-letter Extension ID:
   ```json
   {
     "name": "pykeep_host",
     "description": "PyKeep On-Demand Native Host",
     "path": "/home/j5/.config/py-agent/plugins/pykeep/pykeep/native_host.py",
     "type": "stdio",
     "allowed_origins": [
       "chrome-extension://YOUR_EXTENSION_ID_HERE/"
     ]
   }
   ```

2. Make the native host script executable:
   ```bash
   chmod +x ~/.config/py-agent/plugins/pykeep/pykeep/native_host.py
   ```

3. Copy the JSON manifest to Brave's native messaging directory:
   ```bash
   mkdir -p ~/.config/BraveSoftware/Brave-Origin/NativeMessagingHosts
   cp pykeep_host.json ~/.config/BraveSoftware/Brave-Origin/NativeMessagingHosts/pykeep_host.json
   ```

4. **Restart your browser completely.**

### Usage
On any login page, click the **P** toolbar icon (or press `Alt + P`), enter your master password, and hit Enter. Credentials are injected directly into the page DOM, and the Python process terminates immediately with zero background footprint.

