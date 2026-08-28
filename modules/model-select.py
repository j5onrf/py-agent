#!/usr/bin/env python3
"""Fully Dynamic TUI Model Selector driven by OpenRouter & HuggingFace Router Rankings"""

import asyncio
import atexit
import json
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import tty
import urllib.request as urlreq

ENV_PATH = os.path.expanduser("~/.config/py-agent/.env")
CACHE_PATH = os.path.expanduser("~/.config/py-agent/.openrouter_cache_v2.json")
CUSTOM_SPACES_FILE = os.path.expanduser("~/.config/py-agent/custom_spaces.json")
HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"

ORIGINAL_TERMIOS = termios.tcgetattr(sys.stdin.fileno()) if sys.stdin.isatty() else None


def cleanup_terminal():
    if ORIGINAL_TERMIOS:
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, ORIGINAL_TERMIOS)
        except (termios.error, OSError):
            pass
    sys.stdout.write("\x1b[H\x1b[2J\033[?25h\033[0m")
    sys.stdout.flush()


atexit.register(cleanup_terminal)

# ── Color Palette ─────────────────────────────────────────────────────────────
AMBER, GREEN, RED, RESET, BOLD, DIM = (
    "\033[38;2;230;120;60m",
    "\033[1;32m",
    "\033[1;31m",
    "\033[0m",
    "\033[1m",
    "\033[90m",
)

DEFAULTS = {
    "gemini": ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.5-pro"],
    "openai": ["gpt-5.5", "gpt-5", "gpt-4.5", "o3", "o3-mini", "gpt-4o", "gpt-4o-mini"],
    "claude": ["claude-3-7-sonnet", "claude-opus-5", "claude-fable-5", "claude-sonnet-5", "claude-opus-4-8"],
    "grok": ["grok-4.5", "grok-4", "grok-3", "grok-2"],
    "free": ["openrouter/free", "nvidia/nemotron-3-ultra:free", "google/gemma-4-26b-a4b:free", "meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat:free"],
    "paid": ["deepseek/deepseek-v4-flash", "anthropic/claude-3.7-sonnet", "google/gemini-3.7-flash", "openai/gpt-5.5", "openai/gpt-4o-mini"],
    "spaces": {
        "Local llama-server / vLLM (Port 8080)": {"url": "http://127.0.0.1:8080/v1/chat/completions", "model": "local-model"},
        "Local Ollama (Port 11434)": {"url": "http://127.0.0.1:11434/v1/chat/completions", "model": "llama3.3"},
    },
}

