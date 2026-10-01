#!/usr/bin/env python3
# model-select-local.py - Hardened Local Offline Model Selector with Auto-CPU Control & RAM Monitor

import asyncio
import atexit
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import tty

MODELS_DIR = "/home/j5/models"
SERV_DIR = "/home/j5/models/serv"

STATE_DIR = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "model-select",
)
STATE_FILE = os.path.join(STATE_DIR, "cpu_mode")

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
        "script": "nexn25.sh",
    },
    {
        "name": "Ornith-1.5-35B-A3B-APEX-I-Compact (16.5gb)",
        "alias": "Ornith-1.5-35B-A3B",
        "file": "Ornith-1.5-35B-A3B-APEX-I-Compact.gguf",
        "script": "ornith.sh",
    },
    {
        "name": "Tiel-Coder-35B-A3B-APEX-I-MiniPlus-V2.1 (15.2gb)",
        "alias": "Tiel-Coder-35B-A3B",
        "file": "Tiel-Coder-35B-A3B.APEX-I-MiniPlus-V2.1.gguf",
        "script": "tielcoder.sh",
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
        "file": "Qwen3.8-35B-A3B-Distill.APEX-I-MiniPlus-V2.1.gguf",
        "script": "qwen38d.sh",
    },
]

ORIGINAL_TERMIOS = None


def cleanup_terminal():
    sys.stdout.write("\x1b[?25h\x1b[?1049l")
    sys.stdout.flush()
    if ORIGINAL_TERMIOS is not None and sys.stdin.isatty():
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, ORIGINAL_TERMIOS)
        except Exception:
            pass
    try:
        os.system("stty sane 2>/dev/null")
    except Exception:
        pass


atexit.register(cleanup_terminal)


def write_cpu_state(state: str):
    try:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        fd = os.open(
            STATE_FILE,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "w") as f:
            f.write(state)
    except Exception:
        pass


def get_memory_info() -> dict:
    try:
        mem = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].strip().split()[0])

        total_kb = mem.get("MemTotal", 0)
        avail_kb = mem.get("MemAvailable", 0)
        used_kb = max(0, total_kb - avail_kb)

        swap_total_kb = mem.get("SwapTotal", 0)
        swap_free_kb = mem.get("SwapFree", 0)
        swap_used_kb = max(0, swap_total_kb - swap_free_kb)

        total_gb = total_kb / (1024 * 1024)
        used_gb = used_kb / (1024 * 1024)
        avail_gb = avail_kb / (1024 * 1024)
        pct = (used_kb / total_kb * 100) if total_kb > 0 else 0

        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "avail_gb": avail_gb,
            "pct": pct,
            "swap_used_gb": swap_used_kb / (1024 * 1024),
            "swap_total_gb": swap_total_kb / (1024 * 1024),
        }
    except Exception:
        return {}


