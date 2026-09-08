#!/usr/bin/env python3
"""Dynamic Cloud Cascade Engine - Top-down .env provider API priority with infinite CUSTOM* support."""

import os
import re
from typing import Any

ENV_PATH: str = os.path.expanduser("~/.config/py-agent/.env")
RE_ENV_API_KEY: re.Pattern = re.compile(
    r"^([A-Z0-9_]+_API_KEY|[A-Z0-9_]+_KEY)\s*=\s*\"?([^\"]*)\"?$"
)

FALLBACK_MODELS = {
    "gemini": "gemini-3.8-flash",
    "openrouter": "openrouter/free",
    "custom": "Qwen/Qwen3.8-27B",
}


def _is_valid_key(val: str) -> bool:
    v = val.strip().strip("'\"")
    if not v:
        return False
    if v.lower() == "not-needed":
        return True
    return not any(sub in v.lower() for sub in ("your", "here", "api-key"))


def get_active_configs(
    messages: list[dict[str, Any]],
) -> list[tuple[str, dict[str, str], dict[str, Any], int]]:
    """Compiles all active cloud API configurations in top-down .env order supporting infinite CUSTOM* endpoints."""
    configs: list[tuple[str, dict[str, str], dict[str, Any], int]] = []
    if not os.path.exists(ENV_PATH):
        return configs

    # 1. Pre-parse all environment variables from .env to resolve paired URLs and models
    env_vars: dict[str, str] = {}
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    k, v = s.replace("export ", "", 1).split("=", 1)
                    env_vars[k.strip()] = v.split(" #")[0].strip().strip('"').strip("'")
    except OSError:
        pass

    # 2. Sequential top-down scan to preserve exact .env priority ordering
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line_strip = line.strip()
                if not line_strip or line_strip.startswith("#"):
                    continue

                if match := RE_ENV_API_KEY.match(line_strip):
                    key_name, key_val = match.groups()
                    val_clean = key_val.strip().strip('"').strip("'")
                    if not _is_valid_key(val_clean):
                        continue

                    # Dynamic Custom Matcher: CUSTOM, CUSTOM2, CUSTOM3, CUSTOM_GROQ, etc.
                    if m_custom := re.match(r"^(CUSTOM[0-9A-Z_]*?)_API_KEY$", key_name):
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
                        body = {"model": model, "messages": messages, "stream": True}
                        configs.append((url, headers, body, 180))

                    # Google Gemini
                    elif key_name == "GEMINI_API_KEY":
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
                        body = {"model": model, "messages": messages, "stream": True}
                        configs.append((url, headers, body, 45))

                    # OpenRouter
                    elif key_name == "OPENROUTER_API_KEY":
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
                            "messages": messages,
                            "stream": True,
                            "usage": {"include": True},
                        }
                        configs.append((url, headers, body, 180))

    except (OSError, UnicodeDecodeError, KeyError, IndexError, ValueError):
        pass

    return configs
