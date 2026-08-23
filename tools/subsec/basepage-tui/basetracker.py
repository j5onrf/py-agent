#!/usr/bin/env python3
# Base Tracker TUI v0.8.0 [TUIAMP-Engine]

import json
import shutil
import sys
import termios
import tty
import urllib.request
from datetime import datetime

# --- Configuration ---
TRACK_TARGETS = {
    "1": {"name": "Hugging Face: HauhauCS", "type": "huggingface_user", "id": "HauhauCS"},
    "2": {"name": "Hugging Face: Unsloth", "type": "huggingface_org", "id": "unsloth"},
    "3": {"name": "Hugging Face: mradermacher", "type": "huggingface_user", "id": "mradermacher"},
    "4": {"name": "Hugging Face: Bartowski", "type": "huggingface_user", "id": "bartowski"},
    "5": {"name": "Hugging Face: MaziyarPanahi", "type": "huggingface_user", "id": "MaziyarPanahi"},
    "6": {"name": "Hugging Face: Arcee AI", "type": "huggingface_org", "id": "arcee-ai"},
}

LIMIT = 10  # Number of items to show per category

# --- UI Controls ---
def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\033':
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch

def print_header(subtitle=""):
    sys.stdout.write("\033[2J\033[H")  # Clear screen and home cursor
    c = [f"\033[3{i}m" for i in range(1, 6)]
    reset = "\033[0m"
    print("         \033[90m┌──────────────────────────────┐\033[0m")
    print("         \033[90m│\033[0m   \033[1;32m󰚌  B A S E T R A C K E R\033[0m   \033[90m│\033[0m")
    print("         \033[90m└──────────────────────────────┘\033[0m")
    if subtitle:
        print(f"               \033[1;35m// {subtitle}\033[0m\n")

def parse_iso_time(iso_str):
    if not iso_str:
        return "Unknown date"
    clean_stamp = iso_str.split('.')[0].replace('Z', '')
    try:
        dt = datetime.fromisoformat(clean_stamp)
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return iso_str

# --- Data Fetcher ---
def fetch_hf_data(username, sort_by):
    """Fetches data from HF API sorted by lastModified or createdAt."""
    url = f"https://huggingface.co/api/models?author={username}&sort={sort_by}&direction=-1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6.0) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        return None

