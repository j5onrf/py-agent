#!/usr/bin/env python3
"""
pykeep.py — High-Performance Lightweight KeePass TUI built with Textual
Hardened with defensive config parsing, safe subprocess handling,
strict entry binding in modals, and diagnostic unlock error reporting [ocr 0.01].
"""

import configparser
import json
import os
import subprocess
import time
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, DataTable, Footer, Input, Label, Static

CONFIG_FILE = Path(__file__).parent / "config.ini"
STATE_FILE = Path(__file__).parent / ".state.json"

# Global lazy module holders
_pyotp = None


def get_pyotp():
    global _pyotp
    if _pyotp is None:
        import pyotp
        _pyotp = pyotp
    return _pyotp


class CachedItem:
    """Pre-computed search cache with slots for zero attribute-lookup overhead."""
    __slots__ = ("entry", "search_blob", "cells")

    def __init__(self, entry, search_blob, cells):
        self.entry = entry
        self.search_blob = search_blob
        self.cells = cells


def get_saved_theme() -> str:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("theme", "code1")
        except Exception:
            pass
    return "code1"


def save_theme(theme_name: str) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"theme": theme_name}, f, indent=2)
    except Exception:
        pass


def safe_int(value: object, default: int = 30) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def generate_password(length: int = 20) -> str:
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_db_backup(db_path_str: str) -> Path | None:
    import shutil
    from datetime import datetime
    db_path = Path(db_path_str).expanduser()
    if not db_path.exists():
        return None
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{db_path.stem}_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_file)
    return backup_file


# Themes
code1_theme = Theme(
    name="code1",
    primary="#89b4fa",
    secondary="#a6adc8",
    accent="#89b4fa",
    background="#11121d",
    surface="#161726",
    panel="#1b1c2b",
)
code2_theme = Theme(
    name="code2",
    primary="#ff9e64",
    secondary="#e0af68",
    accent="#ff9e64",
    background="#11121d",
    surface="#161726",
    panel="#1b1c2b",
)
dark_theme = Theme(
    name="dark",
    primary="#00d7d7",
    secondary="#b0b0b0",
    accent="#ffffff",
    background="#121212",
    surface="#1c1c1c",
    panel="#242424",
)


def load_config() -> dict[str, str]:
    defaults = {
        "database": str(Path.home() / "Documents/Pass/Passwords.kdbx"),
        "keyfile": "",
        "clipboard_timeout": "30",
    }
    if CONFIG_FILE.exists():
        config = configparser.ConfigParser()
        try:
            config.read(CONFIG_FILE)
            if config.has_section("pykeep"):
                return {**defaults, **dict(config["pykeep"])}
        except Exception:
            pass
    return defaults


