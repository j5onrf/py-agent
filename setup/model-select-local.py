#!/usr/bin/env python3
# model-select-local.py - Hardened Local Offline Model Selector with Auto-CPU Control

import asyncio
import atexit
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import time
import tty

MODELS_DIR = "/home/user/models"
SERV_DIR = "/home/user/models/serv"
STATE_FILE = "/tmp/cpu_mode_state"

LOCAL_MODELS = [
    {
        "name": "MiniCPM5-2B (DSpark Off)",
        "alias": "MiniCPM5-2B-DSpark",
        "file": "MiniCPM5-2B-Q4_K_M.gguf",
        "script": "Mini2Bs.sh",
    },
    {
        "name": "Qwen 3.5 2B (unsloth)",
        "alias": "Qwen3.5-2B",
        "file": "Qwen3.5-2B.gguf",
        "script": "q2bu.sh",
    },
    {
        "name": "Tini-Cybersec-8B-A1B (MoE)",
        "alias": "Tini-Cybersec-8B-A1B",
        "file": "iselabvn_Tini-Cybersec-8B-A1B-Q5_K_M.gguf",
        "script": "tini.sh",
    },
    {
        "name": "LFM2.5-8B-A1B-APEX-I-Compact",
        "alias": "LFM2.5-8B-A1B",
        "file": "LFM2.5-8B-A1B.gguf",
        "script": "lfm2.sh",
    },
    {
        "name": "Ling-3.0-tiny-abliterated-APEX-I-Compact",
        "alias": "Ling-3.0-tiny",
        "file": "Ling-3.0-tiny-abliterated-APEX-I-Compact.gguf",
        "script": "Ltiny.sh",
    },
    {
        "name": "Nex-N2.5-mini-APEX-I-Compact (16.5gb)",
        "alias": "Nex-N2.5-mini",
        "file": "Nex-N2.5-mini-APEX-I-Compact.gguf",
        "script": "nex-n2.5.sh",
    },
    {
        "name": "Ornith-1.5-35B-A3B-APEX-I-Compact (16.5gb)",
        "alias": "Ornith-1.5-35B-A3B",
        "file": "Ornith-1.5-35B-A3B-APEX-I-Compact.gguf",
        "script": "ornith.sh",
    },
    {
        "name": "KAT-Coder-V2.5-Dev-APEX-I-Compact (16.5gb)",
        "alias": "KAT-Coder-V2.5-Dev",
        "file": "KAT-Coder-V2.5-Dev-APEX-I-Compact.gguf",
        "script": "kat.sh",
    },
    {
        "name": "Occamy-1.0-APEX-I-MiniPlus-V2.1 (14.7gb)",
        "alias": "Occamy-1.0",
        "file": "Occamy-1.0.APEX-I-MiniPlus-V2.1.gguf",
        "script": "occamy.sh",
    },
    {
        "name": "Qwen3.8-35B-A3B-Distill-MTP-APEX-I-MiniPlus-V2.1 (17.2gb)",
        "alias": "Qwen3.8-35B-Distill",
        "file": "Qwen3.8-35B-A3B-Distill-MTP-APEX-I-MiniPlus-V2.1.gguf",
        "script": "qwen38d.sh",
    },
]


def cleanup_terminal():
    sys.stdout.write("\x1b[?25h\x1b[?1049l")
    sys.stdout.flush()
    os.system("stty sane 2>/dev/null")


atexit.register(cleanup_terminal)


# --- HARDENED PROCESS DETECTION ---
def get_running_instances() -> list[dict]:
    instances = []
    if os.path.exists("/proc"):
        try:
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                pid = int(entry)
                cmdline_path = f"/proc/{pid}/cmdline"
                try:
                    with open(cmdline_path, "rb") as f:
                        raw = f.read()
                    if not raw:
                        continue
                    args = [a.decode("utf-8", errors="ignore") for a in raw.split(b"\x00") if a]
                    if not any("llama-server" in os.path.basename(a) for a in args):
                        continue

                    model_file = None
                    alias = None
                    all_ggufs = []

                    i = 0
                    while i < len(args):
                        arg = args[i]
                        if arg in ("-m", "--model") and i + 1 < len(args):
                            model_file = os.path.basename(args[i + 1].strip("\"'"))
                            i += 2
                            continue
                        elif arg in ("-a", "--alias") and i + 1 < len(args):
                            alias = args[i + 1].strip("\"'")
                            i += 2
                            continue
                        if arg.startswith("--alias="):
                            alias = arg.split("=", 1)[1].strip("\"'")
                        elif arg.startswith(("-m=", "--model=")):
                            model_file = os.path.basename(arg.split("=", 1)[1].strip("\"'"))
                        if ".gguf" in arg.lower():
                            clean_gguf = os.path.basename(arg.strip("\"'"))
                            if clean_gguf not in all_ggufs:
                                all_ggufs.append(clean_gguf)
                        i += 1

                    if model_file and model_file not in all_ggufs:
                        all_ggufs.append(model_file)

                    instances.append({
                        "pid": pid,
                        "model_file": model_file,
                        "alias": alias,
                        "all_ggufs": all_ggufs,
                        "args": args,
                    })
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
            if instances:
                return instances
        except Exception:
            pass

    try:
        output = subprocess.check_output(["pgrep", "-af", "llama-server"], stderr=subprocess.DEVNULL).decode()
        for line in output.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            alias_m = re.search(r"--alias[=\s]+([^\s]+)", line)
            model_m = re.search(r"(?:-m|--model)[=\s]+([^\s]+)", line)
            ggufs = [os.path.basename(m.group(0).strip("\"'")) for m in re.finditer(r"[^\s]+\.gguf", line, re.IGNORECASE)]

            instances.append({
                "pid": int(parts[0]) if parts[0].isdigit() else 0,
                "model_file": os.path.basename(model_m.group(1).strip("\"'")) if model_m else None,
                "alias": alias_m.group(1).strip("\"'") if alias_m else None,
                "all_ggufs": ggufs,
                "args": parts,
            })
    except Exception:
        pass

    return instances


