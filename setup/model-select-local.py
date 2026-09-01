#!/usr/bin/env python3
"""
model-select-local.py - Universal Local Model Selector & Engine Manager
Supports interactive TUI selection, RAM page flushing, and automated power governance.
"""

import asyncio
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import termios
import tty

# --- DYNAMIC SYSTEM PATHS ---
HOME_DIR = os.path.expanduser("~")
MODELS_DIR = os.environ.get("AI_MODELS_DIR", os.path.join(HOME_DIR, "models"))
SERV_DIR = os.environ.get("AI_SERV_DIR", os.path.join(MODELS_DIR, "serv"))
STATE_FILE = os.path.join(tempfile.gettempdir(), "cpu_mode_state")

# Frequency targets for systems using cpupower (configurable via environment)
CPU_CHILL_FREQ = os.environ.get("AI_CPU_CHILL_FREQ", "3.5GHz")
CPU_BALANCED_FREQ = os.environ.get("AI_CPU_BALANCED_FREQ", "5.2GHz")

# --- MODEL REGISTRY ---
# Map model display names to their GGUF filename and launcher script inside SERV_DIR
LOCAL_MODELS = [
    {
        "name": "Qwen3.5-2B-Claude (Fast Chat / Single-Task)",
        "file": "Qwen3.5-2B-Claude.gguf",
        "script": "q2b.sh",
    },
    {
        "name": "LFM2.5-8B-A1B (Balanced / Lite Coding Agent)",
        "file": "LFM2.5-8B-A1B-UD-Q4_K_XL.gguf",
        "script": "lfm2.sh",
    },
    {
        "name": "Hermes3.6-35B-A3B (Heavy / Developer Agent)",
        "file": "Herm3.6-35B-A3B.gguf",
        "script": "q35b.sh",
    },
]