def copy_to_clipboard(text: str, label: str, timeout: int = 30) -> bool:
    try:
        subprocess.run(["wl-copy", text], check=True)
    except (FileNotFoundError, subprocess.SubprocessError):
        return False

    try:
        subprocess.run([
            "notify-send", "-u", "low", "-t", "2000",
            "pykeep", f"Copied {label} (clears in {timeout}s)"
        ], check=False)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    if timeout > 0:
        try:
            subprocess.Popen(
                ["sh", "-c", 'sleep "$1" && wl-copy --clear', "_", str(timeout)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
    return True


def extract_totp(entry):
    uri = getattr(entry, "otp", None)
    if uri:
        try:
            totp = get_pyotp().parse_uri(uri)
            rem = 30 - (int(time.time()) % 30)
            return totp.now(), rem
        except Exception:
            pass

    custom = getattr(entry, "custom_properties", {}) or {}
    for key in ("TOTP Seed", "TimeOtp-Secret", "otp", "TOTP"):
        if key in custom:
            try:
                totp = get_pyotp().TOTP(custom[key])
                rem = 30 - (int(time.time()) % 30)
                return totp.now(), rem
            except Exception:
                pass
    return None, 0


def get_raw_totp_secret(entry) -> str:
    uri = getattr(entry, "otp", None)
    if uri:
        return str(uri)
    custom = getattr(entry, "custom_properties", {}) or {}
    for key in ("TOTP Seed", "TimeOtp-Secret", "otp", "TOTP"):
        if key in custom:
            return str(custom[key])
    return ""


class SetTotpModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, entry_title: str):
        super().__init__()
        self.entry_title = entry_title

    def compose(self) -> ComposeResult:
        with Vertical(id="totp-box"):
            yield Label(f"󰦖 Configure 2FA for '{self.entry_title}'", id="totp-title")
            yield Static("Paste the secret key from the website (or otpauth:// URI):", id="totp-help")
            yield Input(placeholder="e.g. JBSWY3DPEHPK3PXP...", id="totp-secret")
            with Horizontal(id="modal-actions"):
                yield Button("Cancel", id="btn-cancel", variant="error")
                yield Button("Save 2FA", id="btn-save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#totp-secret").focus()

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-save")
    def action_save(self) -> None:
        secret = self.query_one("#totp-secret", Input).value.strip()
        if not secret:
            self.notify("Secret cannot be empty!", severity="error")
            return
        self.dismiss(secret)


class ConfirmDeleteModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, entry_title: str):
        super().__init__()
        self.entry_title = entry_title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label("󰆴 Delete Account", id="confirm-title")
            yield Static(
                f"Are you sure you want to permanently delete:\n\n[bold red]{self.entry_title}[/]?",
                id="confirm-text",
            )
            with Horizontal(id="modal-actions"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Delete", id="btn-delete", variant="error")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel").focus()

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#btn-delete")
    def action_delete(self) -> None:
        self.dismiss(True)


class EditEntryModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+g", "gen_password", "Gen Pass"),
    ]

    def __init__(self, entry):
        super().__init__()
        self.entry = entry

    def compose(self) -> ComposeResult:
        with Vertical(id="add-box"):
            yield Label(f"󰏫 Edit '{self.entry.title}'", id="add-title")
            yield Input(value=self.entry.title or "", placeholder="Title...", id="entry-title")
            yield Input(value=self.entry.username or "", placeholder="Username / Email...", id="entry-username")
            with Horizontal(id="pass-row"):
                yield Input(value=self.entry.password or "", placeholder="Password...", id="entry-password")
                yield Button("󰒃 Gen", id="btn-gen", variant="warning")
            yield Input(value=self.entry.url or "", placeholder="URL...", id="entry-url")
            yield Input(
                value=get_raw_totp_secret(self.entry),
                placeholder="2FA Secret Key or otpauth:// (optional)...",
                id="entry-totp",
            )
            with Horizontal(id="modal-actions"):
                yield Button("Cancel", id="btn-cancel", variant="error")
                yield Button("Save Changes", id="btn-save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#entry-title").focus()

    @on(Button.Pressed, "#btn-gen")
    def on_gen_click(self) -> None:
        self.action_gen_password()

    def action_gen_password(self) -> None:
        pwd_input = self.query_one("#entry-password", Input)
        pwd_input.value = generate_password(20)
        self.notify("Generated new password", title="Generator")

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-save")
    def action_save(self) -> None:
        title = self.query_one("#entry-title", Input).value.strip()
        username = self.query_one("#entry-username", Input).value.strip()
        password = self.query_one("#entry-password", Input).value.strip()
        url = self.query_one("#entry-url", Input).value.strip()
        totp = self.query_one("#entry-totp", Input).value.strip()

        if not title:
            self.notify("Title is required!", severity="error")
            return

        self.dismiss({
            "title": title,
            "username": username,
            "password": password,
            "url": url,
            "totp": totp,
        })


class AddEntryModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+g", "gen_password", "Gen Pass"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-box"):
            yield Label("󰆓 Add New Account", id="add-title")
            yield Input(placeholder="Title (e.g. GitHub, Router)...", id="entry-title")
            yield Input(placeholder="Username / Email...", id="entry-username")
            with Horizontal(id="pass-row"):
                yield Input(placeholder="Password...", id="entry-password")
                yield Button("󰒃 Gen", id="btn-gen", variant="warning")
            yield Input(placeholder="URL (e.g. https://github.com)...", id="entry-url")
            with Horizontal(id="modal-actions"):
                yield Button("Cancel", id="btn-cancel", variant="error")
                yield Button("Save Entry", id="btn-save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#entry-title").focus()

    @on(Button.Pressed, "#btn-gen")
    def on_gen_click(self) -> None:
        self.action_gen_password()

    def action_gen_password(self) -> None:
        pwd_input = self.query_one("#entry-password", Input)
        pwd_input.value = generate_password(20)
        self.notify("Generated 20-character password", title="Generator")

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-save")
    def action_save(self) -> None:
        title = self.query_one("#entry-title", Input).value.strip()
        username = self.query_one("#entry-username", Input).value.strip()
        password = self.query_one("#entry-password", Input).value.strip()
        url = self.query_one("#entry-url", Input).value.strip()

        if not title:
            self.notify("Title is required!", severity="error")
            return

        self.dismiss({
            "title": title,
            "username": username,
            "password": password,
            "url": url,
        })


