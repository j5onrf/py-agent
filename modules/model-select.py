#!/usr/bin/env python3
"""Streamlined TUI Model Selector driven by Local/HF, Generic Custom 2, Google Gemini & OpenRouter"""

import asyncio
import atexit
import json
import os
import re
import select
import shutil
import sys
import termios
import time
import tty
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
    "gemini": ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.5-pro"],
    "free": [
        "openrouter/free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "minimax/minimax-m3:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat:free",
        "qwen/qwen-2.5-coder-32b-instruct:free",
    ],
    "paid": [
        "anthropic/claude-3.7-sonnet",
        "openai/gpt-4o",
        "openai/o3-mini",
        "deepseek/deepseek-r1",
        "google/gemini-3.8-flash",
        "qwen/qwen-2.5-72b-instruct",
    ],
    "spaces": {
        "Local llama-server / vLLM (Port 8080)": {"url": "http://127.0.0.1:8080/v1/chat/completions", "model": "local-model"},
        "Local Ollama (Port 11434)": {"url": "http://127.0.0.1:11434/v1/chat/completions", "model": "llama3.3"},
    },
    "custom2_models": {
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "x.ai": ["grok-2-latest", "grok-2-vision-latest", "grok-beta"],
        "anthropic": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
        "openai": ["gpt-4o", "gpt-4o-mini", "o3-mini", "o1"],
        "meta": ["meta-llama/Llama-3.3-70B-Instruct", "meta-llama/Llama-3.1-8B-Instruct"],
        "spark": ["spark-lite", "spark-v3.5", "spark-max", "spark-ultra"],
        "muse": ["muse-v1", "muse-chat"],
        "groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "llama-3.1-8b-instant"],
        "mistral": ["mistral-large-latest", "codestral-latest", "mistral-small-latest"],
        "together": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3"],
    }
}

