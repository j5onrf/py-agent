# WebUI Gateway

## 1. Launch

* **Inside `ai` CLI:** `/webui or /web`
* **From terminal:** `python3 ~/.config/py-agent/plugins/webui/server.py`

Open: **http://127.0.0.1:3000**

---

## 2. Ports

| Port | Service | Note |
| :---: | :--- | :--- |
| **8080** | `llama-server` | Backend engine |
| **3000** | **WebUI Gateway** | **Always use this port** (keeps agent tools & prompts active) |

---

## 3. Troubleshooting

* **404 File Not Found**: Change `--no-ui` to `--ui` in your model launch script and restart it.
* **502 Bad Gateway**: `llama-server` is not running. Launch your model script first.