def format_memory_bar(mem: dict, bar_width: int = 14) -> str:
    if not mem:
        return ""

    pct = mem["pct"]
    used = mem["used_gb"]
    total = mem["total_gb"]
    avail = mem["avail_gb"]

    if pct < 70:
        color = "\033[1;32m"
    elif pct < 85:
        color = "\033[38;2;230;120;60m"
    else:
        color = "\033[1;31m"

    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[90m"

    filled = int((pct / 100) * bar_width)
    filled = max(0, min(bar_width, filled))
    bar = f"{color}{'■' * filled}{dim}{'·' * (bar_width - filled)}{reset}"

    msg = (
        f"{dim}RAM:{reset} [{bar}] {bold}{color}{used:.1f}{reset}/{total:.1f} GB "
        f"({color}{pct:.0f}%{reset})  {dim}Free:{reset} {bold}{avail:.1f} GB{reset}"
    )

    if mem.get("swap_used_gb", 0) > 0.1:
        msg += f"  {dim}| Swap:{reset} \033[1;33m{mem['swap_used_gb']:.1f} GB{reset}"

    return msg


def is_target_pid(pid: int, expected_comm: str) -> bool:
    try:
        comm_path = f"/proc/{pid}/comm"
        if os.path.exists(comm_path):
            with open(comm_path, "r") as f:
                return f.read().strip() == expected_comm
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
    return False


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
        current_uid = str(os.getuid())
        output = subprocess.check_output(
            ["pgrep", "-u", current_uid, "-af", "llama-server"],
            stderr=subprocess.DEVNULL,
        ).decode()
        for line in output.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            alias_m = re.search(r"--alias[=\s]+([^\s]+)", line)
            model_m = re.search(r"(?:-m|--model)[=\s]+([^\s]+)", line)
            ggufs = [
                os.path.basename(m.group(0).strip("\"'"))
                for m in re.finditer(r"[^\s]+\.gguf", line, re.IGNORECASE)
            ]

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
        if target_alias and running_alias and target_alias.lower() == running_alias.lower():
            return True
        for arg in inst.get("args", []):
            if target_file and target_file in arg:
                return True

    return False


async def async_set_cpu_mode(governor: str, max_freq: str, mode_name: str, notify_title: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-n", "cpupower", "frequency-set", "-g", governor, "--max", max_freq,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        rc = await proc.wait()
        if rc == 0:
            write_cpu_state(mode_name)
            if shutil.which("notify-send"):
                proc_n = await asyncio.create_subprocess_exec(
                    "notify-send", "CPU Mode", notify_title,
                    "-u", "low", "-t", "1500", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                await proc_n.wait()
            return True
        return False
    except Exception:
        return False


async def async_set_cpu_chill() -> bool:
    return await async_set_cpu_mode("powersave", "3.0GHz", "chill", "LOCAL-AI CHILL (3.0 GHz) - Active")


async def async_set_cpu_balanced() -> bool:
    return await async_set_cpu_mode("powersave", "5.2GHz", "balanced", "BALANCED (Dynamic) - Restored")


async def async_stop_all_engines():
    current_uid = str(os.getuid())
    targets = ["llama-server", "llama-cli"]

    for target in targets:
        try:
            output = subprocess.check_output(
                ["pgrep", "-u", current_uid, "-x", target],
                stderr=subprocess.DEVNULL,
            ).decode()
            pids = [int(p) for p in output.split() if p.isdigit()]
        except Exception:
            pids = []

        if not pids:
            continue

        for pid in pids:
            if is_target_pid(pid, target):
                try:
                    os.kill(pid, 15)
                except ProcessLookupError:
                    pass

        for _ in range(20):
            await asyncio.sleep(0.1)
            alive = [p for p in pids if is_target_pid(p, target)]
            if not alive:
                break
        else:
            for pid in pids:
                if is_target_pid(pid, target):
                    try:
                        os.kill(pid, 9)
                    except ProcessLookupError:
                        pass

    try:
        proc_sync = await asyncio.create_subprocess_exec("sync", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await proc_sync.wait()
    except Exception:
        pass

    if shutil.which("notify-send"):
        try:
            proc_n = await asyncio.create_subprocess_exec(
                "notify-send", "AI Engine", "All Engines Stopped & Memory Flushed",
                "-i", "system-shutdown", "-t", "1500", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            await proc_n.wait()
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

    def _read():
        try:
            rlist, _, _ = select.select([fd], [], [], timeout)
            if not rlist:
                return None
            raw = os.read(fd, 32)
            if not raw:
                return None
            seq = raw.decode("utf-8", errors="ignore")
        except Exception:
            return None

        if seq in ("\x1b[A", "\x1bOA") or seq.startswith("\x1b[A"):
            return "up"
        elif seq in ("\x1b[B", "\x1bOB") or seq.startswith("\x1b[B"):
            return "down"
        elif seq in ("\x1b[C", "\x1bOC") or seq.startswith("\x1b[C"):
            return "right"
        elif seq in ("\x1b[D", "\x1bOD") or seq.startswith("\x1b[D"):
            return "left"
        elif seq == "\x1b":
            return "esc"
        elif seq in ("\r", "\n"):
            return "enter"
        elif seq.lower() == "q":
            return "q"
        return seq

    return await asyncio.to_thread(_read)


def draw_menu(
    selected: int,
    running_instances: list[dict],
    active_statuses: dict[str, bool],
    message: str = "",
    mem_info: dict = None,
):
    sys.stdout.write("\x1b[H")
    amber = "\033[38;2;230;120;60m"
    green = "\033[1;32m"
    red = "\033[1;31m"
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[90m"

    if mem_info is None:
        mem_info = get_memory_info()

    term_cols = shutil.get_terminal_size((80, 24)).columns
    box_width = min(max(term_cols - 6, 60), 88)

    sys.stdout.write(f"\r\x1b[K\n   {bold}⚡ LOCAL-AI OFFLINE WORKSPACE{reset}\n")
    sys.stdout.write(f"\r\x1b[K   {format_memory_bar(mem_info)}\n")
    sys.stdout.write(f"\r\x1b[K   {dim}{'─' * box_width}{reset}\n")

    for i, model in enumerate(LOCAL_MODELS):
        is_active = active_statuses.get(model["alias"], False)
        exists_on_disk = model.get("file_exists", True)

        prefix = f"   {amber}❯{reset}  {bold}" if i == selected else "      "
        name_text = model["name"]

        if is_active:
            status_tag = f"{green}{bold}[● LOADED]{reset}"
            status_len = 10
        elif not exists_on_disk:
            status_tag = f"{red}{dim}[NOT FOUND]{reset}"
            status_len = 11
        else:
            status_tag = ""
            status_len = 0

        visible_left = 6 + len(name_text)
        pad_len = max(2, box_width - visible_left - status_len)

        sys.stdout.write(f"\r\x1b[K{prefix}{name_text}{reset}{' ' * pad_len}{status_tag}\n")

    sys.stdout.write("\r\x1b[K\n")
    stop_idx = len(LOCAL_MODELS)
    exit_idx = len(LOCAL_MODELS) + 1

    sys.stdout.write(
        f"\r\x1b[K{'   ' + amber + '❯' + reset + '  ' + bold if selected == stop_idx else '      '}🚫  Unload All Models {dim}(Free RAM){reset}\n"
    )
    sys.stdout.write(
        f"\r\x1b[K{'   ' + amber + '❯' + reset + '  ' + bold if selected == exit_idx else '      '}✕   Close Settings{reset}\n"
    )

    selected_file = LOCAL_MODELS[selected]["file"] if selected < len(LOCAL_MODELS) else "System memory control"
    sys.stdout.write(f"\r\x1b[K   {dim}{'─' * box_width}{reset}\n")
    sys.stdout.write(f"\r\x1b[K   {dim}Target:{reset} {selected_file[:box_width-12]}\n")
    sys.stdout.write(
        f"\r\x1b[K   {message or f'{dim}▲/▼: Navigate | Enter: Start Server | Esc/q: Exit{reset}'}\n"
    )
    sys.stdout.write("\x1b[J")
    sys.stdout.flush()


async def async_main():
    global ORIGINAL_TERMIOS

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.stderr.write("Error: model-select-local requires an interactive TTY.\n")
        sys.exit(1)

    ORIGINAL_TERMIOS = termios.tcgetattr(sys.stdin.fileno())
    tty.setcbreak(sys.stdin.fileno())

    for m in LOCAL_MODELS:
        m["file_exists"] = os.path.isfile(os.path.join(MODELS_DIR, m["file"]))

    selected = 0
    total_options = len(LOCAL_MODELS) + 2
    message = ""
    last_state_hash = None

    sys.stdout.write("\x1b[?1049h\x1b[?25l")
    sys.stdout.flush()

    write_cpu_state("balanced")

    try:
        while True:
            running_instances, mem_info = await asyncio.gather(
                asyncio.to_thread(get_running_instances),
                asyncio.to_thread(get_memory_info),
            )

            active_statuses = {m["alias"]: is_model_active(m, running_instances) for m in LOCAL_MODELS}
            mem_snapshot = round(mem_info.get("used_gb", 0), 1)

            current_hash = (
                selected,
                message,
                mem_snapshot,
                tuple(active_statuses.items()),
            )

            if current_hash != last_state_hash:
                draw_menu(selected, running_instances, active_statuses, message, mem_info)
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

                    message = "\033[1;33m↺ Releasing current server and flushing RAM pages...\033[0m"
                    draw_menu(selected, running_instances, active_statuses, message, mem_info)

                    await async_stop_all_engines()
                    chill_ok = await async_set_cpu_chill()

                    if launch_local_server(target_model["script"]):
                        verified = False
                        for _ in range(25):
                            await asyncio.sleep(0.2)
                            fresh_instances = await asyncio.to_thread(get_running_instances)
                            if is_model_active(target_model, fresh_instances):
                                verified = True
                                running_instances = fresh_instances
                                break

                        throttle_note = "" if chill_ok else " (CPU throttle skipped: sudo required)"
                        if verified:
                            message = f"\033[1;32m✓ Initialized {target_model['name']} on Port 8080.{throttle_note}\033[0m"
                        else:
                            message = f"\033[1;33m⚠ Script executed, verifying backend startup in background...{throttle_note}\033[0m"
                    else:
                        message = f"\033[1;31m✗ Failed to execute {target_model['script']} (Check {SERV_DIR}).\033[0m"
                    last_state_hash = None

                elif selected == len(LOCAL_MODELS):
                    message = "\033[1;33m↺ Shutting down active local engines...\033[0m"
                    draw_menu(selected, running_instances, active_statuses, message, mem_info)

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
