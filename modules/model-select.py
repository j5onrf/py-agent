#!/usr/bin/env python3
"""Fully Dynamic TUI Model Selector driven by OpenRouter Rankings"""

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

ENV_PATH, CACHE_PATH = os.path.expanduser("~/.config/py-agent/.env"), os.path.expanduser("~/.config/py-agent/.openrouter_cache_v2.json")

ORIGINAL_TERMIOS = termios.tcgetattr(sys.stdin.fileno()) if sys.stdin.isatty() else None


def cleanup_terminal():
    if ORIGINAL_TERMIOS:
        try: termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, ORIGINAL_TERMIOS)
        except (termios.error, OSError): pass
    sys.stdout.write("\x1b[H\x1b[2J\033[?25h\033[0m")
    sys.stdout.flush()


atexit.register(cleanup_terminal)

GEMINI_CURATED = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.5-pro"]
OPENAI_CURATED = ["gpt-5.5", "gpt-5", "gpt-4.5", "o3", "o3-mini", "gpt-4o", "gpt-4o-mini"]
CLAUDE_CURATED = ["claude-3-7-sonnet", "claude-opus-5", "claude-fable-5", "claude-sonnet-5", "claude-opus-4-8", "claude-opus-4-7"]
GROK_CURATED = ["grok-4.5", "grok-4", "grok-3", "grok-2"]
HF_ENDPOINT_MAP = {
    "Qwen/Qwen3.8-27B": "https://g9hnto0u7lvbu837.us-east-2.aws.endpoints.huggingface.cloud/v1/chat/completions",
    "deepseek-ai/DeepSeek-V4-Flash-0731": "https://q5dh1rfszfym23hj.us-east-2.aws.endpoints.huggingface.cloud/v1/chat/completions",
    "Qwen/Qwen2.5-Coder-32B-Instruct": "https://router.huggingface.co/hf-inference/v1/chat/completions",
    "meta-llama/Llama-3.3-70B-Instruct": "https://router.huggingface.co/hf-inference/v1/chat/completions",
    "deepseek-ai/DeepSeek-R1": "https://router.huggingface.co/hf-inference/v1/chat/completions"
}
CUSTOM_CURATED = list(HF_ENDPOINT_MAP.keys())
OR_FREE_DEFAULTS = ["openrouter/free", "nvidia/nemotron-3-ultra:free", "poolside/laguna-m.1:free", "tencent/hy3:free", "google/gemma-4-26b-a4b:free", "meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat:free", "microsoft/phi-4:free", "mistralai/mistral-nemo:free"]
OR_PAID_DEFAULTS = ["deepseek/deepseek-v4-flash", "anthropic/claude-3.7-sonnet", "google/gemini-3.7-flash", "xiaomi/mimo-v2.5", "minimax/minimax-m3", "tencent/hy3", "z-ai/glm-5.2", "deepseek/deepseek-v4-pro", "anthropic/claude-opus-4.8", "openai/gpt-5.5", "openai/gpt-4o-mini"]


def classify_openrouter_models(raw_data):
    if not isinstance(raw_data, list): return OR_FREE_DEFAULTS, OR_PAID_DEFAULTS, GEMINI_CURATED, CLAUDE_CURATED, OPENAI_CURATED, GROK_CURATED
    free_c, paid_c, gemini_c, openai_c, claude_c, grok_c = [], [], [], [], [], []

    for item in raw_data:
        if not (m_id := item.get("id", "")): continue
        did = m_id.split("/", 1)[1].split(":")[0] if "/" in m_id else m_id
        if m_id.startswith("google/gemini") and did not in gemini_c: gemini_c.append(did)
        elif m_id.startswith("openai/") and did not in openai_c: openai_c.append(did)
        elif m_id.startswith("anthropic/") and did not in claude_c: claude_c.append(did)
        elif m_id.startswith("x-ai/") and did not in grok_c: grok_c.append(did)

        if "google/gemini" in m_id.lower() or "google/gemini" in item.get("name", "").lower(): continue

        p = item.get("pricing", {})
        is_free = "free" in m_id.lower() or (p and float(p.get("prompt", 0)) == 0 and float(p.get("completion", 0)) == 0)
        target = free_c if is_free else paid_c
        if m_id not in target: target.append(m_id)

    free_c = ["openrouter/free"] + [x for x in (free_c or OR_FREE_DEFAULTS) if x != "openrouter/free"]
    return free_c, paid_c or OR_PAID_DEFAULTS, gemini_c or GEMINI_CURATED, claude_c or CLAUDE_CURATED, openai_c or OPENAI_CURATED, grok_c or GROK_CURATED


