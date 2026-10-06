#!/usr/bin/env python3
"""Streamlined TUI Model Selector with Dynamic CUSTOM<N> Discovery [Production Ready]"""

import asyncio
import atexit
import copy
import json
import os
import re
import select
import shutil
import sys
import termios
import tty
import urllib.error as urlerr
import urllib.request as urlreq

ENV_PATH = os.path.expanduser("~/.config/py-agent/.env")
ENV_EXAMPLE = os.path.expanduser("~/.config/py-agent/.env.example")
CACHE_PATH = os.path.expanduser("~/.config/py-agent/.openrouter_cache_v2.json")
CUSTOM_SPACES_FILE = os.path.expanduser("~/.config/py-agent/custom_spaces.json")
LAST_KEY_FILE = os.path.expanduser("~/.config/py-agent/.last_cloud_key.txt")
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
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
    ],
    "free": [
        "openrouter/free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat:free",
        "qwen/qwen-2.5-coder-32b-instruct:free",
    ],
    "paid": [
        "anthropic/claude-3.7-sonnet",
        "openai/gpt-4o",
        "openai/o3-mini",
        "deepseek/deepseek-r1",
        "google/gemini-2.5-flash",
        "qwen/qwen-2.5-72b-instruct",
    ],
    "spaces": {
        "Local llama-server / vLLM (Port 8080)": {"url": "http://127.0.0.1:8080/v1/chat/completions", "model": "local-model"},
        "Local Ollama (Port 11434)": {"url": "http://127.0.0.1:11434/v1/chat/completions", "model": "llama3.3"},
    },
    "custom_presets": {
        "vercel": ["stealth/pixel-canary"],
        "tokenharbor": ["qwen3.8-flash:free", "deepseek-v4.1-flash:free"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "x.ai": ["grok-2-latest", "grok-beta"],
        "anthropic": ["claude-3-7-sonnet-20250219", "claude-3-5-haiku-20241022"],
        "openai": ["gpt-4o", "o3-mini", "gpt-4o-mini"],
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "mistral": ["codestral-latest", "mistral-large-latest"],
    }
}


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return copy.deepcopy(default)


def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass


def _atomic_write_env(lines: list[str]) -> None:
    tmp = f"{ENV_PATH}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.chmod(tmp, 0o600)
        os.replace(tmp, ENV_PATH)
    except OSError:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def ensure_env_exists():
    if os.path.exists(ENV_PATH):
        try:
            os.chmod(ENV_PATH, 0o600)
        except OSError:
            pass
        return

    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
    if os.path.isfile(ENV_EXAMPLE):
        try:
            shutil.copy2(ENV_EXAMPLE, ENV_PATH)
            os.chmod(ENV_PATH, 0o600)
            return
        except OSError:
            pass


def load_env_vars():
    ensure_env_exists()
    env = {}
    uncommented_seen = set()
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for l in f:
                    s = l.strip()
                    if m := re.match(r"^#?\s*([A-Z0-9_]+)\s*=\s*\"?([^\"]*)\"?$", s):
                        k, val = m.groups()
                        is_commented = s.startswith("#")
                        if not is_commented:
                            if k not in uncommented_seen:
                                env[k] = val
                                uncommented_seen.add(k)
                        elif k not in env:
                            env[k] = val
        except OSError:
            pass
    return env


def get_custom_indices(env: dict) -> list[str]:
    """Dynamically detects CUSTOM<N> entries (e.g. CUSTOM2, CUSTOM3, CUSTOM4) from .env."""
    indices = set()
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for l in f:
                    if m := re.search(r"CUSTOM(\d+)_(?:API_KEY|URL|MODEL)", l):
                        indices.add(m.group(1))
        except OSError:
            pass
    for k in env:
        if m := re.search(r"CUSTOM(\d+)_(?:API_KEY|URL|MODEL)", k):
            indices.add(m.group(1))
    if "2" not in indices:
        indices.add("2")
    return sorted(indices, key=lambda x: int(x))


