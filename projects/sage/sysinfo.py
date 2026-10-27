#!/usr/bin/env python3
"""CLI tool that prints RAM and CPU usage."""

import argparse
import os
import subprocess
import sys

try:
    import psutil
except ImportError:
    psutil = None


def get_cpu_usage():
    """Return CPU usage percentage."""
    if psutil is not None:
        return psutil.cpu_percent(interval=1)
    # Fallback: parse load average from uptime
    try:
        with open("/proc/loadavg") as f:
            load_avg = float(f.read().split()[0])
        ncpu = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else 1
        return round(load_avg / ncpu * 100, 1)
    except Exception:
        return "n/a"


def get_ram_usage():
    """Return RAM usage as a string like '4.2 GB used of 16 GB'."""
    if psutil is not None:
        mem = psutil.virtual_memory()
        used = mem.total - mem.available
        return f"{used / 1e9:.1f} GB used of {mem.total / 1e9:.1f} GB ({mem.percent}%)"
    # Fallback: read /proc/meminfo
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, value = line.partition(":")
                meminfo[key.strip()] = int(value.split()[0]) * 1024
        total = meminfo["MemTotal"]
        free = meminfo["MemFree"] + meminfo["Buffers"] + meminfo["Cached"]
        used = total - free
        return f"{used / 1e9:.1f} GB used of {total / 1e9:.1f} GB"
    except Exception:
        return "n/a"


def main():
    parser = argparse.ArgumentParser(description="Print RAM and CPU usage.")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    cpu = get_cpu_usage()
    ram = get_ram_usage()

    if args.json:
        import json
        print(json.dumps({"cpu_percent": cpu, "ram": ram}, indent=2))
    else:
        print(f"CPU usage: {cpu}%")
        print(f"RAM usage: {ram}")


if __name__ == "__main__":
    main()