def ensure_env_exists():
    """Auto-creates ~/.config/py-agent/.env from .env.example or built-in template on startup."""
    if not os.path.exists(ENV_PATH):
        example_path = os.path.join(os.path.dirname(ENV_PATH), ".env.example")
        if os.path.exists(example_path):
            try:
                shutil.copyfile(example_path, ENV_PATH)
                return
            except OSError: pass
        try:
            os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(
                    "# Top-Down Priority (First Active Key is Used)\n\n"
                    "# GEMINI_API_KEY=\"AIzaSyYourGeminiKey\"\n"
                    "GEMINI_MODEL=\"gemini-3.7-flash\"\n\n"
                    "# OPENROUTER_API_KEY=\"sk-or-v1-YourOpenRouterKey\"\n"
                    "OPENROUTER_MODEL=\"openrouter/free\"\n\n"
                    "# OPENAI_API_KEY=\"your-openai-key\"\n"
                    "OPENAI_MODEL=\"gpt-5.5\"\n\n"
                    "# CLAUDE_API_KEY=\"your-claude-key\"\n"
                    "CLAUDE_MODEL=\"claude-fable-5\"\n\n"
                    "# XAI_API_KEY=\"xai-your-grok-key\"\n"
                    "XAI_MODEL=\"grok-4.6\"\n\n"
                    "AI_MAX_TOKENS=\"8192\"\n"
                )
        except OSError: pass


def load_env_vars():
    ensure_env_exists()
    v = {
        "GEMINI_API_KEY": "", "OPENROUTER_API_KEY": "", "CLAUDE_API_KEY": "",
        "OPENAI_API_KEY": "", "XAI_API_KEY": "", "CUSTOM_API_KEY": "",
        "GEMINI_MODEL": "gemini-3.7-flash", "OPENROUTER_MODEL": "openrouter/free",
        "CLAUDE_MODEL": "claude-fable-5", "OPENAI_MODEL": "gpt-5.5",
        "XAI_MODEL": "grok-4.6", "CUSTOM_MODEL": "default"
    }
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for l in f:
                    if m := re.match(r"^#?\s*([A-Z0-9_]+)\s*=\s*\"?([^\"]*)\"?$", l.strip()):
                        k, val = m.groups()
                        if not l.strip().startswith("#") or not v.get(k): v[k] = val
        except (OSError, UnicodeDecodeError): pass
    return v


def get_active_key_set() -> set[str]:
    """Single-pass reader returning all active non-placeholder API key names."""
    active = set()
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for l in f:
                    if (s := l.strip()) and not s.startswith("#") and "=" in s:
                        k, v = s.split("=", 1)
                        val = v.strip().strip('"').strip("'")
                        if val and not any(sub in val.lower() for sub in ("your", "here", "api-key")):
                            active.add(k.strip())
        except (OSError, UnicodeDecodeError): pass
    return active


def update_env(key, value):
    if not os.path.exists(ENV_PATH): return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f: lines = f.readlines()
        updated = False
        for i, l in enumerate(lines):
            if re.match(rf"^#?\s*{key}\s*=\s*.*$", l):
                lines[i] = f"{'#' if l.strip().startswith('#') else ''}{key}=\"{value}\"\n"
                updated = True
                break
        if not updated: lines.append(f'{key}="{value}"\n')
        with open(ENV_PATH, "w", encoding="utf-8") as f: f.writelines(lines)
    except OSError: pass