def get_provider_keys() -> list[str]:
    """Returns all primary chat model keys including dynamically detected CUSTOM<N>_API_KEY."""
    keys = ["CUSTOM_API_KEY"]
    keys.extend(f"CUSTOM{idx}_API_KEY" for idx in get_custom_indices(load_env_vars()))
    keys.extend(["GEMINI_API_KEY", "OPENROUTER_API_KEY"])
    return keys


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
                        if val and len(val) >= 8 and not any(sub in val.lower() for sub in ("your-key-here", "aizasyyour", "not-needed", "sk-your")):
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
                if re.match(rf"^#?\s*{k}\s*=", l.strip()):
                    lines[i] = f'{k}="{v}"\n'
                    updated = True
                    break
            if not updated:
                lines.append(f'{k}="{v}"\n')
        _atomic_write_env(lines)
    except OSError:
        pass


def isolate_active_key(active_key_name: str):
    """Activates ONLY the chosen key and comments out others."""
    if not os.path.exists(ENV_PATH):
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if active_key_name:
            try:
                with open(LAST_KEY_FILE, "w", encoding="utf-8") as lkf:
                    lkf.write(active_key_name)
                os.chmod(LAST_KEY_FILE, 0o600)
            except OSError:
                pass

        provider_keys = get_provider_keys()
        for i, l in enumerate(lines):
            for k in provider_keys:
                if re.match(rf"^#?\s*{k}\s*=", l.strip()):
                    should_comment = (k != active_key_name)
                    raw = re.sub(rf"^#?\s*({k}\s*=.*)$", r"\1", l.strip())
                    lines[i] = f"{'#' if should_comment else ''}{raw}\n"

        _atomic_write_env(lines)
    except OSError:
        pass


def deactivate_key(key_to_disable: str):
    if not os.path.exists(ENV_PATH):
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, l in enumerate(lines):
            s = l.strip()
            if re.match(rf"^#?\s*{key_to_disable}\s*=", s):
                raw = re.sub(rf"^#?\s*({key_to_disable}\s*=.*)$", r"\1", s)
                lines[i] = f"#{raw}\n"
        _atomic_write_env(lines)
    except OSError:
        pass


def toggle_single_provider(key_name: str, model_var: str, default_model: str) -> bool:
    active_keys = get_active_key_set()
    if key_name in active_keys:
        deactivate_key(key_name)
        return False
    else:
        isolate_active_key(key_name)
        env = load_env_vars()
        cur_model = env.get(model_var) or default_model
        update_env_multiple({model_var: cur_model})
        return True


def toggle_independent_key(key_name: str) -> bool:
    if not os.path.exists(ENV_PATH):
        return False
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        now_active = False
        found = False
        for i, l in enumerate(lines):
            if re.match(rf"^#?\s*{key_name}\s*=", l.strip()):
                found = True
                if l.strip().startswith("#"):
                    lines[i] = re.sub(r"^#\s*", "", l)
                    now_active = True
                else:
                    lines[i] = f"#{l}"
                    now_active = False
                break
        if not found:
            lines.append(f'{key_name}="AIzaSyYourApiKeyHere"\n')
            now_active = True
        _atomic_write_env(lines)
        return now_active
    except OSError:
        return False


def toggle_env_api_keys():
    if not os.path.exists(ENV_PATH):
        return False
    active_keys = get_active_key_set()
    provider_keys = get_provider_keys()
    if any(k in active_keys for k in provider_keys):
        for k in provider_keys:
            deactivate_key(k)
        return False
    else:
        last_key = "OPENROUTER_API_KEY"
        if os.path.isfile(LAST_KEY_FILE):
            try:
                with open(LAST_KEY_FILE, "r", encoding="utf-8") as lkf:
                    read_k = lkf.read().strip()
                    if read_k in provider_keys:
                        last_key = read_k
            except OSError:
                pass
        isolate_active_key(last_key)
        return True


def detect_provider(url: str, model: str) -> tuple[str, str]:
    u, m = url.lower(), model.lower()
    if "vercel" in u or "pixel-canary" in m:
        return "Vercel Gateway", "▲"
    if "tokenharbor" in u:
        return "TokenHarbor", "⚓"
    if "deepseek" in u or "deepseek" in m:
        return "DeepSeek", "🐳"
    if "x.ai" in u or "grok" in m:
        return "xAI (Grok)", "🪐"
    if "anthropic" in u or "claude" in m:
        return "Anthropic", "🪸"
    if "openai" in u or any(x in m for x in ("gpt-", "o1", "o3-", "chatgpt")):
        return "OpenAI", "✳️"
    if "meta" in u or "llama" in m:
        return "Meta (Llama)", "🦙"
    if "groq" in u:
        return "Groq", "⚡"
    if "mistral" in u or "codestral" in m:
        return "Mistral", "🌪️"
    if u:
        host = u.split("://")[-1].split("/")[0]
        return host, "🌐"
    return "Generic Endpoint", "🌐"