# --- View Renderer ---
def render_target_view(target_config):
    print_header(f"Fetching Live Streams: {target_config['name']}")
    sys.stdout.flush()

    username = target_config["id"]
    now = datetime.now()
    
    if target_config["type"] in ("huggingface_user", "huggingface_org"):
        modified_models = fetch_hf_data(username, "lastModified")
        created_models = fetch_hf_data(username, "createdAt")
        
        if modified_models is None or created_models is None:
            print("  \033[1;31m⚠️ Error: Could not connect to Hugging Face API.\033[0m")
            input("\n  Press [Enter] to return to menu...")
            return

        while True:
            # Query current terminal dimensions
            W, H = shutil.get_terminal_size()
            
            # --- Redraw full screen header with a compact border panel ---
            sys.stdout.write("\033[2J\033[H")
            
            target_name = target_config["name"]
            target_type = target_config["type"].replace("huggingface_", "").capitalize()
            
            header_text = f"{target_name}  │  Type: {target_type}  │  Snapshots (Max {LIMIT})"
            sys.stdout.write(f"  \033[90m┌{'─' * (W - 6)}┐\033[0m\033[K\r\n")
            sys.stdout.write(f"  \033[90m│\033[0m \033[1;32m{header_text:<{W - 8}}\033[0m \033[90m│\033[0m\033[K\r\n")
            sys.stdout.write(f"  \033[90m└{'─' * (W - 6)}┘\033[0m\033[K\r\n\r\n")
            
            # --- SECTION 1: LAST 10 UPDATED ---
            sys.stdout.write(" \033[1;35m󰚌  RECENTLY UPDATED / MODIFIED\033[0m\033[K\r\n")
            sys.stdout.write(f"  \033[90m{'_' * (W - 6)}\033[0m\033[K\r\n\r\n")
            
            if not modified_models:
                sys.stdout.write("  No public repositories found.\033[K\r\n")
            else:
                for idx, model in enumerate(modified_models[:LIMIT], 1):
                    short_name = model.get("id", "Unknown").split('/')[-1]
                    raw_mod_time = model.get("lastModified", "")
                    formatted_time = parse_iso_time(raw_mod_time)
                    
                    # Compute dynamic badge state
                    badge_str = ""
                    badge_len = 0
                    if raw_mod_time:
                        try:
                            clean_stamp = raw_mod_time.split('.')[0].replace('Z', '')
                            days_old = (now - datetime.fromisoformat(clean_stamp)).days
                            if days_old <= 7:
                                badge_str = "\033[1;42;30m UPDATED \033[0m"
                                badge_len = 9
                        except Exception:
                            pass

                    date_str = f"Modified: {formatted_time}"
                    date_len = len(date_str)
                    
                    # Allocate exactly 40% of screen width for the model name
                    col_name_w = max(25, int(W * 0.4))
                    if len(short_name) > col_name_w:
                        display_name = f"{short_name[:col_name_w-3]}..."
                    else:
                        display_name = f"{short_name:<{col_name_w}}"
                        
                    # Calculate padding to dynamically align dates to the right-margin
                    pad_space = max(2, W - 10 - col_name_w - badge_len - date_len)
                    padding_str = " " * pad_space
                    
                    color = "\033[0m" if idx % 2 == 0 else "\033[38;5;246m"
                    sys.stdout.write(f"  {idx:2d}. \033[1;32m{display_name}\033[0m{padding_str}{badge_str}  {color}{date_str}\033[0m\033[K\r\n")

            sys.stdout.write(f"\r\n  \033[90m{'_' * (W - 6)}\033[0m\033[K\r\n\r\n")
            
            # --- SECTION 2: LAST 10 CREATED ---
            sys.stdout.write(" \033[1;33m󰚌  NEWEST REPOSITORIES CREATED\033[0m\033[K\r\n")
            sys.stdout.write(f"  \033[90m{'_' * (W - 6)}\033[0m\033[K\r\n\r\n")
            
            if not created_models:
                sys.stdout.write("  No public repositories found.\033[K\r\n")
            else:
                for idx, model in enumerate(created_models[:LIMIT], 1):
                    short_name = model.get("id", "Unknown").split('/')[-1]
                    raw_create_time = model.get("createdAt", "")
                    formatted_time = parse_iso_time(raw_create_time)
                    
                    badge_str = ""
                    badge_len = 0
                    if raw_create_time:
                        try:
                            clean_stamp = raw_create_time.split('.')[0].replace('Z', '')
                            days_old = (now - datetime.fromisoformat(clean_stamp)).days
                            if days_old <= 7:
                                badge_str = "\033[1;46;30m  NEW  \033[0m"
                                badge_len = 7
                        except Exception:
                            pass

                    date_str = f"Created:  {formatted_time}"
                    date_len = len(date_str)
                    
                    col_name_w = max(25, int(W * 0.4))
                    if len(short_name) > col_name_w:
                        display_name = f"{short_name[:col_name_w-3]}..."
                    else:
                        display_name = f"{short_name:<{col_name_w}}"
                        
                    pad_space = max(2, W - 10 - col_name_w - badge_len - date_len)
                    padding_str = " " * pad_space

                    color = "\033[0m" if idx % 2 == 0 else "\033[38;5;246m"
                    sys.stdout.write(f"  {idx:2d}. \033[1;36m{display_name}\033[0m{padding_str}{badge_str}  {color}{date_str}\033[0m\033[K\r\n")

            sys.stdout.write("\r\n\033[90m─────────────────────────────────────────────────────────────────────────────\033[0m\033[K\r\n")
            sys.stdout.write(" \033[90m[q/Enter] Return to Target Selection\033[0m\033[K\r\n")
            sys.stdout.flush()

            key = get_key()
            if key.lower() == 'q' or key == '\r':
                break

# --- Main Runtime Loop ---
def main():
    keys = list(TRACK_TARGETS.keys())
    selected = 0
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        while True:
            print_header("Active Platform Tracklist")
            print("  Select an item to run an on-demand update stream verification:\n")
            
            options = [TRACK_TARGETS[k]["name"] for k in keys] + ["Exit Tracking Utility"]
            
            for i, opt in enumerate(options):
                if i == selected:
                    sys.stdout.write(f"  \033[1;36m▶ {opt}\033[0m\n")
                else:
                    sys.stdout.write(f"    {opt}\n")
            sys.stdout.flush()
            
            key = get_key()
            if key == '\033[A':
                selected = (selected - 1) % len(options)
            elif key == '\033[B':
                selected = (selected + 1) % len(options)
            elif key == '\r':
                if selected == len(keys):
                    break
                else:
                    render_target_view(TRACK_TARGETS[keys[selected]])
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