def set_key_commented_state(key, should_comment):
    if not os.path.exists(ENV_PATH): return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f: lines = f.readlines()
        updated = False
        for i, l in enumerate(lines):
            if f"{key}=" in l.strip() or f"{key} =" in l.strip():
                lines[i] = f"{'#' if should_comment else ''}{l.strip().lstrip('#').strip()}\n"
                updated = True
                break
        if not updated and not should_comment:
            pm = {
                "GEMINI_API_KEY": "AIzaSyYourFullGeminiApiKeyHere",
                "OPENROUTER_API_KEY": "sk-or-v1-YourFullOpenRouterKeyHere",
                "CLAUDE_API_KEY": "your-claude-api-key-here",
                "OPENAI_API_KEY": "your-openai-api-key-here",
                "XAI_API_KEY": "xai-your-grok-api-key-here",
                "CUSTOM_API_KEY": "free"
            }
            lines.append(f'{key}="{pm.get(key, "your-key-here")}"\n')
        with open(ENV_PATH, "w", encoding="utf-8") as f: f.writelines(lines)
    except OSError: pass


def toggle_env_api_keys():
    if not os.path.exists(ENV_PATH): return False
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f: lines = f.readlines()
        t_keys = {"GEMINI_API_KEY", "OPENROUTER_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "CUSTOM_API_KEY"}
        is_commented = any(l.strip().startswith("#") for l in lines if any(k in l for k in t_keys))
        lines = [f"{'#' if not is_commented else ''}{l.strip().lstrip('#').strip()}\n" if any(k in l for k in t_keys) else l for l in lines]
        with open(ENV_PATH, "w", encoding="utf-8") as f: f.writelines(lines)
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "AI Environment Toggle", f"Switched to {'Cloud Mode (APIs Enabled)' if is_commented else 'Local / Offline Mode (APIs Disabled)'}", "-t", "2000"], check=False)
        return is_commented
    except (OSError, subprocess.SubprocessError): return False


def load_cached_lists():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                return (
                    d.get("free", OR_FREE_DEFAULTS), d.get("paid", OR_PAID_DEFAULTS),
                    d.get("gemini", GEMINI_CURATED), d.get("claude", CLAUDE_CURATED),
                    d.get("openai", OPENAI_CURATED), d.get("grok", GROK_CURATED),
                    d.get("custom", CUSTOM_CURATED)
                )
        except (OSError, json.JSONDecodeError): pass
    return OR_FREE_DEFAULTS, OR_PAID_DEFAULTS, GEMINI_CURATED, CLAUDE_CURATED, OPENAI_CURATED, GROK_CURATED, CUSTOM_CURATED


def save_cached_lists(free_l, paid_l, gemini_l, claude_l, openai_l, grok_l, custom_l=CUSTOM_CURATED):
    try:
        tmp = f"{CACHE_PATH}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"free": free_l, "paid": paid_l, "gemini": gemini_l, "claude": claude_l, "openai": openai_l, "grok": grok_l, "custom": custom_l}, f, indent=2)
        os.replace(tmp, CACHE_PATH)
    except OSError:
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except OSError: pass