def parse_endpoint_url(raw_url: str) -> tuple[str, str, str]:
    url = raw_url.strip()
    if "huggingface.co/spaces/" in url:
        parts = url.split("huggingface.co/spaces/", 1)[1].strip("/").split("/")
        if len(parts) >= 2:
            author, space = parts[0], parts[1]
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


async def async_fetch_remote(env_vars: dict, spaces: dict):
    def _fetch():
        api_key_or = env_vars.get("OPENROUTER_API_KEY", "")
        api_key_hf = env_vars.get("CUSTOM_API_KEY", "")
        api_key_gem = env_vars.get("GEMINI_API_KEY", "")

        free_c, paid_c, hf_res = [], [], list(spaces.keys())
        gem_models = []

        if api_key_gem and len(api_key_gem) > 8 and "your" not in api_key_gem.lower():
            try:
                req_gem = urlreq.Request(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    headers={"x-goog-api-key": api_key_gem}
                )
                with urlreq.urlopen(req_gem, timeout=6) as res:
                    if res.status == 200:
                        data = json.loads(res.read().decode("utf-8"))
                        for m in data.get("models", []):
                            mid = m.get("name", "").replace("models/", "")
                            if "generateContent" in m.get("supportedGenerationMethods", []) and not any(x in mid for x in ("embedding", "aqa", "imagen", "tts")):
                                gem_models.append(mid)
                        gem_models.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)], reverse=True)
            except (urlerr.URLError, json.JSONDecodeError, OSError):
                pass

        try:
            req = urlreq.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key_or}"} if api_key_or else {}
            )
            with urlreq.urlopen(req, timeout=10) as res:
                if res.status == 200:
                    models_data = json.loads(res.read().decode("utf-8")).get("data", [])
                    non_chat = ("embed", "rerank", "tts", "audio", "speech", "safety", "flux-")

                    for it in models_data:
                        m_id = it.get("id", "")
                        if not m_id or any(k in m_id.lower() for k in non_chat):
                            continue

                        p = it.get("pricing", {})
                        try:
                            prompt_price = float(p.get("prompt", 0))
                            comp_price = float(p.get("completion", 0))
                        except (ValueError, TypeError):
                            prompt_price, comp_price = 1.0, 1.0

                        is_free = (":free" in m_id.lower()) or (prompt_price == 0 and comp_price == 0)

                        if is_free:
                            if m_id != "openrouter/free" and m_id not in free_c:
                                free_c.append(m_id)
                        else:
                            paid_c.append(m_id)
        except (urlerr.URLError, json.JSONDecodeError, OSError):
            pass

        free_c.sort(key=lambda s: s.lower())
        free_c.insert(0, "openrouter/free")

        try:
            req_hf = urlreq.Request("https://router.huggingface.co/v1/models", headers={"Authorization": f"Bearer {api_key_hf}"} if (api_key_hf and "your" not in api_key_hf.lower()) else {})
            with urlreq.urlopen(req_hf, timeout=8) as res:
                if res.status == 200:
                    for it in json.loads(res.read().decode("utf-8")).get("data", []):
                        if (m_id := it.get("id")) and m_id not in hf_res:
                            hf_res.append(m_id)
                            if len(hf_res) >= 25:
                                break
        except (urlerr.URLError, json.JSONDecodeError, OSError):
            pass

        return {
            "gemini": gem_models or DEFAULTS["gemini"],
            "free": free_c or DEFAULTS["free"],
            "paid": paid_c or DEFAULTS["paid"],
            "custom": hf_res,
        }

    return await asyncio.to_thread(_fetch)