def is_model_active(model_def: dict, instances: list[dict]) -> bool:
    if not instances:
        return False

    target_file = model_def.get("file", "").strip()
    target_alias = model_def.get("alias", "").strip()

    for inst in instances:
        if target_file and target_file in inst.get("all_ggufs", []):
            return True
        running_alias = (inst.get("alias") or "").strip()
        if target_alias and running_alias:
            if target_alias.lower() == running_alias.lower():
                return True
            if target_alias.replace("es", "").lower() == running_alias.replace("es", "").lower():
                return True
        for arg in inst.get("args", []):
            if target_file and target_file in arg:
                return True

    return False


async def async_set_cpu_chill():
    try:
        await asyncio.create_subprocess_exec(
            "sudo", "-n", "cpupower", "frequency-set", "-g", "powersave", "--max", "3.0GHz",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with open(STATE_FILE, "w") as f:
            f.write("chill")
        if shutil.which("notify-send"):
            await asyncio.create_subprocess_exec(
                "notify-send", "CPU Mode", "LOCAL-AI CHILL (3.0 GHz) - Active",
                "-u", "low", "-t", "1500", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


async def async_set_cpu_balanced():
    try:
        await asyncio.create_subprocess_exec(
            "sudo", "-n", "cpupower", "frequency-set", "-g", "powersave", "--max", "5.2GHz",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with open(STATE_FILE, "w") as f:
            f.write("balanced")
        if shutil.which("notify-send"):
            await asyncio.create_subprocess_exec(
                "notify-send", "CPU Mode", "BALANCED (Dynamic) - Restored",
                "-u", "normal", "-t", "1500", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


async def async_stop_all_engines():
    targets = ["llama-server", "llama-cli"]
    for target in targets:
        try:
            pids = subprocess.check_output(["pgrep", "-x", target], stderr=subprocess.DEVNULL).decode().split()
        except Exception:
            pids = []

        if pids:
            for pid in pids:
                try:
                    os.kill(int(pid), 15)
                except Exception:
                    pass

            for _ in range(20):
                await asyncio.sleep(0.1)
                try:
                    subprocess.check_output(["pgrep", "-x", target], stderr=subprocess.DEVNULL)
                except Exception:
                    break
            else:
                for pid in pids:
                    try:
                        os.kill(int(pid), 9)
                    except Exception:
                        pass

    try:
        await asyncio.create_subprocess_exec("pkill", "-f", "AI ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.create_subprocess_exec("pkill", "-f", "uvicorn", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.create_subprocess_exec("sync", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    if shutil.which("notify-send"):
        try:
            await asyncio.create_subprocess_exec(
                "notify-send", "AI Engine", "All Engines Stopped & Memory Flushed",
                "-i", "system-shutdown", "-t", "1500", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def launch_local_server(script_name: str) -> bool:
    script_path = os.path.join(SERV_DIR, script_name)
    if not os.path.isfile(script_path):
        return False

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


async def async_get_key_with_timeout(timeout: float = 0.5) -> str | None:
    fd = sys.stdin.fileno()

    def _read_with_select():
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            rlist, _, _ = select.select([fd], [], [], timeout)
            if not rlist:
                return None

            ch_bytes = os.read(fd, 1)
            if not ch_bytes:
                return None
            ch = ch_bytes.decode("utf-8", errors="ignore")

            if ch == "\x1b":
                rlist_seq, _, _ = select.select([fd], [], [], 0.05)
                if rlist_seq:
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

    return await asyncio.to_thread(_read_with_select)


def draw_menu(selected: int, running_instances: list[dict], message: str = ""):
    sys.stdout.write("\x1b[H")
    amber = "\033[38;2;230;120;60m"
    green = "\033[1;32m"
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[90m"

    term_cols = shutil.get_terminal_size((80, 24)).columns
    box_width = min(max(term_cols - 6, 60), 88)

    sys.stdout.write(
        f"\r\x1b[K\n   {bold}⚡ LOCAL-AI OFFLINE WORKSPACE{reset}\n   {dim}{'─' * box_width}{reset}\n"
    )

    for i, model in enumerate(LOCAL_MODELS):
        is_active = is_model_active(model, running_instances)
        prefix = f"   {amber}❯{reset}  {bold}" if i == selected else "      "
        name_text = model["name"]
        status_tag = f"{green}{bold}[● LOADED]{reset}" if is_active else ""
        status_len = 10 if is_active else 0

        visible_left = 6 + len(name_text)
        pad_len = max(2, box_width - visible_left - status_len)

        sys.stdout.write(f"\r\x1b[K{prefix}{name_text}{reset}{' ' * pad_len}{status_tag}\n")

    sys.stdout.write(f"\r\x1b[K\n")
    stop_idx = len(LOCAL_MODELS)
    exit_idx = len(LOCAL_MODELS) + 1

    sys.stdout.write(
        f"\r\x1b[K{'   ' + amber + '❯' + reset + '  ' + bold if selected == stop_idx else '      '}🚫  Unload All Models {dim}(Free RAM){reset}\n"
    )
    sys.stdout.write(
        f"\r\x1b[K{'   ' + amber + '❯' + reset + '  ' + bold if selected == exit_idx else '      '}✕   Close Settings{reset}\n"
    )

    # Active model file path banner
    selected_file = LOCAL_MODELS[selected]["file"] if selected < len(LOCAL_MODELS) else "System memory control"
    sys.stdout.write(f"\r\x1b[K   {dim}{'─' * box_width}{reset}\n")
    sys.stdout.write(f"\r\x1b[K   {dim}Target:{reset} {selected_file[:box_width-12]}\n")
    sys.stdout.write(
        f"\r\x1b[K   {message or f'{dim}▲/▼: Navigate | Enter: Start Server | Esc/q: Exit{reset}'}\n"
    )
    sys.stdout.write("\x1b[J")
    sys.stdout.flush()


async def async_main():
    selected = 0
    total_options = len(LOCAL_MODELS) + 2
    message = ""
    last_state_hash = None

    # Switch to clean alternate screen buffer (zero scrollback pollution)
    sys.stdout.write("\x1b[?1049h\x1b[?25l")
    sys.stdout.flush()

    if not os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "w") as f:
                f.write("balanced")
        except Exception:
            pass

    try:
        while True:
            running_instances = get_running_instances()
            current_hash = (selected, message, [(m["alias"], is_model_active(m, running_instances)) for m in LOCAL_MODELS])

            if current_hash != last_state_hash:
                draw_menu(selected, running_instances, message)
                last_state_hash = current_hash
                message = ""

            key = await async_get_key_with_timeout(timeout=0.5)

            if key is None:
                continue
            elif key == "up":
                selected = (selected - 1) % total_options
            elif key == "down":
                selected = (selected + 1) % total_options
            elif key == "enter":
                if selected < len(LOCAL_MODELS):
                    target_model = LOCAL_MODELS[selected]

                    if is_model_active(target_model, running_instances):
                        message = f"\033[1;33mℹ {target_model['name']} is already LOADED and active.\033[0m"
                        last_state_hash = None
                        continue

                    message = f"\033[1;33m↺ Releasing current server and flushing RAM pages...\033[0m"
                    draw_menu(selected, running_instances, message)

                    await async_stop_all_engines()
                    await async_set_cpu_chill()

                    if launch_local_server(target_model["script"]):
                        verified = False
                        for _ in range(25):
                            await asyncio.sleep(0.2)
                            fresh_instances = get_running_instances()
                            if is_model_active(target_model, fresh_instances):
                                verified = True
                                running_instances = fresh_instances
                                break

                        if verified:
                            message = f"\033[1;32m✓ Initialized {target_model['name']} on Port 8080.\033[0m"
                        else:
                            message = f"\033[1;33m⚠ Script executed, verifying backend startup in background...\033[0m"
                    else:
                        message = f"\033[1;31m✗ Failed to execute {target_model['script']} (Check {SERV_DIR}).\033[0m"
                    last_state_hash = None

                elif selected == len(LOCAL_MODELS):
                    message = "\033[1;33m↺ Shutting down active local engines...\033[0m"
                    draw_menu(selected, running_instances, message)

                    await async_stop_all_engines()
                    await async_set_cpu_balanced()

                    message = "\033[1;32m✓ Engines stopped. Local RAM cleared successfully.\033[0m"
                    last_state_hash = None

                elif selected == len(LOCAL_MODELS) + 1:
                    break
            elif key in ("q", "esc"):
                break
    finally:
        cleanup_terminal()


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        cleanup_terminal()
        sys.exit(0)
