#!/usr/bin/env python3
# model-select-local.py - Standalone Local Offline Model Selector with Auto-CPU Control

import asyncio
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import tty

MODELS_DIR = "/home/user/models"
SERV_DIR = "/home/user/models/serv"
STATE_FILE = "/tmp/cpu_mode_state"

# Map local GGUF filenames to their respective launch scripts
LOCAL_MODELS = [
    {
        "name": "LFM2.5-8B-A1B-APEX-I-Compact",
        "file": "LFM2.5-8B-A1B.gguf",
        "script": "lfm2.sh",
    },
    {"name": "Qwen 3.5 2B", "file": "Qwen3.5-2B.gguf", "script": "q2b.sh"},
    {
        "name": "Hermes3.6-35B-A3B-Uncensored-Genesis-V6-APEX",
        "file": "Herm3.6-35B-A3B.gguf",
        "script": "q35b.sh",
    },
]


# --- CPU POWER AUTOMATION ---
async def async_set_cpu_chill():
    try:
        await asyncio.create_subprocess_exec(
            "sudo",
            "-n",
            "cpupower",
            "frequency-set",
            "-g",
            "powersave",
            "--max",
            "3.5GHz",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(STATE_FILE, "w") as f:
            f.write("chill")
        if shutil.which("notify-send"):
            await asyncio.create_subprocess_exec(
                "notify-send",
                "CPU Mode",
                "OLLAMA CHILL (3.5 GHz) - Auto",
                "-u",
                "low",
                "-t",
                "2000",
            )
    except Exception:
        pass


async def async_set_cpu_balanced():
    try:
        await asyncio.create_subprocess_exec(
            "sudo",
            "-n",
            "cpupower",
            "frequency-set",
            "-g",
            "powersave",
            "--max",
            "4.4GHz",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(STATE_FILE, "w") as f:
            f.write("balanced")
        if shutil.which("notify-send"):
            await asyncio.create_subprocess_exec(
                "notify-send",
                "CPU Mode",
                "BALANCED (Dynamic) - Auto",
                "-u",
                "normal",
                "-t",
                "2000",
            )
    except Exception:
        pass


def get_current_running_model():
    try:
        output = subprocess.check_output(["pgrep", "-af", "llama-server"]).decode()
        for line in output.splitlines():
            match = re.search(r"-m\s+([^\s]+)", line)
            if match:
                return os.path.basename(match.group(1))
    except Exception:
        pass
    return None


# --- NON-BLOCKING POWER CLEAN ENGINE ---
async def async_stop_all_engines():
    targets = ["llama-server", "llama-cli"]
    for target in targets:
        try:
            pids = subprocess.check_output(["pgrep", "-x", target]).decode().split()
        except Exception:
            pids = []

        if pids:
            for pid in pids:
                try:
                    os.kill(int(pid), 15)
                except Exception:
                    pass

            terminated = False
            for _ in range(20):
                await asyncio.sleep(0.1)
                try:
                    subprocess.check_output(["pgrep", "-x", target])
                except Exception:
                    terminated = True
                    break

            if not terminated:
                for pid in pids:
                    try:
                        os.kill(int(pid), 9)
                    except Exception:
                        pass

    try:
        await asyncio.create_subprocess_exec(
            "pkill", "-f", "AI ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        await asyncio.create_subprocess_exec(
            "pkill",
            "-f",
            "uvicorn",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.create_subprocess_exec(
            "sync", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    if shutil.which("notify-send"):
        try:
            await asyncio.create_subprocess_exec(
                "notify-send",
                "AI Engine",
                "All Engines & Windows Shutdown",
                "-i",
                "system-shutdown",
            )
        except Exception:
            pass


def launch_local_server(script_name):
    script_path = os.path.join(SERV_DIR, script_name)
    if not os.path.exists(script_path):
        return False
    try:
        subprocess.Popen(
            [script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


async def async_get_key():
    fd = sys.stdin.fileno()

    def _read():
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch_bytes = os.read(fd, 1)
            if not ch_bytes:
                return None
            ch = ch_bytes.decode("utf-8", errors="ignore")
            if ch == "\x1b":
                rlist, _, _ = select.select([fd], [], [], 0.05)
                if rlist:
                    seq_bytes = os.read(fd, 2)
                    seq = seq_bytes.decode("utf-8", errors="ignore")
                    if seq in ("[A", "OA"):
                        return "up"
                    elif seq in ("[B", "OB"):
                        return "down"
                    elif seq in ("[C", "OC"):
                        return "right"
                    elif seq in ("[D", "OD"):
                        return "left"
                return "esc"
            elif ch in ("\r", "\n"):
                return "enter"
            elif ch.lower() == "q":
                return "q"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return await asyncio.to_thread(_read)


def draw_menu(selected, active_model, message=""):
    # Clear screen and move cursor to top-left
    sys.stdout.write("\x1b[H\x1b[2J")
    amber, green, reset, bold, dim = (
        "\033[38;2;230;120;60m",
        "\033[1;32m",
        "\033[0m",
        "\033[1m",
        "\033[90m",
    )

    sys.stdout.write(
        f"\r\n   {bold}  LOCAL-AI OFFLINE WORKSPACE{reset}\r\n   {dim}────────────────────────────────────────────────────────────{reset}\r\n\r\n"
    )

    for i, model in enumerate(LOCAL_MODELS):
        status = f" {green}(active){reset}" if model["file"] == active_model else ""
        opt_text = f"Run {model['name']}{status}\r\n       {dim}Start backend container for {model['file']}{reset}"
        prefix = f"   {amber}❯{reset}  {bold}" if i == selected else "      "
        sys.stdout.write(f"{prefix}{opt_text}{reset}\r\n\r\n")

    stop_idx, exit_idx = len(LOCAL_MODELS), len(LOCAL_MODELS) + 1

    sys.stdout.write(
        f"{'   ' + amber + '❯' + reset + '  ' + bold if selected == stop_idx else '      '}🚫  Unload All Local Models {dim}(Free System RAM){reset}\r\n\r\n"
    )
    sys.stdout.write(
        f"{'   ' + amber + '❯' + reset + '  ' + bold if selected == exit_idx else '      '}✕   Close Settings{reset}\r\n"
    )

    sys.stdout.write(
        f"\r\n   {dim}────────────────────────────────────────────────────────────{reset}\r\n"
    )
    sys.stdout.write(
        f"   {message or f'{dim}Use ▲/▼ Arrows to choose local server, Enter to initialize.{reset}'}\r\n"
    )
    sys.stdout.flush()


async def async_main():
    selected = 0
    total_options = len(LOCAL_MODELS) + 2
    message = ""

    if not os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "w") as f:
                f.write("balanced")
        except Exception:
            pass

    try:
        while True:
            active_model = get_current_running_model()
            draw_menu(selected, active_model, message)
            message = ""
            key = await async_get_key()

            if key == "up":
                selected = (selected - 1) % total_options
            elif key == "down":
                selected = (selected + 1) % total_options
            elif key == "enter":
                if selected < len(LOCAL_MODELS):
                    target_model = LOCAL_MODELS[selected]

                    if target_model["file"] == active_model:
                        message = f"\033[1;33mℹ {target_model['file']} is already active and running.\033[0m"
                        continue

                    message = "\033[1;33m↺ Releasing current server and flushing RAM pages...\033[0m"
                    draw_menu(selected, active_model, message)

                    await async_stop_all_engines()
                    await async_set_cpu_chill()

                    if launch_local_server(target_model["script"]):
                        message = f"\033[1;32m✓ Initialized {target_model['name']} on Port 8080.\033[0m"
                    else:
                        message = f"\033[1;31m✗ Failed to execute {target_model['script']}.\033[0m"

                elif selected == len(LOCAL_MODELS):
                    message = "\033[1;33m↺ Shutting down active local engines...\033[0m"
                    draw_menu(selected, active_model, message)

                    await async_stop_all_engines()
                    await async_set_cpu_balanced()

                    message = "\033[1;32m✓ Engines stopped. Local RAM cleared successfully.\033[0m"
                elif selected == len(LOCAL_MODELS) + 1:
                    break
            elif key == "q":
                break
    finally:
        # Reset terminal to clean state upon exiting
        os.system("stty sane")
        sys.stdout.write("\x1b[H\x1b[2J")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(async_main())