async def async_get_key():
    fd = sys.stdin.fileno()

    def _read():
        if not sys.stdin.isatty():
            return "esc"
        try:
            old = termios.tcgetattr(fd)
        except (termios.error, OSError):
            return "esc"

        try:
            tty.setraw(fd)
            if not (b := os.read(fd, 1)):
                return "esc"
            ch = b.decode("utf-8", errors="ignore")
            if ch == "\x1b" and select.select([fd], [], [], 0.05)[0]:
                return {"[A": "up", "OA": "up", "[B": "down", "OB": "down", "[C": "right", "OC": "right", "[D": "left", "OD": "left"}.get(os.read(fd, 2).decode("utf-8", errors="ignore"), "esc")
            return {"\x1b": "esc", "\r": "enter", "\n": "enter", " ": "space", "\x7f": "backspace", "\x08": "backspace"}.get(ch, ch.lower() if ch.lower() == "q" else ch)
        except Exception:
            return "esc"
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except (termios.error, OSError):
                pass

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
    state = {"query": "", "all": len(items) <= 50}
    extras = extras or []

    def filter_items():
        filt = items if not state["query"] else [x for x in items if state["query"].lower() in x.lower()]
        return extras + (filt if (state["all"] or state["query"]) else filt[:20])

    opts = filter_items()

    def _is_cur(item: str) -> bool:
        return item == current or item.split()[0] == current

    cur_idx = next((i for i, x in enumerate(opts) if _is_cur(x)), None)
    if active and cur_idx is not None:
        sel = cur_idx
    elif len(opts) > len(extras):
        sel = len(extras)
    else:
        sel = 0

    while True:
        sys.stdout.write(f"\x1b[H\x1b[2J\n   {BOLD}  SELECT {title.upper()}:{RESET}\n   {DIM}{'─'*60}{RESET}\n\n")
        if state["query"]:
            sys.stdout.write(f"   🔍  Filter: {GREEN}{state['query']}{AMBER}_{RESET}\n\n")

        start = max(0, min(sel - 7, len(opts) - 14))
        end = min(len(opts), start + 14)

        for i in range(start, end):
            opt = opts[i]
            bullet = f"{AMBER}❯{RESET} " if i == sel else "  "
            line = f"{bullet}{RED}{opt} (disabled){RESET}" if (i == 0 and not active and "Turn Off" in opt) else f"{bullet}{GREEN}{opt} (active){RESET}" if (_is_cur(opt) and active) else f"{bullet}{opt}"
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


