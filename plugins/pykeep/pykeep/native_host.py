#!/usr/bin/env python3
"""
native_host.py — Ephemeral host launched on-demand by Brave.
Alive for ~50ms to answer the query, then immediately shuts down.
"""

import json
import struct
import sys
from pathlib import Path
from urllib.parse import urlparse

import configparser
import os
import pykeepass

CONFIG_FILE = Path(__file__).parent / "config.ini"


def get_db_path() -> Path:
    """Reads database path from config.ini, falls back to ~/passwords.kdbx."""
    if CONFIG_FILE.exists():
        cfg = configparser.ConfigParser()
        try:
            cfg.read(CONFIG_FILE)
            if cfg.has_section("pykeep") and "database" in cfg["pykeep"]:
                return Path(os.path.expanduser(cfg["pykeep"]["database"]))
        except Exception:
            pass
    return Path.home() / "passwords.kdbx"


def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        return None
    message_length = struct.unpack("@I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)


def send_message(message_content):
    encoded = json.dumps(message_content).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("@I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def find_matching_entry(kp, page_url):
    parsed = urlparse(page_url)
    hostname = (parsed.hostname or "").lower()
    full_url = page_url.lower()

    # 1. Match IP or hostname in entry URL
    for e in kp.entries:
        if e.url and (hostname in e.url.lower() or e.url.lower() in full_url):
            return e

    # 2. Match Title in URL
    for e in kp.entries:
        if e.title and e.title.lower() in full_url:
            return e

    # 3. Match generic router keywords if on local gateway
    if hostname in ("192.168.1.1", "192.168.0.1", "10.0.0.1"):
        for e in kp.entries:
            title = (e.title or "").lower()
            if any(k in title for k in ("wrt", "router", "openwrt", "gateway")):
                return e

    return None


def main():
    data = read_message()
    if not data:
        return

    master_pwd = data.get("password", "")
    page_url = data.get("url", "")

    db_path = get_db_path()
    try:
        kp = pykeepass.PyKeePass(str(db_path), password=master_pwd)
    except Exception:
        send_message({"error": "Invalid master password"})
        return

    entry = find_matching_entry(kp, page_url)
    if entry:
        send_message({
            "found": True,
            "title": entry.title,
            "username": entry.username or "",
            "password": entry.password or "",
        })
    else:
        send_message({"found": False})


if __name__ == "__main__":
    main()