class PyKeepApp(App):
    THEMES = ["code1", "code2", "dark"]

    CSS = """
    Screen {
        background: $background;
        align: center middle;
    }
    #unlock-box {
        width: 60;
        height: auto;
        border: round $primary;
        padding: 1 2;
        background: $surface;
    }
    #main-layout {
        width: 100%;
        height: 100%;
        padding: 1;
        background: $background;
    }
    #search-bar {
        border: round $primary;
        margin-bottom: 1;
        background: $surface;
        color: $text;
    }
    #split-pane {
        width: 100%;
        height: 1fr;
    }
    DataTable {
        width: 65%;
        height: 100%;
        border: round $panel;
        background: $surface;
        color: $text;
    }
    DataTable > .datatable--cursor {
        background: $panel;
        color: $primary;
        text-style: bold;
    }
    #details-pane {
        width: 35%;
        height: 100%;
        margin-left: 1;
        padding: 1 2;
        border: round $panel;
        background: $surface;
    }
    #unlock-title, #pane-title, #add-title, #totp-title, #confirm-title {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }
    #confirm-title {
        color: #f38ba8;
    }
    Footer {
        background: $surface;
    }

    AddEntryModal, EditEntryModal, ConfirmDeleteModal, SetTotpModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #add-box, #totp-box {
        width: 65;
        height: auto;
        border: round $primary;
        padding: 1 2;
        background: $surface;
    }
    #confirm-box {
        width: 50;
        height: auto;
        border: round #f38ba8;
        padding: 1 2;
        background: $surface;
    }
    #confirm-text {
        margin-bottom: 1;
    }
    #totp-help {
        margin-bottom: 1;
        color: #a6adc8;
    }
    #add-box Input, #totp-box Input {
        margin-bottom: 1;
        background: $panel;
        border: round $panel;
    }
    #pass-row {
        height: auto;
        margin-bottom: 1;
    }
    #pass-row Input {
        width: 80%;
        margin-bottom: 0;
    }
    #pass-row Button {
        width: 20%;
        margin-left: 1;
    }
    #modal-actions {
        margin-top: 1;
        align: right middle;
        height: auto;
    }
    #modal-actions Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "add_entry", "New (Add)", show=True),
        Binding("a", "add_entry", "Add", show=False),
        Binding("e", "edit_entry", "Edit", show=True),
        Binding("d", "delete_entry", "Delete", show=True),
        Binding("ctrl+d", "delete_entry", "Delete", show=False),
        Binding("delete", "delete_entry", "Delete", show=False),
        Binding("b", "create_backup", "Backup", show=True),
        Binding("p", "copy_password", "Pass", show=True),
        Binding("u", "copy_username", "User", show=True),
        Binding("t", "copy_totp", "TOTP", show=True),
        Binding("s", "set_totp", "Set 2FA", show=True),
        Binding("o", "open_url", "URL", show=True),
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
        Binding("/", "focus_search", "Search", show=False),
        Binding("escape", "handle_escape", "Back", show=True),
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.kp = None
        self.cached_items: list[CachedItem] = []
        self.filtered_items: list[CachedItem] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="unlock-box"):
            yield Label("󰌾 Unlock Vault", id="unlock-title")
            yield Input(placeholder="Enter Master Password...", password=True, id="master-pwd")

        with Vertical(id="main-layout"):
            yield Input(placeholder="󱞩 Search accounts (Title, User, URL, Group)...", id="search-bar")
            with Horizontal(id="split-pane"):
                yield DataTable(id="entry-table", cursor_type="row")
                with Vertical(id="details-pane"):
                    yield Label("󱞩 Entry Inspector", id="pane-title")
                    yield Static("", id="details-text")
            yield Footer()

    def on_mount(self) -> None:
        if hasattr(self, "register_theme"):
            for t in (code1_theme, code2_theme, dark_theme):
                try:
                    self.register_theme(t)
                except Exception:
                    pass
        saved = get_saved_theme()
        self.theme = saved if saved in self.THEMES else "code1"

        self.query_one("#main-layout").display = False
        self.query_one("#master-pwd").focus()

    @property
    def current_accent(self) -> str:
        t = getattr(self, "theme", "code1")
        return {
            "code1": "#89b4fa",
            "code2": "#ff9e64",
            "dark": "#00d7d7",
        }.get(t, "#89b4fa")

    @on(Input.Submitted, "#master-pwd")
    def unlock(self, event: Input.Submitted) -> None:
        db_path = os.path.expanduser(self.cfg.get("database", ""))
        keyfile = os.path.expanduser(self.cfg.get("keyfile", "")) or None

        if not os.path.exists(db_path):
            event.input.value = ""
            event.input.placeholder = f"❌ File not found: {db_path}"
            return

        if keyfile and not os.path.exists(keyfile):
            event.input.value = ""
            event.input.placeholder = f"❌ Keyfile not found: {keyfile}"
            return

        try:
            import pykeepass
        except ImportError:
            event.input.value = ""
            event.input.placeholder = "❌ Missing module: pykeepass"
            return

        try:
            self.kp = pykeepass.PyKeePass(db_path, password=event.value, keyfile=keyfile)
        except (pykeepass.exceptions.CredentialsError, pykeepass.exceptions.HeaderChecksumError):
            event.input.value = ""
            event.input.placeholder = "❌ Invalid Password / Key. Try again..."
            return
        except Exception as err:
            event.input.value = ""
            event.input.placeholder = f"❌ Error loading database: {err}"
            return

        self.query_one("#unlock-box").display = False
        self.query_one("#main-layout").display = True

        table = self.query_one(DataTable)
        table.add_columns("Group", "Title", "Username", "2FA")

        self.rebuild_cache()
        self.query_one("#search-bar").focus()
        self.set_interval(1.0, self.tick_live_totp)

    def rebuild_cache(self):
        items = []
        for e in self.kp.entries:
            if not e.title:
                continue
            totp, _ = extract_totp(e)
            grp = e.group.name if e.group else "Root"
            totp_badge = "󰦖 Active" if totp else "—"
            cells = (grp, e.title or "", e.username or "", totp_badge)
            blob = f"{e.title} {e.username or ''} {e.url or ''} {e.notes or ''} {grp}".lower()
            items.append(CachedItem(e, blob, cells))

        self.cached_items = items
        q = self.query_one("#search-bar", Input).value.lower().strip()
        self.filtered_items = [ci for ci in items if q in ci.search_blob] if q else items
        self.refresh_table()

    def refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()
        if self.filtered_items:
            table.add_rows([ci.cells for ci in self.filtered_items])
            table.cursor_coordinate = (0, 0)
            self.update_inspector(self.filtered_items[0].entry)
        else:
            self.query_one("#details-text").update("[bold red]No matching entries found.[/]")

    @on(Input.Changed, "#search-bar")
    def filter_search(self, event: Input.Changed):
        q = event.value.lower().strip()
        if not q:
            self.filtered_items = self.cached_items
        else:
            self.filtered_items = [ci for ci in self.cached_items if q in ci.search_blob]
        self.refresh_table()

    @on(Input.Submitted, "#search-bar")
    def on_search_enter(self, event: Input.Submitted):
        self.query_one("#entry-table").focus()

    @on(DataTable.RowHighlighted, "#entry-table")
    def row_selected(self, event: DataTable.RowHighlighted):
        idx = event.cursor_row
        if 0 <= idx < len(self.filtered_items):
            self.update_inspector(self.filtered_items[idx].entry)

    def tick_live_totp(self):
        entry = self.get_current_entry()
        if entry:
            totp, _ = extract_totp(entry)
            if totp:
                self.update_inspector(entry)

    def update_inspector(self, entry):
        totp, rem = extract_totp(entry)
        totp_display = f"[bold #a6e3a1]{totp}[/] ([bold #e0af68]{rem}s[/] left)" if totp else "None configured"
        pwd_len = len(entry.password) if entry.password else 0
        acc = self.current_accent

        info = (
            f"[bold {acc}]Title:[/]\n{entry.title}\n\n"
            f"[bold {acc}]Username:[/]\n{entry.username or '—'}\n\n"
            f"[bold {acc}]Password:[/]\n{'•' * pwd_len} ({pwd_len} chars)\n\n"
            f"[bold {acc}]TOTP (2FA):[/]\n{totp_display}\n\n"
            f"[bold {acc}]URL:[/]\n{entry.url or '—'}\n\n"
            f"[bold {acc}]Notes:[/]\n{(entry.notes or '—')[:160]}"
        )
        self.query_one("#details-text").update(info)

    def get_current_entry(self):
        table = self.query_one(DataTable)
        try:
            row_idx = table.cursor_coordinate.row
            if 0 <= row_idx < len(self.filtered_items):
                return self.filtered_items[row_idx].entry
        except Exception:
            pass
        return None

    def action_add_entry(self):
        if not self.kp:
            return
        self.push_screen(AddEntryModal(), self.handle_entry_added)

    def handle_entry_added(self, data):
        if not data:
            return

        try:
            self.kp.add_entry(
                self.kp.root_group,
                data["title"],
                data["username"],
                data["password"],
                url=data.get("url", ""),
            )
            self.kp.save()
            self.rebuild_cache()
            self.notify(f"Saved '{data['title']}' to database!", title="Vault Saved")
        except Exception as err:
            self.notify(f"Failed to save entry: {err}", severity="error")

    def action_edit_entry(self):
        entry = self.get_current_entry()
        if not entry:
            self.notify("No entry selected to edit", severity="warning")
            return
        # Bind the specific entry instance to the callback to prevent selection-drift bugs
        self.push_screen(
            EditEntryModal(entry),
            lambda data: self.handle_entry_edited(entry, data),
        )

    def handle_entry_edited(self, entry, data):
        if not data or not entry:
            return

        try:
            entry.title = data["title"]
            entry.username = data["username"]
            entry.password = data["password"]
            entry.url = data.get("url", "")

            totp_val = data.get("totp", "").strip()
            if totp_val:
                if totp_val.startswith("otpauth://"):
                    try:
                        entry.otp = totp_val
                    except Exception:
                        pass
                    entry.set_custom_property("otp", totp_val)
                else:
                    clean = totp_val.replace(" ", "").upper()
                    entry.set_custom_property("TOTP Seed", clean)
            else:
                try:
                    entry.otp = None
                except Exception:
                    pass
                for k in ("TOTP Seed", "TimeOtp-Secret", "otp", "TOTP"):
                    try:
                        entry.delete_custom_property(k)
                    except Exception:
                        pass

            self.kp.save()
            self.rebuild_cache()
            self.update_inspector(entry)
            self.notify(f"Updated '{entry.title}'!", title="Vault Saved")
        except Exception as err:
            self.notify(f"Failed to update entry: {err}", severity="error")

    def action_delete_entry(self):
        entry = self.get_current_entry()
        if not entry:
            self.notify("No entry selected to delete", severity="warning")
            return
        # Bind the target entry instance directly so cursor changes cannot delete the wrong row
        self.push_screen(
            ConfirmDeleteModal(entry.title),
            lambda confirmed: self.handle_entry_deleted(entry, confirmed),
        )

    def handle_entry_deleted(self, entry, confirmed: bool):
        if not confirmed or not entry:
            return

        try:
            title = entry.title
            self.kp.delete_entry(entry)
            self.kp.save()
            self.rebuild_cache()
            self.notify(f"Deleted '{title}' from database!", title="Vault Updated")
        except Exception as err:
            self.notify(f"Failed to delete entry: {err}", severity="error")

    def action_set_totp(self):
        entry = self.get_current_entry()
        if not entry:
            self.notify("No entry selected", severity="warning")
            return
        self.push_screen(
            SetTotpModal(entry.title),
            lambda secret: self.handle_totp_saved(entry, secret),
        )

    def handle_totp_saved(self, entry, secret: str | None):
        if not secret or not entry:
            return

        try:
            clean = secret.strip()
            if clean.startswith("otpauth://"):
                try:
                    entry.otp = clean
                except Exception:
                    pass
                entry.set_custom_property("otp", clean)
            else:
                entry.set_custom_property("TOTP Seed", clean.replace(" ", "").upper())

            self.kp.save()
            self.rebuild_cache()
            self.update_inspector(entry)
            self.notify(f"2FA activated for '{entry.title}'!", title="2FA Configured")
        except Exception as err:
            self.notify(f"Failed to save 2FA: {err}", severity="error")

    def action_create_backup(self):
        db_path = self.cfg.get("database", "")
        backup = create_db_backup(db_path)
        if backup:
            self.notify(f"Backup created:\n{backup.name}", title="Backup Saved")
        else:
            self.notify("Failed to create backup", severity="error")

    def action_copy_password(self):
        entry = self.get_current_entry()
        timeout = safe_int(self.cfg.get("clipboard_timeout", 30), 30)
        if entry and entry.password:
            if copy_to_clipboard(entry.password, f"Password for '{entry.title}'", timeout):
                self.notify(f"Copied Password for '{entry.title}'", title="Clipboard")
            else:
                self.notify("Failed: wl-copy not found or failed", severity="error")

    def action_copy_username(self):
        entry = self.get_current_entry()
        timeout = safe_int(self.cfg.get("clipboard_timeout", 30), 30)
        if entry and entry.username:
            if copy_to_clipboard(entry.username, f"Username for '{entry.title}'", timeout):
                self.notify(f"Copied Username for '{entry.title}'", title="Clipboard")
            else:
                self.notify("Failed: wl-copy not found or failed", severity="error")

    def action_copy_totp(self):
        entry = self.get_current_entry()
        timeout = safe_int(self.cfg.get("clipboard_timeout", 30), 30)
        if entry:
            totp, _ = extract_totp(entry)
            if totp:
                if copy_to_clipboard(totp, f"TOTP for '{entry.title}'", timeout):
                    self.notify(f"Copied TOTP ({totp}) for '{entry.title}'", title="2FA Token")
                else:
                    self.notify("Failed: wl-copy not found or failed", severity="error")
            else:
                self.action_set_totp()

    def action_open_url(self):
        entry = self.get_current_entry()
        if entry and entry.url:
            try:
                subprocess.Popen(["xdg-open", entry.url])
                self.notify(f"Opened {entry.url}", title="Browser")
            except (FileNotFoundError, subprocess.SubprocessError) as err:
                self.notify(f"Failed to open URL: {err}", severity="error")

    def action_focus_search(self):
        self.query_one("#search-bar").focus()

    def action_handle_escape(self):
        """Esc goes back to search from the table; if already on empty search, exits."""
        if not self.query_one("#main-layout").display:
            self.exit()
            return

        table = self.query_one(DataTable)
        search_bar = self.query_one("#search-bar", Input)

        if self.focused == table:
            search_bar.focus()
        elif search_bar.value:
            search_bar.value = ""
        else:
            self.exit()

    def action_cycle_theme(self):
        try:
            idx = self.THEMES.index(self.theme) if self.theme in self.THEMES else 0
            self.theme = self.THEMES[(idx + 1) % len(self.THEMES)]
            save_theme(self.theme)
            entry = self.get_current_entry()
            if entry:
                self.update_inspector(entry)
            self.notify(f"Active Theme: {self.theme}", title="Theme Switcher")
        except Exception:
            pass


if __name__ == "__main__":
    app = PyKeepApp()
    app.run()