async def async_main():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    ensure_env_exists()
    env = load_env_vars()
    spaces = load_json(CUSTOM_SPACES_FILE, DEFAULTS["spaces"])
    cache = load_json(CACHE_PATH, DEFAULTS)

    free_list = cache.get("free", DEFAULTS["free"])
    if "openrouter/free" in free_list:
        free_list.remove("openrouter/free")
    free_list.insert(0, "openrouter/free")
    cache["free"] = free_list

    custom_list = list(spaces.keys()) + [x for x in cache.get("custom", []) if x not in spaces]

    menu_idx, message = 0, ""
    while True:
        active_keys = get_active_key_set()
        env = load_env_vars()
        provider_keys = get_provider_keys()
        custom_indices = get_custom_indices(env)

        col_w = 25

        # ── Custom 1 (Local / HF) Status ──
        custom_curr = env.get("CUSTOM_MODEL", "default")
        for k, v in spaces.items():
            if custom_curr == v.get("model") or env.get("CUSTOM_URL") == v.get("url"):
                custom_curr = k
                break

        or_model_val = env.get("OPENROUTER_MODEL", "").lower()
        is_or_active = "OPENROUTER_API_KEY" in active_keys
        free_ids_lower = {m.lower() for m in free_list}
        is_free_active = is_or_active and (or_model_val in free_ids_lower or "free" in or_model_val or not or_model_val)
        is_paid_active = is_or_active and not is_free_active

        def fmt(curr: str, k: str, ak: set[str] = active_keys) -> str:
            return f"{GREEN}{curr}{RESET}" if k in ak else f"{RED}DISABLED{RESET}"

        fmt_or_free = f"{GREEN}{env.get('OPENROUTER_MODEL', 'openrouter/free')}{RESET}" if is_free_active else f"{RED}DISABLED{RESET}"
        fmt_or_paid = f"{GREEN}{env.get('OPENROUTER_MODEL', 'anthropic/claude-3.7-sonnet')}{RESET}" if is_paid_active else f"{RED}DISABLED{RESET}"
        status_all = f"{GREEN}ENABLED{RESET}" if any(k in active_keys for k in provider_keys) else f"{RED}DISABLED{RESET}"

        gnd_curr = env.get("GND_MODEL", "gemini-2.5-flash")
        voice_curr = env.get("GEM_MODEL", "gemini-3.5-flash-lite")
        img_curr = env.get("IMG_MODEL", "gemini-3.5-flash-lite")
        ctx_curr = env.get("AI_MAX_TOKENS", "8192")
        rounds_curr = env.get("AI_MAX_AGENT_ROUNDS", "10")

        # ── Dynamically Build Menu Items & Handlers ──
        items = []

        # 0: Cloud Connection Master Toggle
        items.append({"type": "cloud", "render": f"🔌  {'Cloud Connection':<{col_w}} {status_all}"})

        # 1: Custom 1
        items.append({
            "type": "custom1",
            "render": f"🤗  {'Custom 1 (Local / HF)':<{col_w}} {fmt(custom_curr, 'CUSTOM_API_KEY')}\n       {DIM}Local llama-server, Ollama, HF Spaces & official HF Router{RESET}"
        })

        # 2..N: Dynamic CUSTOM<N> Generic Endpoints
        for n in custom_indices:
            c_url = env.get(f"CUSTOM{n}_URL", "")
            c_mod = env.get(f"CUSTOM{n}_MODEL", "default")
            c_name, c_icon = detect_provider(c_url, c_mod)
            c_label = f"Custom {n} ({c_name})"
            items.append({
                "type": "custom_generic",
                "n": n,
                "name": c_name,
                "url": c_url,
                "model": c_mod,
                "render": f"{c_icon}  {c_label:<{col_w}} {fmt(c_mod, f'CUSTOM{n}_API_KEY')}\n       {DIM}Direct endpoint via {c_url or 'OpenAI-compatible URL'}{RESET}"
            })

        # Gemini & OpenRouter
        items.append({
            "type": "gemini",
            "render": f"✨  {'Google Gemini':<{col_w}} {fmt(env.get('GEMINI_MODEL', 'gemini-2.5-flash'), 'GEMINI_API_KEY')}\n       {DIM}Free daily tier via Google AI Studio{RESET}"
        })
        items.append({
            "type": "or_free",
            "render": f"🌐  {'OpenRouter Free':<{col_w}} {fmt_or_free}\n       {DIM}Top rotating community models (100% free){RESET}"
        })
        items.append({
            "type": "or_paid",
            "render": f"🌐  {'OpenRouter Paid':<{col_w}} {fmt_or_paid}\n       {DIM}High-end paid catalog (Claude, GPT, DeepSeek, Llama){RESET}"
        })

        # Auxiliary Services (Compact)
        items.append({"type": "aux", "key": "GND_KEY", "mod": "GND_MODEL", "curr": gnd_curr, "title": "Search Grounding (/gnd)", "render": f"🔍  {'Search Grounding (/gnd)':<{col_w}} {fmt(gnd_curr, 'GND_KEY')}"})
        items.append({"type": "aux", "key": "GEM_VOICE", "mod": "GEM_MODEL", "curr": voice_curr, "title": "Voice Transcription", "render": f"🎙️  {'Voice Transcription':<{col_w}} {fmt(voice_curr, 'GEM_VOICE')}"})
        items.append({"type": "aux", "key": "IMG_VOICE", "mod": "IMG_MODEL", "curr": img_curr, "title": "Vision OCR Multimodal", "render": f"👁️  {'Vision OCR Multimodal':<{col_w}} {fmt(img_curr, 'IMG_VOICE')}"})

        # Tokens, Rounds, Refresh & Exit (Compact)
        items.append({"type": "tokens", "render": f"🧠  {'Context Budget':<{col_w}} {GREEN}{ctx_curr} tokens{RESET}"})
        items.append({"type": "rounds", "render": f"🔄  {'Max Agent Rounds':<{col_w}} {GREEN}{rounds_curr} rounds{RESET}"})
        items.append({"type": "refresh", "render": f"↺  Refresh API Lists        {DIM}Sync live endpoints (Gemini, OpenRouter, HF){RESET}"})
        items.append({"type": "exit", "render": "✕  Save & Close"})

        # ── Render Terminal UI ──
        sys.stdout.write(f"\x1b[H\x1b[2J\n   {BOLD}  LOCAL-AI CONFIGURATION{RESET}\n   {DIM}{'─'*60}{RESET}\n\n")

        for i, itm in enumerate(items):
            # Dynamic dividers based on item types
            if itm["type"] == "aux" and (i == 0 or items[i-1]["type"] != "aux"):
                sys.stdout.write(f"   {DIM}{'─'*19}  Auxiliary Services  {'─'*19}{RESET}\n\n")
            elif itm["type"] == "tokens":
                sys.stdout.write(f"\n   {DIM}{'─'*18}  Context & Loop Budget  {'─'*17}{RESET}\n\n")
            elif itm["type"] == "refresh":
                sys.stdout.write(f"\n   {DIM}{'─'*60}{RESET}\n")

            cursor = f"   {AMBER}❯{RESET}  {BOLD}" if i == menu_idx else "      "
            extra_nl = "\n" if itm["type"] in ("custom1", "custom_generic", "gemini", "or_free", "or_paid") else ""
            sys.stdout.write(f"{cursor}{itm['render']}{RESET}\n{extra_nl}")

        sys.stdout.write(f"\n   {DIM}{'─'*60}{RESET}\n   {message or f'{DIM}▲/▼: Navigate | Space: Toggle | Enter: Select | Q: Quit{RESET}'}\n")
        sys.stdout.flush()
        message = ""

        key = await async_get_key()
        if key == "up":
            menu_idx = (menu_idx - 1) % len(items)
        elif key == "down":
            menu_idx = (menu_idx + 1) % len(items)
        elif key in ("q", "esc"):
            break
        elif key == "space":
            target = items[menu_idx]
            ttype = target["type"]

            if ttype == "custom1":
                now_on = toggle_single_provider("CUSTOM_API_KEY", "CUSTOM_MODEL", "Qwen/Qwen3.8-27B")
                message = f"✓ Custom 1/HF: {GREEN+'ENABLED'+RESET if now_on else RED+'DISABLED'+RESET}"
            elif ttype == "custom_generic":
                n = target["n"]
                d_mod = target["model"] or "default"
                now_on = toggle_single_provider(f"CUSTOM{n}_API_KEY", f"CUSTOM{n}_MODEL", d_mod)
                message = f"✓ Custom {n} ({target['name']}): {GREEN+'ENABLED'+RESET if now_on else RED+'DISABLED'+RESET}"
            elif ttype == "gemini":
                now_on = toggle_single_provider("GEMINI_API_KEY", "GEMINI_MODEL", "gemini-2.5-flash")
                message = f"✓ Gemini: {GREEN+'ENABLED'+RESET if now_on else RED+'DISABLED'+RESET}"
            elif ttype in ("or_free", "or_paid"):
                cur_or_model = env.get("OPENROUTER_MODEL") or "openrouter/free"
                target_m = cur_or_model if (ttype == "or_free" and "free" in cur_or_model.lower()) else "openrouter/free" if ttype == "or_free" else cur_or_model if "free" not in cur_or_model.lower() else "anthropic/claude-3.7-sonnet"
                now_on = toggle_single_provider("OPENROUTER_API_KEY", "OPENROUTER_MODEL", target_m)
                message = f"✓ OpenRouter: {GREEN+'ENABLED'+RESET if now_on else RED+'DISABLED'+RESET}"
            elif ttype == "aux":
                now_on = toggle_independent_key(target["key"])
                message = f"✓ {target['title']}: {GREEN+'ENABLED'+RESET if now_on else RED+'DISABLED'+RESET}"
            elif ttype == "rounds":
                cycle_rounds = ["5", "10", "15", "20", "25", "30", "50"]
                next_rounds = cycle_rounds[(cycle_rounds.index(rounds_curr) + 1) % len(cycle_rounds)] if rounds_curr in cycle_rounds else "10"
                update_env_multiple({"AI_MAX_AGENT_ROUNDS": next_rounds})
                message = f"✓ Max Agent Rounds: {next_rounds}"

        elif key == "enter":
            target = items[menu_idx]
            ttype = target["type"]

            if ttype == "cloud":
                is_on = toggle_env_api_keys()
                message = f"✓ Switched Connection: {GREEN+'ENABLED'+RESET if is_on else RED+'DISABLED'+RESET}"

            elif ttype == "custom_generic":
                n = target["n"]
                c_key_name = f"CUSTOM{n}_API_KEY"
                c_mod_name = f"CUSTOM{n}_MODEL"
                c_url_name = f"CUSTOM{n}_URL"
                c_curr_m = target["model"]
                c_name_val = target["name"]
                c_url_val = target["url"]

                provider_key = next((k for k in DEFAULTS["custom_presets"] if k in c_url_val.lower()), None)
                preset_models = DEFAULTS["custom_presets"].get(provider_key, [c_curr_m]) if provider_key else [c_curr_m]
                c_menu_items = list(dict.fromkeys(preset_models + ["stealth/pixel-canary", "deepseek-chat", "gpt-4o"]))

                res = await run_interactive_menu(
                    f"Custom {n} ({c_name_val})",
                    c_menu_items,
                    c_curr_m,
                    c_key_name in active_keys,
                    [f"🚫 Turn Off Custom {n}", "✏️  [Edit Model Name]", "🔗 [Edit Endpoint URL]", "🔑 [Edit API Key]"]
                )

                if not res:
                    continue
                if res.startswith("🚫 Turn Off"):
                    deactivate_key(c_key_name)
                    message = f"✓ Custom {n} disabled."
                elif res == "✏️  [Edit Model Name]":
                    if m_in := prompt_user_input(f"Enter model name for Custom {n} (current: {c_curr_m})"):
                        update_env_multiple({c_mod_name: m_in})
                        isolate_active_key(c_key_name)
                        message = f"✓ Custom {n} Model set to: {m_in}"
                elif res == "🔗 [Edit Endpoint URL]":
                    if u_in := prompt_user_input("Enter completions URL (e.g. https://ai-gateway.vercel.sh/v1/chat/completions)"):
                        update_env_multiple({c_url_name: u_in})
                        message = f"✓ Custom {n} URL updated to: {u_in}"
                elif res == "🔑 [Edit API Key]":
                    if k_in := prompt_user_input(f"Enter API Key for Custom {n}"):
                        update_env_multiple({c_key_name: k_in})
                        isolate_active_key(c_key_name)
                        message = f"✓ Custom {n} API key updated and activated."
                else:
                    isolate_active_key(c_key_name)
                    update_env_multiple({c_mod_name: res})
                    message = f"✓ Custom {n} Model set: {res}"

            elif ttype in ("custom1", "gemini", "or_free", "or_paid"):
                if ttype == "custom1":
                    title, model_items, cur_val, key_name, extra_opts = ("Custom 1 / HuggingFace", custom_list, custom_curr, "CUSTOM_API_KEY", ["🚫 Turn Off Custom 1", "➕ [Add Endpoint / Space URL]", "🗑  [Delete Custom Space]"])
                elif ttype == "gemini":
                    title, model_items, cur_val, key_name, extra_opts = ("Gemini", cache.get("gemini", DEFAULTS["gemini"]), env.get("GEMINI_MODEL", ""), "GEMINI_API_KEY", ["🚫 Turn Off Gemini"])
                elif ttype == "or_free":
                    title, model_items, cur_val, key_name, extra_opts = ("OpenRouter Free", cache.get("free", DEFAULTS["free"]), env.get("OPENROUTER_MODEL", ""), "OPENROUTER_API_KEY", ["🚫 Turn Off OpenRouter"])
                else:
                    title, model_items, cur_val, key_name, extra_opts = ("OpenRouter Paid", cache.get("paid", DEFAULTS["paid"]), env.get("OPENROUTER_MODEL", ""), "OPENROUTER_API_KEY", ["🚫 Turn Off OpenRouter"])

                res = await run_interactive_menu(title, model_items, cur_val, key_name in active_keys, extra_opts)
                if not res:
                    continue
                if res.startswith("🚫 Turn Off"):
                    deactivate_key(key_name)
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
                    if ttype == "custom1":
                        sp = spaces.get(res, {"url": HF_ROUTER_URL, "model": res})
                        update_env_multiple({"CUSTOM_URL": sp["url"], "CUSTOM_MODEL": sp["model"]})
                    else:
                        target_var = "GEMINI_MODEL" if ttype == "gemini" else "OPENROUTER_MODEL"
                        update_env_multiple({target_var: res})
                    message = f"✓ Primary model set: {res}"

            elif ttype == "aux":
                a_presets = ["gemini-2.5-flash", "gemini-2.0-flash"]
                res = await run_interactive_menu(
                    target["title"],
                    a_presets,
                    target["curr"],
                    target["key"] in active_keys,
                    [f"🚫 Turn Off {target['title']}", "🔑 [Edit API Key]", "✏️  [Custom Model Name]"]
                )
                if not res:
                    continue
                if res.startswith("🚫 Turn Off"):
                    toggle_independent_key(target["key"])
                    message = f"✓ {target['title']} disabled."
                elif res == "🔑 [Edit API Key]":
                    if k_in := prompt_user_input(f"Enter API Key for {target['title']}"):
                        update_env_multiple({target["key"]: k_in})
                        message = f"✓ {target['key']} saved and activated."
                elif res == "✏️  [Custom Model Name]":
                    if m_in := prompt_user_input(f"Enter model for {target['title']} (current: {target['curr']})"):
                        update_env_multiple({target["mod"]: m_in})
                        message = f"✓ {target['mod']} updated: {m_in}"
                else:
                    update_env_multiple({target["mod"]: res})
                    if target["key"] not in active_keys:
                        toggle_independent_key(target["key"])
                    message = f"✓ {target['title']} model set: {res}"

            elif ttype == "tokens":
                ctx_presets = [
                    "4096 (4k - Low RAM / CPU)",
                    "8192 (8k - Default Local)",
                    "16384 (16k - Mid Local GPU)",
                    "32768 (32k - Cloud / 24GB GPU)",
                    "65536 (64k - DeepSeek / Claude)",
                    "131072 (128k - Maximum Cloud)",
                ]
                cur_preset = next((p for p in ctx_presets if p.startswith(ctx_curr)), ctx_curr)
                res = await run_interactive_menu("Context Window Budget", ctx_presets, cur_preset, True, ["✏️  [Custom Token Limit]"])
                if not res:
                    continue
                if res == "✏️  [Custom Token Limit]":
                    if t_in := prompt_user_input(f"Enter token limit (current: {ctx_curr})"):
                        clean_tok = "".join(c for c in t_in if c.isdigit())
                        if clean_tok and int(clean_tok) > 0:
                            update_env_multiple({"AI_MAX_TOKENS": clean_tok})
                            message = f"✓ Context window budget set to {clean_tok} tokens."
                else:
                    tok_val = res.split()[0]
                    update_env_multiple({"AI_MAX_TOKENS": tok_val})
                    message = f"✓ Context window budget set to {tok_val} tokens."

            elif ttype == "rounds":
                round_presets = [
                    "5 (Fast / Strict Tool Limit)",
                    "10 (10 rounds - Default)",
                    "15 (15 rounds - Extended)",
                    "20 (20 rounds - Deep Investigation)",
                    "25 (25 rounds - High Autonomy)",
                    "30 (30 rounds - Heavy Refactoring)",
                    "50 (50 rounds - Autonomous Loop)",
                ]
                cur_preset = next((p for p in round_presets if p.startswith(f"{rounds_curr} ")), rounds_curr)
                res = await run_interactive_menu("Max Agent Rounds", round_presets, cur_preset, True, ["✏️  [Custom Rounds Limit]"])
                if not res:
                    continue
                if res == "✏️  [Custom Rounds Limit]":
                    if r_in := prompt_user_input(f"Enter max agent rounds (current: {rounds_curr})"):
                        clean_r = "".join(c for c in r_in if c.isdigit())
                        if clean_r and int(clean_r) > 0:
                            update_env_multiple({"AI_MAX_AGENT_ROUNDS": clean_r})
                            message = f"✓ Max agent rounds set to {clean_r}."
                else:
                    r_val = res.split()[0]
                    update_env_multiple({"AI_MAX_AGENT_ROUNDS": r_val})
                    message = f"✓ Max agent rounds set to {r_val}."

            elif ttype == "refresh":
                message = f"{AMBER}↺ Querying live models...{RESET}"
                remote_data = await async_fetch_remote(env, spaces)
                cache.update(remote_data)
                save_json(CACHE_PATH, cache)
                custom_list = list(spaces.keys()) + [x for x in cache.get("custom", []) if x not in spaces]
                message = "✓ Synchronized endpoints live."

            elif ttype == "exit":
                break

    cleanup_terminal()
    print("\033[1;32m✓ Local-AI configuration saved.\033[0m")


if __name__ == "__main__":
    asyncio.run(async_main())