PROVIDER_KEYS = ["CUSTOM_API_KEY", "CUSTOM2_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"]


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
    """Auto-applies template for new users if .env does not exist."""
    if not os.path.exists(ENV_PATH):
        os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
        if os.path.isfile(ENV_EXAMPLE):
            try:
                shutil.copy2(ENV_EXAMPLE, ENV_PATH)
                return
            except OSError:
                pass

        template = (
            "# ==============================================================================\n"
            "# Py-Agent Environment Configuration (.env.example)\n"
            "#\n"
            "# RULES:\n"
            "# 1. Top-Down: First uncommented key is active.\n"
            "# 2. Toggle: Add '#' to disable; remove '#' to enable.\n"
            "# 3. Add More: Define CUSTOM3_*, CUSTOM4_*, etc. anywhere.\n"
            "# 4. Fallback: If all keys have '#', routes to local server (:8080).\n"
            "# 5. TUI Config: Run 'model select' to configure everything interactively.\n"
            "# ==============================================================================\n\n"
            "# ── 1. Custom 1 / Hugging Face Router ─────────────────────────────────────────\n"
            '# CUSTOM_API_KEY="not-needed"\n'
            'CUSTOM_URL="https://router.huggingface.co/v1/chat/completions"\n'
            'CUSTOM_MODEL="Qwen/Qwen3.8-27B"\n\n'
            "# ── 2. Custom 2 / Generic Endpoint (DeepSeek, OpenAI, etc.) ───────────────────\n"
            '# CUSTOM2_API_KEY="sk-your-key-here"\n'
            'CUSTOM2_URL="https://api.deepseek.com/chat/completions"\n'
            'CUSTOM2_MODEL="deepseek-chat"\n\n'
            "# ── 3. Google Gemini (Free daily tier via Google AI Studio) ───────────────────\n"
            '# GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"\n'
            'GEMINI_MODEL="gemini-3.5-flash-lite"\n\n'
            "# ── 4. OpenRouter (Free community models & Universal paid gateway) ────────────\n"
            '# OPENROUTER_API_KEY="sk-or-v1-YourOpenRouterKeyHere"\n'
            'OPENROUTER_MODEL="openrouter/free"\n\n'
            "# ── Auxiliary Services (Independent Toggles) ──────────────────────────────────\n\n"
            "# Google Search Grounding (/gnd)\n"
            '# GND_KEY="AIzaSyYourGeminiApiKeyHere"\n'
            '# GND_MODEL="gemini-2.5-flash"\n\n'
            "# Voice Bridge Transcription (Speech-to-Text on :9999)\n"
            '# GEM_VOICE="AIzaSyYourGeminiApiKeyHere"\n'
            '# GEM_MODEL="gemini-3.5-flash-lite"\n\n'
            "# Multimodal Vision OCR (Pre-processor for text-only local models)\n"
            '# IMG_VOICE="AIzaSyYourGeminiApiKeyHere"\n'
            '# IMG_MODEL="gemini-3.5-flash-lite"\n\n'
            "# ── Context Window Budget ─────────────────────────────────────────────────────\n"
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
                if re.match(rf"^#?\s*{k}\s*=", l.strip()):
                    lines[i] = f'{k}="{v}"\n'
                    updated = True
                    break
            if not updated:
                lines.append(f'{k}="{v}"\n')
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
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
            except OSError:
                pass

        for i, l in enumerate(lines):
            for k in PROVIDER_KEYS:
                if re.match(rf"^#?\s*{k}\s*=", l.strip()):
                    should_comment = (k != active_key_name)
                    raw = re.sub(rf"^#?\s*({k}\s*=.*)$", r"\1", l.strip())
                    lines[i] = f"{'#' if should_comment else ''}{raw}\n"

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        pass


def toggle_single_provider(key_name: str, model_var: str, default_model: str) -> bool:
    active_keys = get_active_key_set()
    if key_name in active_keys:
        isolate_active_key("")
        return False
    else:
        isolate_active_key(key_name)
        env = load_env_vars()
        cur_model = env.get(model_var) or default_model
        update_env_multiple({model_var: cur_model})
        return True


def toggle_independent_key(key_name: str) -> bool:
    """Toggles an auxiliary service key (GND_KEY, GEM_VOICE, IMG_VOICE) without disturbing primary chat models."""
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
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return now_active
    except OSError:
        return False


def toggle_env_api_keys():
    if not os.path.exists(ENV_PATH):
        return False
    active_keys = get_active_key_set()
    if any(k in active_keys for k in PROVIDER_KEYS):
        isolate_active_key("")
        return False
    else:
        last_key = "OPENROUTER_API_KEY"
        if os.path.isfile(LAST_KEY_FILE):
            try:
                with open(LAST_KEY_FILE, "r", encoding="utf-8") as lkf:
                    read_k = lkf.read().strip()
                    if read_k in PROVIDER_KEYS:
                        last_key = read_k
            except OSError:
                pass
        isolate_active_key(last_key)
        return True


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

        if api_key_gem and "your" not in api_key_gem.lower():
            try:
                req_gem = urlreq.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key_gem}")
                with urlreq.urlopen(req_gem, timeout=6) as res:
                    if res.status == 200:
                        data = json.loads(res.read().decode("utf-8"))
                        for m in data.get("models", []):
                            mid = m.get("name", "").replace("models/", "")
                            if "generateContent" in m.get("supportedGenerationMethods", []) and not any(x in mid for x in ("embedding", "aqa", "imagen", "tts")):
                                gem_models.append(mid)
                        gem_models.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)], reverse=True)
            except Exception:
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
        except Exception:
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
        except Exception:
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
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            if not (b := os.read(fd, 1)):
                return None
            ch = b.decode("utf-8", errors="ignore")
            if ch == "\x1b" and select.select([fd], [], [], 0.05)[0]:
                return {"[A": "up", "OA": "up", "[B": "down", "OB": "down", "[C": "right", "OC": "right", "[D": "left", "OD": "left"}.get(os.read(fd, 2).decode("utf-8", errors="ignore"), "esc")
            return {"\x1b": "esc", "\r": "enter", "\n": "enter", " ": "space", "\x7f": "backspace", "\x08": "backspace"}.get(ch, ch.lower() if ch.lower() == "q" else ch)
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

    if active and current in opts:
        sel = opts.index(current)
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


