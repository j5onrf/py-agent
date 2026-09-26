#!/usr/bin/env python3
"""Dynamic Cloud Cascade Engine - Top-down .env provider API priority with infinite CUSTOM* support [Production Ready]"""

import os
import re
from typing import Any

ENV_PATH: str = os.path.expanduser("~/.config/py-agent/.env")

# Matches: KEY="val" or KEY='val' or KEY=val, with optional 'export ' prefix and trailing comments
RE_ENV_LINE: re.Pattern = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z0-9_]+)\s*=\s*(?:([\"'])(.*?)\2|([^#\s\r\n]+))(?:\s*#.*)?$"
)
RE_API_KEY_NAME: re.Pattern = re.compile(r"^[A-Z0-9_]+(?:_API)?_KEY$")

FALLBACK_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openrouter": "openrouter/free",
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o",
    "custom": "Qwen/Qwen3.8-27B",
}

PLACEHOLDER_PREFIXES = ("your-", "sk-your", "aizasyyour", "<your", "todo", "replace-me")
PLACEHOLDER_EXACT = {"your-api-key-here", "sk-your-key-here", "aizasyyourgeminiapikeyhere", "not-set"}


def _is_valid_key(val: str) -> bool:
    v = val.strip().strip("'\"")
    if not v:
        return False
    v_low = v.lower()
    if v_low == "not-needed":
        return True
    if v_low in PLACEHOLDER_EXACT or any(v_low.startswith(p) for p in PLACEHOLDER_PREFIXES):
        return False
    return len(v) >= 8


def get_active_configs(
    messages: list[dict[str, Any]],
) -> list[tuple[str, dict[str, str], dict[str, Any], int]]:
    """Compiles all active cloud API configurations in a single pass top-down scan."""
    configs: list[tuple[str, dict[str, str], dict[str, Any], int]] = []
    target_env = getattr(get_active_configs, "ENV_PATH", ENV_PATH)
    if not os.path.exists(target_env):
        return configs

    env_vars: dict[str, str] = {}
    ordered_keys: list[tuple[str, str]] = []

    # Single-pass read: parse all variables and preserve top-down priority ordering
    try:
        with open(target_env, "r", encoding="utf-8") as f:
            for line in f:
                line_clean = line.strip()
                if not line_clean or line_clean.startswith("#"):
                    continue

                if m := RE_ENV_LINE.match(line_clean):
                    k_str = m.group(1).strip()
                    # Quoted value is group 3; unquoted value is group 4
                    v_str = (m.group(3) if m.group(2) else m.group(4)) or ""
                    v_str = v_str.strip()

                    env_vars[k_str] = v_str

                    if RE_API_KEY_NAME.match(k_str) and _is_valid_key(v_str):
                        ordered_keys.append((k_str, v_str))
    except OSError:
        return configs

    # Resolve endpoints matching the exact top-down priority
    for key_name, val_clean in ordered_keys:
        # Isolate message list for each provider config to prevent cross-provider mutation
        isolated_messages = [dict(msg) for msg in messages]

        # 1. Custom Matcher: CUSTOM_API_KEY, CUSTOM2_KEY, CUSTOM_GROQ_API_KEY, etc.
        if m_custom := re.match(r"^(CUSTOM[0-9A-Z_]*?)(?:_API)?_KEY$", key_name):
            prefix = m_custom.group(1)
            url = (
                env_vars.get(f"{prefix}_URL")
                or os.environ.get(f"{prefix}_URL")
                or "https://router.huggingface.co/v1/chat/completions"
            )
            model = (
                env_vars.get(f"{prefix}_MODEL")
                or os.environ.get(f"{prefix}_MODEL")
                or FALLBACK_MODELS["custom"]
            )
            headers = {"Content-Type": "application/json"}
            if val_clean.lower() != "not-needed":
                headers["Authorization"] = f"Bearer {val_clean}"
            body = {"model": model, "messages": isolated_messages, "stream": True}
            configs.append((url, headers, body, 180))

        # 2. Google Gemini
        elif key_name in ("GEMINI_API_KEY", "GEMINI_KEY"):
            model = (
                env_vars.get("GEMINI_MODEL")
                or os.environ.get("GEMINI_MODEL")
                or FALLBACK_MODELS["gemini"]
            )
            url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            headers = {
                "Authorization": f"Bearer {val_clean}",
                "x-goog-api-key": val_clean,
                "Content-Type": "application/json",
            }
            body = {"model": model, "messages": isolated_messages, "stream": True}
            configs.append((url, headers, body, 45))

        # 3. OpenRouter
        elif key_name in ("OPENROUTER_API_KEY", "OPENROUTER_KEY"):
            model = (
                env_vars.get("OPENROUTER_MODEL")
                or os.environ.get("OPENROUTER_MODEL")
                or FALLBACK_MODELS["openrouter"]
            )
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {val_clean}",
                "HTTP-Referer": "https://github.com/j5onrf/py-agent",
                "Content-Type": "application/json",
            }
            body = {
                "model": model,
                "messages": isolated_messages,
                "stream": True,
                "usage": {"include": True},
            }
            configs.append((url, headers, body, 180))

        # 4. DeepSeek Direct
        elif key_name in ("DEEPSEEK_API_KEY", "DEEPSEEK_KEY"):
            model = (
                env_vars.get("DEEPSEEK_MODEL")
                or os.environ.get("DEEPSEEK_MODEL")
                or FALLBACK_MODELS["deepseek"]
            )
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {val_clean}",
                "Content-Type": "application/json",
            }
            body = {"model": model, "messages": isolated_messages, "stream": True}
            configs.append((url, headers, body, 180))

        # 5. OpenAI Direct
        elif key_name in ("OPENAI_API_KEY", "OPENAI_KEY"):
            model = (
                env_vars.get("OPENAI_MODEL")
                or os.environ.get("OPENAI_MODEL")
                or FALLBACK_MODELS["openai"]
            )
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {val_clean}",
                "Content-Type": "application/json",
            }
            body = {"model": model, "messages": isolated_messages, "stream": True}
            configs.append((url, headers, body, 120))

    return configs