PROVIDER_KEYS = ["CUSTOM_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]


# ── Storage & Env Helpers ─────────────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return default


def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass


def ensure_env_exists():
    if not os.path.exists(ENV_PATH):
        os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
        template = (
            "# Top-Down Priority (First Active Key is Used)\n\n"
            '# CUSTOM_API_KEY="not-needed"\n'
            'CUSTOM_URL="https://router.huggingface.co/v1/chat/completions"\n'
            'CUSTOM_MODEL="Qwen/Qwen3.8-27B"\n\n'
            '# GEMINI_API_KEY="AIzaSyYourGeminiKey"\n'
            'GEMINI_MODEL="gemini-3.7-flash"\n\n'
            '# OPENROUTER_API_KEY="sk-or-v1-YourKey"\n'
            'OPENROUTER_MODEL="openrouter/free"\n\n'
            '# OPENAI_API_KEY="your-key"\n'
            'OPENAI_MODEL="gpt-5.5"\n\n'
            '# CLAUDE_API_KEY="your-key"\n'
            'CLAUDE_MODEL="claude-fable-5"\n\n'
            '# XAI_API_KEY="your-key"\n'
            'XAI_MODEL="grok-4.6"\n\n'
            'AI_MAX_TOKENS="8192"\n'
        )
        try:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(template)
        except OSError:
            pass


def load_env_vars():
    ensure_env_exists()
    env = {}
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for l in f:
                    if m := re.match(r"^#?\s*([A-Z0-9_]+)\s*=\s*\"?([^\"]*)\"?$", l.strip()):
                        k, val = m.groups()
                        if not l.strip().startswith("#") or k not in env:
                            env[k] = val
        except OSError:
            pass
    return env


def get_active_key_set() -> set[str]:
    active = set()
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for l in f:
                    s = l.strip()
                    if s and not s.startswith("#") and "=" in s:
                        k, v = s.split("=", 1)
                        val = v.strip().strip('"').strip("'")
                        if val and not any(sub in val.lower() for sub in ("your", "here", "api-key")):
                            active.add(k.strip())
        except OSError:
            pass
    return active


def update_env_multiple(updates: dict[str, str]):
    if not os.path.exists(ENV_PATH):
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for k, v in updates.items():
            updated = False
            for i, l in enumerate(lines):
                if re.match(rf"^#?\s*{k}\s*=\s*.*$", l):
                    lines[i] = f'{"#" if l.strip().startswith("#") else ""}{k}="{v}"\n'
                    updated = True
                    break
            if not updated:
                lines.append(f'{k}="{v}"\n')
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        pass


def isolate_active_key(active_key_name: str):
    if not os.path.exists(ENV_PATH):
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, l in enumerate(lines):
            for k in PROVIDER_KEYS:
                if f"{k}=" in l or f"{k} =" in l:
                    should_comment = (k != active_key_name)
                    raw = l.strip().lstrip("#").strip()
                    lines[i] = f"{'#' if should_comment else ''}{raw}\n"
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        pass


def toggle_env_api_keys():
    if not os.path.exists(ENV_PATH):
        return False
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        is_commented = any(l.strip().startswith("#") for l in lines if any(k in l for k in PROVIDER_KEYS))
        lines = [f"{'#' if not is_commented else ''}{l.strip().lstrip('#').strip()}\n" if any(k in l for k in PROVIDER_KEYS) else l for l in lines]
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return is_commented
    except OSError:
        return False


# ── URL Extraction & Networking ───────────────────────────────────────────────
def parse_endpoint_url(raw_url: str) -> tuple[str, str, str]:
    url = raw_url.strip()
    if "huggingface.co/spaces/" in url:
        parts = url.split("huggingface.co/spaces/", 1)[1].strip("/").split("/")
        if len(parts) >= 2:
            author, space = parts[0], parts[1]
            if "qwen3.8-flash-next" in space.lower() or "qwen3-8-flash-next" in space.lower():
                return ("victor/Qwen3.8-Flash-Next (Free Space)", "https://pnywsahxhac1qjbo.us-east-2.aws.endpoints.huggingface.cloud/v1/chat/completions", "Qwen/Qwen3.8-Flash-Next")
            subdomain = f"{author}-{space}".lower().replace("_", "-").replace(".", "-")
            clean_m = space.replace("-free-endpoint", "").replace("-endpoint", "")
            return (f"{author}/{clean_m} (Space)", f"https://{subdomain}.hf.space/v1/chat/completions", clean_m)
    if "endpoints.huggingface.cloud" in url:
        t_url = url if url.endswith("/chat/completions") else f"{url.rstrip('/')}/v1/chat/completions"
        return ("Dedicated Cloud Endpoint", t_url, "default")
    if ".hf.space" in url:
        host = url.split("://")[-1].split("/")[0]
        base = host.replace(".hf.space", "")
        return (f"{base} (Space)", f"https://{host}/v1/chat/completions" if not url.endswith("/chat/completions") else url, base)
    t_url = url if url.endswith("/chat/completions") else f"{url.rstrip('/')}/v1/chat/completions"
    return (f"Custom ({url.split('://')[-1].split('/')[0]})", t_url, "default")


async def async_fetch_remote(api_key_or: str, api_key_hf: str, spaces: dict):
    def _fetch():
        free_c, paid_c, hf_res = [], [], list(spaces.keys())
        try:
            req = urlreq.Request("https://openrouter.ai/api/v1/models?sort=top-weekly", headers={"Authorization": f"Bearer {api_key_or}"} if api_key_or else {})
            with urlreq.urlopen(req, timeout=8) as res:
                if res.status == 200:
                    for it in json.loads(res.read().decode("utf-8")).get("data", []):
                        if m_id := it.get("id"):
                            p = it.get("pricing", {})
                            is_f = "free" in m_id.lower() or (p and float(p.get("prompt", 0)) == 0 and float(p.get("completion", 0)) == 0)
                            (free_c if is_f else paid_c).append(m_id)
        except Exception:
            pass
        try:
            req_hf = urlreq.Request("https://router.huggingface.co/v1/models", headers={"Authorization": f"Bearer {api_key_hf}"} if (api_key_hf and "your" not in api_key_hf.lower()) else {})
            with urlreq.urlopen(req_hf, timeout=8) as res:
                if res.status == 200:
                    for it in json.loads(res.read().decode("utf-8")).get("data", []):
                        if (m_id := it.get("id")) and m_id not in hf_res:
                            hf_res.append(m_id)
                            if len(hf_res) >= 25:
                                break
        except Exception:
            pass
        return free_c or DEFAULTS["free"], paid_c or DEFAULTS["paid"], hf_res

    return await asyncio.to_thread(_fetch)


# ── Interactive TUI Engine ────────────────────────────────────────────────────
async def async_get_key():
    fd = sys.stdin.fileno()

    def _read():
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            if not (b := os.read(fd, 1)):
                return None
            ch = b.decode("utf-8", errors="ignore")
            if ch == "\x1b" and select.select([fd], [], [], 0.05)[0]:
                return {"[A": "up", "OA": "up", "[B": "down", "OB": "down", "[C": "right", "OC": "right", "[D": "left", "OD": "left"}.get(os.read(fd, 2).decode("utf-8", errors="ignore"), "esc")
            return {"\x1b": "esc", "\r": "enter", "\n": "enter", "\x7f": "backspace", "\x08": "backspace"}.get(ch, ch.lower() if ch.lower() == "q" else ch)
        except Exception:
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return await asyncio.to_thread(_read)


def prompt_user_input(prompt_text: str) -> str:
    cleanup_terminal()
    try:
        return input(f"\n\033[1;36m{prompt_text}\033[0m: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    finally:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()


async def run_interactive_menu(title: str, items: list[str], current: str, active: bool, extras: list[str] | None = None):
    state = {"query": "", "all": False}
    extras = extras or []

    def filter_items():
        filt = items if not state["query"] else [x for x in items if state["query"].lower() in x.lower()]
        return extras + (filt if (state["all"] or state["query"]) else filt[:20])

    opts = filter_items()
    sel = opts.index(current) if (active and current in opts) else 0

    while True:
        sys.stdout.write(f"\x1b[H\x1b[2J\n   {BOLD}  SELECT {title.upper()}:{RESET}\n   {DIM}{'─'*60}{RESET}\n\n")
        if state["query"]:
            sys.stdout.write(f"   🔍  Filter: {GREEN}{state['query']}{AMBER}_{RESET}\n\n")

        start = max(0, min(sel - 7, len(opts) - 14))
        end = min(len(opts), start + 14)

        for i in range(start, end):
            opt = opts[i]
            bullet = f"{AMBER}❯{RESET} " if i == sel else "  "
            line = f"{bullet}{RED}{opt} (disabled){RESET}" if (i == 0 and not active and "Turn Off" in opt) else f"{bullet}{GREEN}{opt} (active){RESET}" if (opt == current and active) else f"{bullet}{opt}"
            sys.stdout.write(f"     {BOLD if i == sel else ''}{line}{RESET}\n")

        ind = " ▲ ▼ " if (start > 0 and end < len(opts)) else " ▼ more " if end < len(opts) else " ▲ more " if start > 0 else ""
        sys.stdout.write(f"\n   {DIM}{'─'*25 + AMBER + ind + DIM + '─'*25 if ind else '─'*60}{RESET}\n")
        sys.stdout.write(f"   {DIM}{f'Matches: {len(opts)-len(extras)}. Backspace: edit' if state['query'] else f'Top 20 shown. ► (Right) for all {len(items)}' if not state['all'] else f'Showing all {len(items)}. ◄ (Left) for Top 20'}{RESET}\n")
        sys.stdout.flush()

        key = await async_get_key()
        if key == "up":
            sel = (sel - 1) % len(opts)
        elif key == "down":
            sel = (sel + 1) % len(opts)
        elif key == "backspace" and state["query"]:
            state["query"] = state["query"][:-1]
            sel, opts = 0, filter_items()
        elif key == "esc":
            if state["query"]:
                state["query"], sel, opts = "", 0, filter_items()
            else:
                return None
        elif key in ("right", "left"):
            state["all"] = (key == "right")
            opts = filter_items()
            sel = opts.index(current) if current in opts else 0
        elif key == "enter":
            return opts[sel]
        elif isinstance(key, str) and len(key) == 1 and (key.isalnum() or key in ("-", ":", "/", ".", "_")):
            state["query"] += key
            sel, opts = 0, filter_items()


# ── Main Entry ────────────────────────────────────────────────────────────────
async def async_main():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    env = load_env_vars()
    spaces = load_json(CUSTOM_SPACES_FILE, DEFAULTS["spaces"])
    cache = load_json(CACHE_PATH, DEFAULTS)
    custom_list = list(spaces.keys()) + [x for x in cache.get("custom", []) if x not in spaces]

    menu_idx, message = 0, ""
    while True:
        active_keys = get_active_key_set()
        env = load_env_vars()

        # Current active display detection
        custom_curr = env.get("CUSTOM_MODEL", "default")
        for k, v in spaces.items():
            if custom_curr == v.get("model") or env.get("CUSTOM_URL") == v.get("url"):
                custom_curr = k
                break

        fmt = lambda curr, k: f"{GREEN}{curr}{RESET}" if k in active_keys else f"{RED}DISABLED{RESET}"
        status_all = f"{GREEN}[ ENABLED ]{RESET}" if any(k in active_keys for k in PROVIDER_KEYS) else f"{RED}[ DISABLED ]{RESET}"

        sys.stdout.write(f"\x1b[H\x1b[2J\n   {BOLD}  LOCAL-AI CONFIGURATION{RESET}\n   {DIM}{'─'*60}{RESET}\n\n")
        options = [
            f"🔌  Cloud Connection      {status_all}",
            f"🤗  Custom / HuggingFace   {fmt(custom_curr, 'CUSTOM_API_KEY')}\n       {DIM}Select from Spaces, official HF Router & local ports{RESET}",
            f"♊  Google Gemini          {fmt(env.get('GEMINI_MODEL', 'gemini-3.7-flash'), 'GEMINI_API_KEY')}\n       {DIM}Lightweight, high-speed Google endpoints{RESET}",
            f"🍎  OpenAI Subscription    {fmt(env.get('OPENAI_MODEL', 'gpt-5.5'), 'OPENAI_API_KEY')}\n       {DIM}Direct OpenAI engines{RESET}",
            f"☕  Anthropic Claude       {fmt(env.get('CLAUDE_MODEL', 'claude-fable-5'), 'CLAUDE_API_KEY')}\n       {DIM}Industry-leading Claude models{RESET}",
            f"🚀  x.AI Grok              {fmt(env.get('XAI_MODEL', 'grok-4.5'), 'XAI_API_KEY')}\n       {DIM}Ultra-high-speed Grok engines{RESET}",
            f"🌐  OpenRouter Free       {fmt(env.get('OPENROUTER_MODEL', 'openrouter/free'), 'OPENROUTER_API_KEY')}\n       {DIM}Top popular free models{RESET}",
            f"🌐  OpenRouter Paid       {fmt(env.get('OPENROUTER_MODEL', 'openrouter/free'), 'OPENROUTER_API_KEY')}\n       {DIM}High-end paid catalog{RESET}",
            f"↺  Refresh API Lists      {DIM}Sync OpenRouter & HF models live{RESET}",
            "✕  Save & Close",
        ]

        for i, opt in enumerate(options):
            sys.stdout.write(f"{f'   {AMBER}❯{RESET}  {BOLD}' if i == menu_idx else '      '}{opt}{RESET}\n{'\n' if 1 <= i <= 7 else ''}")
        sys.stdout.write(f"\n   {DIM}{'─'*60}{RESET}\n   {message or f'{DIM}▲/▼: Navigate | Enter: Select | Q: Quit{RESET}'}\n")
        sys.stdout.flush()
        message = ""

        key = await async_get_key()
        if key == "up":
            menu_idx = (menu_idx - 1) % len(options)
        elif key == "down":
            menu_idx = (menu_idx + 1) % len(options)
        elif key in ("q", "esc"):
            break
        elif key == "enter":
            if menu_idx == 0:
                is_on = toggle_env_api_keys()
                message = f"✓ Switched Connection: {GREEN+'ENABLED'+RESET if is_on else RED+'DISABLED'+RESET}"
            elif 1 <= menu_idx <= 7:
                cfg = {
                    1: ("Custom / HuggingFace", custom_list, custom_curr, "CUSTOM_API_KEY", ["🚫 Turn Off Custom / HF", "➕ [Add Endpoint / Space URL]", "🗑  [Delete Custom Space]"]),
                    2: ("Gemini", cache.get("gemini", DEFAULTS["gemini"]), env.get("GEMINI_MODEL", ""), "GEMINI_API_KEY", ["🚫 Turn Off Gemini"]),
                    3: ("OpenAI", cache.get("openai", DEFAULTS["openai"]), env.get("OPENAI_MODEL", ""), "OPENAI_API_KEY", ["🚫 Turn Off OpenAI"]),
                    4: ("Claude", cache.get("claude", DEFAULTS["claude"]), env.get("CLAUDE_MODEL", ""), "CLAUDE_API_KEY", ["🚫 Turn Off Claude"]),
                    5: ("Grok", cache.get("grok", DEFAULTS["grok"]), env.get("XAI_MODEL", ""), "XAI_API_KEY", ["🚫 Turn Off Grok"]),
                    6: ("OpenRouter Free", cache.get("free", DEFAULTS["free"]), env.get("OPENROUTER_MODEL", ""), "OPENROUTER_API_KEY", ["🚫 Turn Off OpenRouter"]),
                    7: ("OpenRouter Paid", cache.get("paid", DEFAULTS["paid"]), env.get("OPENROUTER_MODEL", ""), "OPENROUTER_API_KEY", ["🚫 Turn Off OpenRouter"]),
                }[menu_idx]

                title, model_items, cur_val, key_name, extra_opts = cfg
                res = await run_interactive_menu(title, model_items, cur_val, key_name in active_keys, extra_opts)

                if not res:
                    continue
                if res.startswith("🚫 Turn Off"):
                    isolate_active_key("")
                    message = f"✓ {title} disabled."
                elif res == "➕ [Add Endpoint / Space URL]":
                    if url_in := prompt_user_input("Paste Space / Endpoint URL"):
                        disp_name, target_url, model_name = parse_endpoint_url(url_in)
                        spaces[disp_name] = {"url": target_url, "model": model_name}
                        save_json(CUSTOM_SPACES_FILE, spaces)
                        if disp_name not in custom_list:
                            custom_list.insert(0, disp_name)
                        isolate_active_key("CUSTOM_API_KEY")
                        update_env_multiple({"CUSTOM_URL": target_url, "CUSTOM_MODEL": model_name, "CUSTOM_API_KEY": "not-needed"})
                        message = f"✓ Activated Space: {disp_name}"
                elif res == "🗑  [Delete Custom Space]":
                    del_res = await run_interactive_menu("Space to Delete", list(spaces.keys()), "", True, ["🚫 Cancel"])
                    if del_res and del_res != "🚫 Cancel" and del_res in spaces:
                        del spaces[del_res]
                        save_json(CUSTOM_SPACES_FILE, spaces)
                        if del_res in custom_list:
                            custom_list.remove(del_res)
                        message = f"✓ Removed space: '{del_res}'"
                else:
                    isolate_active_key(key_name)
                    if menu_idx == 1:
                        sp = spaces.get(res, {"url": HF_ROUTER_URL, "model": res})
                        update_env_multiple({"CUSTOM_URL": sp["url"], "CUSTOM_MODEL": sp["model"], "CUSTOM_API_KEY": "not-needed"})
                    else:
                        target_var = {2: "GEMINI_MODEL", 3: "OPENAI_MODEL", 4: "CLAUDE_MODEL", 5: "XAI_MODEL", 6: "OPENROUTER_MODEL", 7: "OPENROUTER_MODEL"}[menu_idx]
                        update_env_multiple({target_var: res})
                    message = f"✓ Primary model set: {res}"
            elif menu_idx == 8:
                message = f"{AMBER}↺ Querying live models...{RESET}"
                free_l, paid_l, hf_l = await async_fetch_remote(env.get("OPENROUTER_API_KEY", ""), env.get("CUSTOM_API_KEY", ""), spaces)
                cache["free"], cache["paid"], cache["custom"] = free_l, paid_l, hf_l
                save_json(CACHE_PATH, cache)
                custom_list = list(spaces.keys()) + [x for x in hf_l if x not in spaces]
                message = "✓ Synchronized OpenRouter and HF models live."
            elif menu_idx == 9:
                break

    cleanup_terminal()
    print("\033[1;32m✓ Local-AI configuration saved.\033[0m")


if __name__ == "__main__":
    asyncio.run(async_main())