async def async_main():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    ensure_env_exists()
    env = load_env_vars()
    spaces = load_json(CUSTOM_SPACES_FILE, DEFAULTS["spaces"])
    cache = load_json(CACHE_PATH, DEFAULTS)

    cache_mtime = os.path.getmtime(CACHE_PATH) if os.path.exists(CACHE_PATH) else 0
    if time.time() - cache_mtime > 86400:
        try:
            remote_data = await async_fetch_remote(env, spaces)
            cache.update(remote_data)
            save_json(CACHE_PATH, cache)
        except Exception:
            pass

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

        col_w = 25

        # ── Custom 1 (Local / HF) Status ──
        custom_curr = env.get("CUSTOM_MODEL", "default")
        for k, v in spaces.items():
            if custom_curr == v.get("model") or env.get("CUSTOM_URL") == v.get("url"):
                custom_curr = k
                break

        # ── Custom 2 (Generic Endpoint) Dynamic Brand & Icon Detection ──
        custom2_curr = env.get("CUSTOM2_MODEL", "default")
        c2_url = env.get("CUSTOM2_URL", "").lower()
        c2_mod = custom2_curr.lower()

        if "deepseek" in c2_url or "deepseek" in c2_mod:
            c2_name, c2_icon = "DeepSeek", "🐳"
        elif "x.ai" in c2_url or "grok" in c2_mod:
            c2_name, c2_icon = "xAI (Grok)", "🪐"
        elif "anthropic" in c2_url or "claude" in c2_mod:
            c2_name, c2_icon = "Anthropic", "🪸"
        elif "openai" in c2_url or any(x in c2_mod for x in ("gpt-", "o1", "o3-", "chatgpt")):
            c2_name, c2_icon = "OpenAI", "✳️"
        elif "meta" in c2_url or "llama" in c2_mod:
            c2_name, c2_icon = "Meta (Llama)", "🦙"
        elif "spark" in c2_url or "xfyun" in c2_url or "spark" in c2_mod:
            c2_name, c2_icon = "iFlytek Spark", "✨"
        elif "muse" in c2_url or "muse" in c2_mod:
            c2_name, c2_icon = "Muse", "🎨"
        elif "groq" in c2_url:
            c2_name, c2_icon = "Groq", "⚡"
        elif "mistral" in c2_url or "codestral" in c2_mod:
            c2_name, c2_icon = "Mistral", "🌪️"
        elif "together" in c2_url:
            c2_name, c2_icon = "Together AI", "🤝"
        elif "perplexity" in c2_url:
            c2_name, c2_icon = "Perplexity", "🔮"
        elif c2_url:
            host = c2_url.split("://")[-1].split("/")[0]
            c2_name, c2_icon = host, "🌐"
        else:
            c2_name, c2_icon = "Direct Endpoint", "🌐"

        c2_label = f"Custom 2 ({c2_name})"

        or_model_val = env.get("OPENROUTER_MODEL", "").lower()
        is_or_active = "OPENROUTER_API_KEY" in active_keys
        is_free_active = is_or_active and ("free" in or_model_val or not or_model_val)
        is_paid_active = is_or_active and not is_free_active

        fmt = lambda curr, k: f"{GREEN}{curr}{RESET}" if k in active_keys else f"{RED}DISABLED{RESET}"
        fmt_or_free = f"{GREEN}{env.get('OPENROUTER_MODEL', 'openrouter/free')}{RESET}" if is_free_active else f"{RED}DISABLED{RESET}"
        fmt_or_paid = f"{GREEN}{env.get('OPENROUTER_MODEL', 'anthropic/claude-3.7-sonnet')}{RESET}" if is_paid_active else f"{RED}DISABLED{RESET}"
        status_all = f"{GREEN}ENABLED{RESET}" if any(k in active_keys for k in PROVIDER_KEYS) else f"{RED}DISABLED{RESET}"

        gnd_curr = env.get("GND_MODEL", "gemini-2.5-flash")
        voice_curr = env.get("GEM_MODEL", "gemini-3.5-flash-lite")
        img_curr = env.get("IMG_MODEL", "gemini-3.5-flash-lite")

        sys.stdout.write(f"\x1b[H\x1b[2J\n   {BOLD}  LOCAL-AI CONFIGURATION{RESET}\n   {DIM}{'─'*60}{RESET}\n\n")
        options = [
            f"🔌  {'Cloud Connection':<{col_w}} {status_all}",
            f"🤗  {'Custom 1 (Local / HF)':<{col_w}} {fmt(custom_curr, 'CUSTOM_API_KEY')}\n       {DIM}Local llama-server, Ollama, HF Spaces & official HF Router{RESET}",
            f"{c2_icon}  {c2_label:<{col_w}} {fmt(custom2_curr, 'CUSTOM2_API_KEY')}\n       {DIM}Direct endpoint via {c2_url or 'OpenAI-compatible URL'}{RESET}",
            f"✨  {'Google Gemini':<{col_w}} {fmt(env.get('GEMINI_MODEL', 'gemini-3.8-flash'), 'GEMINI_API_KEY')}\n       {DIM}Free daily tier via Google AI Studio{RESET}",
            f"🌐  {'OpenRouter Free':<{col_w}} {fmt_or_free}\n       {DIM}Top rotating community models (100% free){RESET}",
            f"🌐  {'OpenRouter Paid':<{col_w}} {fmt_or_paid}\n       {DIM}High-end paid catalog (Claude, GPT, DeepSeek, Llama){RESET}",
            f"🔍  {'Search Grounding (/gnd)':<{col_w}} {fmt(gnd_curr, 'GND_KEY')}\n       {DIM}Live Google search retrieval for facts & documentation{RESET}",
            f"🎙️  {'Voice Transcription':<{col_w}} {fmt(voice_curr, 'GEM_VOICE')}\n       {DIM}Low-latency voice-to-text bridge (:9999){RESET}",
            f"👁️  {'Vision OCR Multimodal':<{col_w}} {fmt(img_curr, 'IMG_VOICE')}\n       {DIM}Gemini OCR pre-processor for text-only local models{RESET}",
            f"↺  Refresh API Lists        {DIM}Sync live endpoints (Gemini, OpenRouter, HF){RESET}",
            "✕  Save & Close",
        ]

        for i, opt in enumerate(options):
            if i == 6:
                sys.stdout.write(f"   {DIM}{'─'*19}  Auxiliary Services  {'─'*19}{RESET}\n\n")
            elif i == 9:
                sys.stdout.write(f"   {DIM}{'─'*60}{RESET}\n")
            sys.stdout.write(f"{f'   {AMBER}❯{RESET}  {BOLD}' if i == menu_idx else '      '}{opt}{RESET}\n{'\n' if (1 <= i <= 5 or 6 <= i <= 8) else ''}")
        sys.stdout.write(f"\n   {DIM}{'─'*60}{RESET}\n   {message or f'{DIM}▲/▼: Navigate | Space: Toggle | Enter: Select | Q: Quit{RESET}'}\n")
        sys.stdout.flush()
        message = ""

        key = await async_get_key()
        if key == "up":
            menu_idx = (menu_idx - 1) % len(options)
        elif key == "down":
            menu_idx = (menu_idx + 1) % len(options)
        elif key in ("q", "esc"):
            break
        elif key == "space" and 1 <= menu_idx <= 8:
            if 1 <= menu_idx <= 5:
                cur_or_model = env.get("OPENROUTER_MODEL") or "openrouter/free"
                k_map = {
                    1: ("CUSTOM_API_KEY", "CUSTOM_MODEL", "Qwen/Qwen3.8-27B"),
                    2: ("CUSTOM2_API_KEY", "CUSTOM2_MODEL", custom2_curr or "deepseek-chat"),
                    3: ("GEMINI_API_KEY", "GEMINI_MODEL", "gemini-3.8-flash"),
                    4: ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", cur_or_model if "free" in cur_or_model.lower() else "openrouter/free"),
                    5: ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", cur_or_model if "free" not in cur_or_model.lower() else "anthropic/claude-3.7-sonnet"),
                }
                k_name, m_var, d_model = k_map[menu_idx]
                now_on = toggle_single_provider(k_name, m_var, d_model)
                label = "OpenRouter" if "OPENROUTER" in k_name else ("Gemini" if "GEMINI" in k_name else (f"Custom 2 ({c2_name})" if "CUSTOM2" in k_name else "Custom 1/HF"))
                message = f"✓ {label}: {GREEN+'ENABLED'+RESET if now_on else RED+'DISABLED'+RESET}"
            else:
                aux_keys = {6: "GND_KEY", 7: "GEM_VOICE", 8: "IMG_VOICE"}
                aux_labels = {6: "Grounding (/gnd)", 7: "Voice Bridge", 8: "Vision OCR"}
                target_k = aux_keys[menu_idx]
                now_on = toggle_independent_key(target_k)
                message = f"✓ {aux_labels[menu_idx]}: {GREEN+'ENABLED'+RESET if now_on else RED+'DISABLED'+RESET}"
        elif key == "enter":
            if menu_idx == 0:
                is_on = toggle_env_api_keys()
                message = f"✓ Switched Connection: {GREEN+'ENABLED'+RESET if is_on else RED+'DISABLED'+RESET}"
            elif menu_idx == 2:
                provider_key = next((k for k in DEFAULTS["custom2_models"] if k in c2_url), None)
                preset_models = DEFAULTS["custom2_models"].get(provider_key, [custom2_curr]) if provider_key else [custom2_curr]
                c2_menu_items = list(dict.fromkeys(preset_models + ["deepseek-chat", "deepseek-reasoner"]))

                res = await run_interactive_menu(
                    f"Custom 2 ({c2_name})",
                    c2_menu_items,
                    custom2_curr,
                    "CUSTOM2_API_KEY" in active_keys,
                    ["🚫 Turn Off Custom 2", "✏️  [Edit Model Name]", "🔗 [Edit Endpoint URL]", "🔑 [Edit API Key]"]
                )

                if not res:
                    continue
                if res.startswith("🚫 Turn Off"):
                    isolate_active_key("")
                    message = "✓ Custom 2 disabled."
                elif res == "✏️  [Edit Model Name]":
                    if m_in := prompt_user_input(f"Enter model name for {c2_name} (current: {custom2_curr})"):
                        update_env_multiple({"CUSTOM2_MODEL": m_in})
                        isolate_active_key("CUSTOM2_API_KEY")
                        message = f"✓ Custom 2 Model set to: {m_in}"
                elif res == "🔗 [Edit Endpoint URL]":
                    if u_in := prompt_user_input("Enter OpenAI-compatible completions URL"):
                        update_env_multiple({"CUSTOM2_URL": u_in})
                        message = f"✓ Custom 2 URL updated to: {u_in}"
                elif res == "🔑 [Edit API Key]":
                    if k_in := prompt_user_input(f"Enter API Key for {c2_name}"):
                        update_env_multiple({"CUSTOM2_API_KEY": k_in})
                        isolate_active_key("CUSTOM2_API_KEY")
                        message = "✓ Custom 2 API key updated and activated."
                else:
                    isolate_active_key("CUSTOM2_API_KEY")
                    update_env_multiple({"CUSTOM2_MODEL": res})
                    message = f"✓ Custom 2 Model set: {res}"
            elif 1 <= menu_idx <= 5:
                cfg = {
                    1: ("Custom 1 / HuggingFace", custom_list, custom_curr, "CUSTOM_API_KEY", ["🚫 Turn Off Custom 1", "➕ [Add Endpoint / Space URL]", "🗑  [Delete Custom Space]"]),
                    3: ("Gemini", cache.get("gemini", DEFAULTS["gemini"]), env.get("GEMINI_MODEL", ""), "GEMINI_API_KEY", ["🚫 Turn Off Gemini"]),
                    4: ("OpenRouter Free", cache.get("free", DEFAULTS["free"]), env.get("OPENROUTER_MODEL", ""), "OPENROUTER_API_KEY", ["🚫 Turn Off OpenRouter"]),
                    5: ("OpenRouter Paid", cache.get("paid", DEFAULTS["paid"]), env.get("OPENROUTER_MODEL", ""), "OPENROUTER_API_KEY", ["🚫 Turn Off OpenRouter"]),
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
                        update_env_multiple({"CUSTOM_URL": sp["url"], "CUSTOM_MODEL": sp["model"]})
                    else:
                        target_var = "GEMINI_MODEL" if menu_idx == 3 else "OPENROUTER_MODEL"
                        update_env_multiple({target_var: res})
                    message = f"✓ Primary model set: {res}"
            elif 6 <= menu_idx <= 8:
                aux_cfg = {
                    6: ("Search Grounding (/gnd)", "GND_KEY", "GND_MODEL", gnd_curr, ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]),
                    7: ("Voice Transcription", "GEM_VOICE", "GEM_MODEL", voice_curr, ["gemini-3.5-flash-lite", "gemini-2.5-flash"]),
                    8: ("Vision OCR Multimodal", "IMG_VOICE", "IMG_MODEL", img_curr, ["gemini-3.5-flash-lite", "gemini-2.5-flash"]),
                }[menu_idx]
                a_title, a_key, a_mod_var, a_cur_m, a_presets = aux_cfg
                res = await run_interactive_menu(a_title, a_presets, a_cur_m, a_key in active_keys, [f"🚫 Turn Off {a_title}", "🔑 [Edit API Key]", "✏️  [Custom Model Name]"])
                if not res:
                    continue
                if res.startswith("🚫 Turn Off"):
                    toggle_independent_key(a_key)
                    message = f"✓ {a_title} disabled."
                elif res == "🔑 [Edit API Key]":
                    if k_in := prompt_user_input(f"Enter API Key for {a_title}"):
                        update_env_multiple({a_key: k_in})
                        message = f"✓ {a_key} saved and activated."
                elif res == "✏️  [Custom Model Name]":
                    if m_in := prompt_user_input(f"Enter model for {a_title} (current: {a_cur_m})"):
                        update_env_multiple({a_mod_var: m_in})
                        message = f"✓ {a_mod_var} updated: {m_in}"
                else:
                    update_env_multiple({a_mod_var: res})
                    if a_key not in active_keys:
                        toggle_independent_key(a_key)
                    message = f"✓ {a_title} model set: {res}"
            elif menu_idx == 9:
                message = f"{AMBER}↺ Querying live models...{RESET}"
                remote_data = await async_fetch_remote(env, spaces)
                cache.update(remote_data)
                save_json(CACHE_PATH, cache)
                custom_list = list(spaces.keys()) + [x for x in cache.get("custom", []) if x not in spaces]
                message = "✓ Synchronized endpoints live."
            elif menu_idx == 10:
                break

    cleanup_terminal()
    print("\033[1;32m✓ Local-AI configuration saved.\033[0m")


if __name__ == "__main__":
    asyncio.run(async_main())
