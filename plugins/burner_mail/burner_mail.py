#!/usr/bin/env python3
"""
Py-Agent Burner Mail Plugin
Location: ~/.config/py-agent/plugins/burner_mail.py
Sensitive data stored securely in: ~/.local/state/py-agent/burner_mail/
"""

import os
import time
import uuid
import re
import json
import subprocess
from pathlib import Path
import requests

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Static, ListView, ListItem, Label, Markdown
from textual import work

BASE = "https://api.mail.tm"

# ── XDG Secure Storage Isolation ──────────────────────────────────────────────
# Stored outside the Git repo in ~/.local/state/py-agent/burner_mail/
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "py-agent" / "burner_mail"
SESSION_FILE = STATE_DIR / "session.json"


def ensure_secure_storage() -> None:
    """Ensure the state directory exists with strict 0700 permissions."""
    if not STATE_DIR.exists():
        STATE_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    else:
        os.chmod(STATE_DIR, 0o700)


def save_secure_session(data: dict) -> None:
    """Save auth credentials with 0600 permissions."""
    ensure_secure_storage()
    # Write atomically
    temp_file = SESSION_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(temp_file, 0o600)
    temp_file.replace(SESSION_FILE)


def load_secure_session() -> dict | None:
    """Load existing active session if available."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def purge_secure_session() -> None:
    """Securely remove session file."""
    if SESSION_FILE.exists():
        try:
            SESSION_FILE.unlink()
        except OSError:
            pass


# ── UI Components ─────────────────────────────────────────────────────────────

class EmailItem(ListItem):
    """List item representing a single email."""
    def __init__(self, msg_data: dict, otp: str = None):
        super().__init__()
        self.msg_data = msg_data
        self.otp = otp

    def compose(self) -> ComposeResult:
        sender = self.msg_data.get("from", {}).get("address", "Unknown")
        subject = self.msg_data.get("subject", "(No Subject)")
        badge = f"[bold green][OTP: {self.otp}][/bold green] " if self.otp else ""
        yield Label(f"✉️ [bold cyan]{sender}[/bold cyan]\n   {badge}{subject}")


class BurnerMailApp(App):
    CSS = """
    Screen {
        background: #121212;
    }
    #top-bar {
        height: auto;
        padding: 1;
        background: #1e1e1e;
        border-bottom: solid #333333;
    }
    #email-label {
        width: 1fr;
        content-align: left middle;
        text-style: bold;
        color: #00ffaa;
    }
    #main-split {
        height: 1fr;
    }
    #inbox-pane {
        width: 40%;
        border-right: solid #333333;
        padding: 0 1;
    }
    #inbox-title {
        text-style: bold;
        padding: 1 0;
        color: #888888;
    }
    #body-pane {
        width: 60%;
        padding: 1 2;
        overflow-y: scroll;
    }
    #otp-box {
        background: #003322;
        border: solid #00aa66;
        color: #00ffaa;
        padding: 1;
        margin-bottom: 1;
        text-align: center;
        text-style: bold;
        display: none;
    }
    EmailItem {
        padding: 1;
        border-bottom: dashed #2a2a2a;
    }
    Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("n", "new_email", "New Email"),
        ("c", "copy_email", "Copy Email"),
        ("x", "purge_data", "Purge/Wipe"),
    ]

    def __init__(self):
        super().__init__()
        self.email_address = "Initializing secure session..."
        self.headers = {}
        self.seen_ids = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top-bar"):
            yield Label(self.email_address, id="email-label")
            yield Button("📋 Copy (c)", id="btn-copy", variant="primary")
            yield Button("🔄 New (n)", id="btn-new", variant="default")
            yield Button("🗑️ Wipe (x)", id="btn-wipe", variant="error")

        with Horizontal(id="main-split"):
            with Vertical(id="inbox-pane"):
                yield Label("📥 Inbox (Waiting for emails...)", id="inbox-title")
                yield ListView(id="email-list")
            with Vertical(id="body-pane"):
                yield Static(id="otp-box")
                yield Markdown("*Select an email from the left to read its contents.*", id="email-body")
        yield Footer()

    def on_mount(self) -> None:
        # Check if we have an existing session saved in ~/.local/state
        saved = load_secure_session()
        if saved and "token" in saved and "email" in saved:
            self.email_address = saved["email"]
            self.headers = {"Authorization": f"Bearer {saved['token']}"}
            self.update_email_ui()
            self.notify(f"Resumed session: {self.email_address}")
        else:
            self.action_new_email()

        # Poll inbox every 3 seconds
        self.set_interval(3.0, self.trigger_check)

    @work(thread=True)
    def action_new_email(self) -> None:
        """Create a fresh disposable inbox via Mail.tm API and save outside git."""
        self.email_address = "⏳ Contacting mail.tm..."
        self.call_from_thread(self.update_email_ui)

        try:
            domain_res = requests.get(f"{BASE}/domains", timeout=10).json()
            domain = domain_res["hydra:member"][0]["domain"]
            username = f"agent_{uuid.uuid4().hex[:8]}"
            email = f"{username}@{domain}"
            password = uuid.uuid4().hex

            requests.post(f"{BASE}/accounts", json={"address": email, "password": password}, timeout=10)
            token = requests.post(f"{BASE}/token", json={"address": email, "password": password}, timeout=10).json()["token"]

            self.email_address = email
            self.headers = {"Authorization": f"Bearer {token}"}
            self.seen_ids.clear()

            # Save strictly into ~/.local/state/py-agent/burner_mail/
            save_secure_session({
                "email": email,
                "password": password,
                "token": token,
                "created_at": int(time.time()),
            })

            self.call_from_thread(self.action_copy_email)
            self.call_from_thread(self.reset_inbox_ui)
        except Exception as e:
            self.email_address = f"Error: {e}"
            self.call_from_thread(self.update_email_ui)

    def action_purge_data(self) -> None:
        """Purge all cached credentials and session files from disk."""
        purge_secure_session()
        self.email_address = "(Session Purged)"
        self.headers = {}
        self.seen_ids.clear()
        self.reset_inbox_ui()
        self.notify("Session wiped from ~/.local/state", severity="warning")

    def update_email_ui(self) -> None:
        self.query_one("#email-label", Label).update(f"📬 {self.email_address}")

    def reset_inbox_ui(self) -> None:
        self.update_email_ui()
        self.query_one("#email-list", ListView).clear()
        self.query_one("#otp-box", Static).styles.display = "none"
        self.query_one("#email-body", Markdown).update("*Waiting for incoming verification emails...*")

    def action_copy_email(self) -> None:
        """Copy current email to Wayland/X11 clipboard."""
        if not self.email_address.startswith("agent_"):
            return
        self.copy_to_clipboard(self.email_address)
        try:
            subprocess.run(["wl-copy"], input=self.email_address.encode(), stderr=subprocess.DEVNULL)
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        self.notify(f"Copied: {self.email_address}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-copy":
            self.action_copy_email()
        elif event.button.id == "btn-new":
            self.action_new_email()
        elif event.button.id == "btn-wipe":
            self.action_purge_data()

    def trigger_check(self) -> None:
        if self.headers:
            self.check_inbox_worker()

    @work(thread=True)
    def check_inbox_worker(self) -> None:
        """Background thread checking for incoming emails."""
        try:
            res = requests.get(f"{BASE}/messages", headers=self.headers, timeout=5).json()
            messages = res.get("hydra:member", [])
            for msg in messages:
                msg_id = msg["id"]
                if msg_id not in self.seen_ids:
                    self.seen_ids.add(msg_id)
                    detail = requests.get(f"{BASE}/messages/{msg_id}", headers=self.headers, timeout=5).json()
                    self.call_from_thread(self.add_email_to_list, detail)
        except Exception:
            pass

    def add_email_to_list(self, detail: dict) -> None:
        body = detail.get("text") or detail.get("intro", "")
        match = re.search(r"\b(\d{6})\b", body)
        otp = match.group(1) if match else None

        item = EmailItem(detail, otp=otp)
        list_view = self.query_one("#email-list", ListView)
        list_view.append(item)
        self.query_one("#inbox-title", Label).update(f"📥 Inbox ({len(list_view.children)} messages)")

        self.render_email(detail, otp)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, EmailItem):
            self.render_email(event.item.msg_data, event.item.otp)

    def render_email(self, detail: dict, otp: str = None) -> None:
        sender = detail.get("from", {}).get("address", "Unknown")
        subject = detail.get("subject", "(No Subject)")
        body = detail.get("text") or detail.get("intro", "")

        otp_widget = self.query_one("#otp-box", Static)
        if otp:
            otp_widget.update(f"🔑 ONE-TIME CODE (OTP):  {otp}")
            otp_widget.styles.display = "block"
            self.copy_to_clipboard(otp)
            try:
                subprocess.run(["wl-copy"], input=otp.encode(), stderr=subprocess.DEVNULL)
            except Exception:
                pass
            self.notify(f"OTP auto-copied: {otp}", severity="information")
        else:
            otp_widget.styles.display = "none"

        md_content = f"### {subject}\n**From:** `{sender}`\n\n---\n\n{body}"
        self.query_one("#email-body", Markdown).update(md_content)


if __name__ == "__main__":
    app = BurnerMailApp()
    app.run()