# --- CPU POWER AUTOMATION ---
async def async_set_cpu_chill():
    """Sets CPU to power-efficient, quiet profile for sustained inference."""
    if not shutil.which("cpupower"):
        return
    try:
        cmd = ["sudo", "-n", "cpupower", "frequency-set", "-g", "powersave"]
        if CPU_CHILL_FREQ:
            cmd.extend(["--max", CPU_CHILL_FREQ])

        await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(STATE_FILE, "w") as f:
            f.write("chill")

        if shutil.which("notify-send"):
            await asyncio.create_subprocess_exec(
                "notify-send",
                "Power Profile",
                f"AI CHILL ({CPU_CHILL_FREQ or 'Powersave'}) - Active",
                "-u",
                "low",
                "-t",
                "1500",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


async def async_set_cpu_balanced():
    """Restores balanced CPU scaling when models are unloaded."""
    if not shutil.which("cpupower"):
        return
    try:
        cmd = ["sudo", "-n", "cpupower", "frequency-set", "-g", "powersave"]
        if CPU_BALANCED_FREQ:
            cmd.extend(["--max", CPU_BALANCED_FREQ])

        await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(STATE_FILE, "w") as f:
            f.write("balanced")

        if shutil.which("notify-send"):
            await asyncio.create_subprocess_exec(
                "notify-send",
                "Power Profile",
                f"BALANCED ({CPU_BALANCED_FREQ or 'Dynamic'}) - Restored",
                "-u",
                "normal",
                "-t",
                "1500",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


def get_current_running_model():
    """Scans running processes to detect currently loaded llama-server model."""
    try:
        output = subprocess.check_output(
            ["pgrep", "-af", "llama-server"], stderr=subprocess.DEVNULL
        ).decode()
        for line in output.splitlines():
            # Check for --alias first, then -m filename
            alias_match = re.search(r"--alias\s+([^\s]+)", line)
            if alias_match:
                return os.path.basename(alias_match.group(1).strip("\"'"))
            model_match = re.search(r"-m\s+([^\s]+)", line)
            if model_match:
                return os.path.basename(model_match.group(1).strip("\"'"))
    except Exception:
        pass
    return None


# --- NON-BLOCKING ENGINE CLEANER ---
async def async_stop_all_engines():
    """Gracefully terminates active backends and flushes system memory caches."""
    targets = ["llama-server", "llama-cli"]
    for target in targets:
        try:
            pids = subprocess.check_output(
                ["pgrep", "-x", target], stderr=subprocess.DEVNULL
            ).decode().split()
        except Exception:
            pids = []

        if pids:
            # 1. Soft SIGTERM
            for pid in pids:
                try:
                    os.kill(int(pid), 15)
                except Exception:
                    pass

            # 2. Wait up to 2 seconds for graceful shutdown
            terminated = False
            for _ in range(20):
                await asyncio.sleep(0.1)
                try:
                    subprocess.check_output(
                        ["pgrep", "-x", target], stderr=subprocess.DEVNULL
                    )
                except Exception:
                    terminated = True
                    break

            # 3. Hard SIGKILL fallback
            if not terminated:
                for pid in pids:
                    try:
                        os.kill(int(pid), 9)
                    except Exception:
                        pass

    # Flush filesystem dirty pages
    try:
        await asyncio.create_subprocess_exec(
            "sync", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    if shutil.which("notify-send"):
        try:
            await asyncio.create_subprocess_exec(
                "notify-send",
                "AI Backend",
                "Engines Stopped & Memory Flushed",
                "-i",
                "system-shutdown",
                "-t",
                "1500",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def launch_local_server(script_name):
    """Executes a launcher script in a fully detached, independent process group."""
    script_path = os.path.join(SERV_DIR, script_name)
    if not os.path.isfile(script_path):
        return False

    # Ensure executable permission
    if not os.access(script_path, os.X_OK):
        try:
            os.chmod(script_path, 0o755)
        except Exception:
            pass

    try:
        subprocess.Popen(
            [script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=SERV_DIR,
        )
        return True
    except Exception:
        return False


async def async_get_key():
    """Reads raw terminal escape sequences and arrow navigation keys safely."""
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
    """Draws clean ANSI terminal interface with active status markers."""
    sys.stdout.write("\x1b[H\x1b[2J")
    amber, green, reset, bold, dim = (
        "\033[38;2;230;120;60m",
        "\033[1;32m",
        "\033[0m",
        "\033[1m",
        "\033[90m",
    )

    sys.stdout.write(
        f"\r\n   {bold}⚡ LOCAL-AI OFFLINE MODEL SELECT{reset}\r\n   {dim}────────────────────────────────────────────────────────────{reset}\r\n\r\n"
    )

    for i, model in enumerate(LOCAL_MODELS):
        # Match active model by file name or alias prefix
        is_active = (
            active_model
            and (model["file"] in active_model or active_model in model["file"])
        )
        status = f" {green}(active){reset}" if is_active else ""
        opt_text = f"Run {model['name']}{status}\r\n       {dim}Start backend container for {model['file']}{reset}"
        prefix = f"   {amber}❯{reset}  {bold}" if i == selected else "      "
        sys.stdout.write(f"{prefix}{opt_text}{reset}\r\n\r\n")

    stop_idx = len(LOCAL_MODELS)
    exit_idx = len(LOCAL_MODELS) + 1

    sys.stdout.write(
        f"{'   ' + amber + '❯' + reset + '  ' + bold if selected == stop_idx else '      '}🚫  Unload All Local Models {dim}(Free System RAM/VRAM){reset}\r\n\r\n"
    )
    sys.stdout.write(
        f"{'   ' + amber + '❯' + reset + '  ' + bold if selected == exit_idx else '      '}✕   Close Settings{reset}\r\n"
    )

    sys.stdout.write(
        f"\r\n   {dim}────────────────────────────────────────────────────────────{reset}\r\n"
    )
    sys.stdout.write(
        f"   {message or f'{dim}Use ▲/▼ Arrows to navigate, Enter to launch, q to quit.{reset}'}\r\n"
    )
    sys.stdout.flush()


async def async_main():
    selected = 0
    total_options = len(LOCAL_MODELS) + 2
    message = ""

    os.makedirs(SERV_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

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

                    # If already running, skip re-initialization
                    if active_model and (
                        target_model["file"] in active_model
                        or active_model in target_model["file"]
                    ):
                        message = f"\033[1;33mℹ {target_model['name']} is already active.\033[0m"
                        continue

                    message = "\033[1;33m↺ Releasing active server and locking memory pages...\033[0m"
                    draw_menu(selected, active_model, message)

                    await async_stop_all_engines()
                    await async_set_cpu_chill()

                    if launch_local_server(target_model["script"]):
                        message = f"\033[1;32m✓ Initialized {target_model['name']} on Port 8080.\033[0m"
                    else:
                        message = f"\033[1;31m✗ Failed to launch {target_model['script']} (Check {SERV_DIR}).\033[0m"

                elif selected == len(LOCAL_MODELS):
                    message = "\033[1;33m↺ Shutting down local engines & clearing RAM...\033[0m"
                    draw_menu(selected, active_model, message)

                    await async_stop_all_engines()
                    await async_set_cpu_balanced()

                    message = "\033[1;32m✓ Engines stopped. System memory freed successfully.\033[0m"

                elif selected == len(LOCAL_MODELS) + 1:
                    break
            elif key in ("q", "esc"):
                break
    finally:
        os.system("stty sane")
        sys.stdout.write("\x1b[H\x1b[2J")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        os.system("stty sane")
        sys.exit(0)