async def async_fetch_openrouter_models(api_key):
    def _fetch():
        try:
            req = urlreq.Request("https://openrouter.ai/api/v1/models?sort=top-weekly", headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
            with urlreq.urlopen(req, timeout=8) as res:
                return json.loads(res.read().decode("utf-8")).get("data", []) if res.status == 200 else None
        except (urlreq.URLError, TimeoutError, json.JSONDecodeError, OSError): return None
    return await asyncio.to_thread(_fetch)


async def async_fetch_hf_spaces():
    def _fetch():
        discovered = dict(HF_ENDPOINT_MAP)
        try:
            req = urlreq.Request("https://huggingface.co/api/spaces?search=free-endpoint&limit=15", headers={"User-Agent": "local-ai"})
            with urlreq.urlopen(req, timeout=5) as res:
                if res.status == 200:
                    for sp in json.loads(res.read().decode("utf-8")):
                        sp_id = sp.get("id", "")
                        if sp_id:
                            clean_id = sp_id.split("/")[-1].replace("-free-endpoint", "")
                            # Only add if not already covered by curated endpoints
                            if not any(clean_id.lower() in k.lower() for k in discovered):
                                sub = sp_id.replace("/", "-").replace(".", "-").replace("_", "-").lower()
                                discovered[sp_id] = f"https://{sub}.hf.space/v1/chat/completions"
        except Exception: pass
        return discovered
    return await asyncio.to_thread(_fetch)


async def async_get_key():
    fd = sys.stdin.fileno()
    def _read():
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            if not (ch_bytes := os.read(fd, 1)): return None
            ch = ch_bytes.decode('utf-8', errors='ignore')
            if ch == '\x1b':
                if select.select([fd], [], [], 0.05)[0]:
                    seq = os.read(fd, 2).decode('utf-8', errors='ignore')
                    return {'[A': 'up', 'OA': 'up', '[B': 'down', 'OB': 'down', '[C': 'right', 'OC': 'right', '[D': 'left', 'OD': 'left'}.get(seq, 'esc')
                return 'esc'
            elif ch in ('\r', '\n'): return 'enter'
            elif ch in ('\x7f', '\x08'): return 'backspace'
            elif ch.lower() == 'q': return 'q'
            return ch
        except (OSError, termios.error): return None
        finally:
            try: termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except (termios.error, OSError): pass
    return await asyncio.to_thread(_read)


def draw_main_menu(selected, gemini_curr, claude_curr, openai_curr, grok_curr, or_curr, custom_curr, active_keys: set[str], message=""):
    sys.stdout.write("\x1b[H\x1b[2J")
    amber, green, red, reset, bold, dim = "\033[38;2;230;120;60m", "\033[1;32m", "\033[1;31m", "\033[0m", "\033[1m", "\033[90m"

    gemini_act = "GEMINI_API_KEY" in active_keys
    or_act = "OPENROUTER_API_KEY" in active_keys
    claude_act = "CLAUDE_API_KEY" in active_keys
    openai_act = "OPENAI_API_KEY" in active_keys
    grok_act = "XAI_API_KEY" in active_keys
    custom_act = "CUSTOM_API_KEY" in active_keys

    status_text = f"{green}[ ENABLED ]{reset}" if any([gemini_act, or_act, claude_act, openai_act, grok_act, custom_act]) else f"{red}[ DISABLED ]{reset}"
    fmt_disp = lambda curr, act: f"{green}{curr}{reset}" if act else f"{red}DISABLED (grayed out){reset}"
    is_or_free = "free" in or_curr.lower()

    sys.stdout.write(f"\n   {bold}  LOCAL-AI CONFIGURATION{reset}\n   {dim}────────────────────────────────────────────────────────────{reset}\n\n")

    options = [
        f"🔌  Cloud Connection      {status_text}",
        f"♊  Google Gemini          {fmt_disp(gemini_curr, gemini_act)}\n       {dim}Select from curated, lightweight Google endpoints{reset}",
        f"🍎  OpenAI Subscription    {fmt_disp(openai_curr, openai_act)}\n       {dim}Select from direct, high-performance OpenAI engines{reset}",
        f"☕  Anthropic Claude       {fmt_disp(claude_curr, claude_act)}\n       {dim}Select from direct, industry-leading Claude models{reset}",
        f"🚀  x.AI Grok              {fmt_disp(grok_curr, grok_act)}\n       {dim}Select from direct, ultra-high-speed Grok engines{reset}",
        f"🤗  Custom / HuggingFace   {fmt_disp(custom_curr, custom_act)}\n       {dim}Select from custom endpoints, Hugging Face spaces, or vLLM{reset}",
        f"🌐  OpenRouter Free       {f'{green}{or_curr}{reset}' if (or_act and is_or_free) else f'{dim}None selected{reset}'}\n       {dim}Select from the top 20 most popular free models{reset}",
        f"🌐  OpenRouter Paid       {f'{green}{or_curr}{reset}' if (or_act and not is_or_free) else f'{dim}None selected{reset}'}\n       {dim}Select from the top 20 industry leading paid engines{reset}",
        f"↺  Refresh API Lists      {dim}Query OpenRouter for current model rankings{reset}",
        "✕  Save & Close"
    ]

    for i, opt in enumerate(options):
        sys.stdout.write(f"{f'   {amber}❯{reset}  {bold}' if i == selected else '      '}{opt}{reset}\n{'\n' if i in (1, 2, 3, 4, 5, 6, 7) else ''}")

    sys.stdout.write(f"\n   {dim}────────────────────────────────────────────────────────────{reset}\n   {message or f'{dim}Use ▲/▼ Arrows to navigate, Enter to choose, Q to exit.{reset}'}\n")
    sys.stdout.flush()


async def run_selector(title, full_models_list, current, key_name, is_active):
    state = {"showing_all": False, "search_query": ""}
    def get_opts():
        filt = full_models_list if not state["search_query"] else [m for m in full_models_list if state["search_query"].lower() in m.lower()]
        return [f"🚫 Turn Off {title}"] + (filt if (state["showing_all"] or state["search_query"]) else filt[:20])

    opts = get_opts()
    selected = opts.index(current) if (is_active and current in opts) else 0
    amber, green, red, reset, bold, dim, max_v = "\033[38;2;230;120;60m", "\033[1;32m", "\033[1;31m", "\033[0m", "\033[1m", "\033[90m", 14

    while True:
        sys.stdout.write("\x1b[H\x1b[2J")
        sys.stdout.write(f"\n   {bold}  SELECT {title.upper()}:{reset}\n   {dim}────────────────────────────────────────────────────────────{reset}\n\n")
        if state["search_query"]: sys.stdout.write(f"   🔍  Filter: {green}{state['search_query']}{amber}_{reset}\n\n")

        start = max(0, min(selected - max_v // 2, len(opts) - max_v))
        end = min(len(opts), start + max_v)

        for i in range(start, end):
            opt = opts[i]
            bullet = f"{amber}❯{reset} " if i == selected else "  "
            line = f"{bullet}{red}{opt} {dim}(disabled){reset}" if (i == 0 and not is_active) else f"{bullet}{green}{opt} {dim}(active){reset}" if (opt == current and is_active) else f"{bullet}{opt}"
            sys.stdout.write(f"     {bold if i == selected else ''}{line}{reset}\n")

        m_above, m_below = start > 0, end < len(opts)
        ind = " ▲ ▼ " if (m_above and m_below) else " ▼ more below " if m_below else " ▲ more above " if m_above else ""
        sys.stdout.write(f"\n{f'   {dim}' + '─'*25 + amber + ind + dim + '─'*25 + reset if ind else f'   {dim}────────────────────────────────────────────────────────────{reset}'}\n")

        hint = f"Found {len(opts) - 1} matches. Backspace to edit, Esc to clear." if state["search_query"] else f"Showing Top 20. Press ► (Right Arrow) for all {len(full_models_list)} models." if not state["showing_all"] else f"Showing All {len(full_models_list)} models. Press ◄ (Left Arrow) for Top 20."
        sys.stdout.write(f"   {dim}{hint}{reset}\n   {dim}Press Enter to apply, or type characters to filter instantly.{reset}\n")
        sys.stdout.flush()

        key = await async_get_key()
        if key == 'up': selected = (selected - 1) % len(opts)
        elif key == 'down': selected = (selected + 1) % len(opts)
        elif key == 'backspace':
            if state["search_query"]: state["search_query"] = state["search_query"][:-1]; selected = 0; opts = get_opts()
        elif key == 'esc':
            if state["search_query"]: state["search_query"] = ""; selected = 0; opts = get_opts()
            else: return None
        elif key == 'right' and not state["showing_all"]:
            state["showing_all"] = True; m = opts[selected]; opts = get_opts(); selected = opts.index(m) if m in opts else 0
        elif key == 'left' and state["showing_all"]:
            state["showing_all"] = False; m = opts[selected]; opts = get_opts(); selected = opts.index(m) if m in opts else 0
        elif key == 'enter': return "DISABLE" if selected == 0 else opts[selected]
        elif isinstance(key, str) and len(key) == 1 and (key.isalnum() or key in ('-', ':', '/', '.', '_')):
            state["search_query"] += key; selected = 0; opts = get_opts()


async def async_main():
    sys.stdout.write("\033[?25l"); sys.stdout.flush()
    env = load_env_vars()
    gemini_curr = env["GEMINI_MODEL"]
    openai_curr = env.get("OPENAI_MODEL", "gpt-5.5")
    claude_curr = env.get("CLAUDE_MODEL", "claude-fable-5")
    grok_curr = env.get("XAI_MODEL", "grok-4.5")
    custom_curr = env.get("CUSTOM_MODEL", "default")
    or_curr = env["OPENROUTER_MODEL"]
    
    or_free_list, or_paid_list, gemini_list, claude_list, openai_list, grok_list, custom_list = load_cached_lists()

    if "openrouter/free" in or_free_list: or_free_list.remove("openrouter/free")
    or_free_list = ["openrouter/free"] + or_free_list

    selected_idx, message, total_options = 0, "", 10

    try:
        while True:
            active_keys = get_active_key_set()
            draw_main_menu(selected_idx, gemini_curr, claude_curr, openai_curr, grok_curr, or_curr, custom_curr, active_keys, message)
            message = ""
            key = await async_get_key()

            if key == 'up': selected_idx = (selected_idx - 1) % total_options
            elif key == 'down': selected_idx = (selected_idx + 1) % total_options
            elif key == 'enter':
                if selected_idx == 0:
                    is_now_enabled = toggle_env_api_keys()
                    env = load_env_vars()
                    message = f"✓ Switched Cloud Connection to: {'\033[1;32mENABLED\033[0m' if is_now_enabled else '\033[1;31mDISABLED\033[0m'}"
                elif selected_idx in (1, 2, 3, 4, 5, 6, 7):
                    target_map = {
                        1: ("Gemini", gemini_list, gemini_curr, "GEMINI_API_KEY", "GEMINI_MODEL"),
                        2: ("OpenAI", openai_list, openai_curr, "OPENAI_API_KEY", "OPENAI_MODEL"),
                        3: ("Claude", claude_list, claude_curr, "CLAUDE_API_KEY", "CLAUDE_MODEL"),
                        4: ("Grok", grok_list, grok_curr, "XAI_API_KEY", "XAI_MODEL"),
                        5: ("Custom / HuggingFace", custom_list, custom_curr, "CUSTOM_API_KEY", "CUSTOM_MODEL"),
                        6: ("OpenRouter Free", or_free_list, or_curr, "OPENROUTER_API_KEY", "OPENROUTER_MODEL"),
                        7: ("OpenRouter Paid", or_paid_list, or_curr, "OPENROUTER_API_KEY", "OPENROUTER_MODEL"),
                    }
                    title, lst, curr, k_name, m_name = target_map[selected_idx]
                    is_active = k_name in active_keys
                    res = await run_selector(title, lst, curr, k_name, is_active)
                    if res == "DISABLE":
                        set_key_commented_state(k_name, True)
                        message = f"✓ {title} disabled."
                    elif res:
                        set_key_commented_state(k_name, False)
                        update_env(m_name, res)
                        if selected_idx == 5:
                            custom_curr = res
                            hf_url = HF_ENDPOINT_MAP.get(res, "https://g9hnto0u7lvbu837.us-east-2.aws.endpoints.huggingface.cloud/v1/chat/completions")
                            update_env("CUSTOM_URL", hf_url)
                            update_env("CUSTOM_API_KEY", "not-needed")
                        elif selected_idx == 1: gemini_curr = res
                        elif selected_idx == 2: openai_curr = res
                        elif selected_idx == 3: claude_curr = res
                        elif selected_idx == 4: grok_curr = res
                        else: or_curr = res
                        message = f"✓ Saved {m_name}={res} and auto-configured endpoint."
                elif selected_idx == 8:
                    message = "\033[1;33m↺ Querying OpenRouter & HuggingFace for live endpoints...\033[0m"
                    draw_main_menu(selected_idx, gemini_curr, claude_curr, openai_curr, grok_curr, or_curr, custom_curr, active_keys, message)
                    raw_or = await async_fetch_openrouter_models(env["OPENROUTER_API_KEY"])
                    raw_hf = await async_fetch_hf_spaces()
                    if raw_hf:
                        HF_ENDPOINT_MAP.update(raw_hf)
                        custom_list = list(HF_ENDPOINT_MAP.keys())
                    if raw_or:
                        or_free_list, or_paid_list, gemini_list, claude_list, openai_list, grok_list = classify_openrouter_models(raw_or)
                    save_cached_lists(or_free_list, or_paid_list, gemini_list, claude_list, openai_list, grok_list, custom_list)
                    message = "✓ Synchronized live OpenRouter rankings and HuggingFace endpoints."
                elif selected_idx == 9:
                    cleanup_terminal()
                    print("\033[1;32m✓ Local-AI configuration saved.\033[0m")
                    return
            elif key in ('q', 'esc'):
                cleanup_terminal()
                return
    finally: cleanup_terminal()

if __name__ == "__main__":
    asyncio.run(async_main())
