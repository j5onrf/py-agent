#!/usr/bin/env python3
"""Dynamic Cloud Cascade Engine - Top-down .env provider API priority with automatic fallback."""

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


def get_active_configs(
    messages: list[dict[str, str]],
) -> list[tuple[str, dict[str, str], dict[str, Any], int]]:
    """Compiles all active cloud API configurations in top-down .env order for multi-provider fallback."""
    configs: list[tuple[str, dict[str, str], dict[str, Any], int]] = []
    if not os.path.exists(ENV_PATH):
        return configs

    # Read CUSTOM_URL directly from environment or .env file (default to official Hugging Face Router)
    custom_url = os.environ.get("CUSTOM_URL")
    if not custom_url:
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if (
                        (s := line.strip())
                        and not s.startswith("#")
                        and s.startswith("CUSTOM_URL=")
                    ):
                        custom_url = s.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except OSError:
            pass
    custom_url = custom_url or "https://router.huggingface.co/v1/chat/completions"

    url_map = {
        "CUSTOM_API_KEY": custom_url,
        "GEMINI_API_KEY": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "OPENROUTER_API_KEY": "https://openrouter.ai/api/v1/chat/completions",
    }

    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if (line_strip := line.strip()) and not line_strip.startswith("#"):
                    if match := RE_ENV_API_KEY.match(line_strip):
                        key_name, key_val = match.groups()
                        val_clean = key_val.strip()
                        if not val_clean or any(
                            k in val_clean.lower() for k in ("your", "here", "api-key")
                        ):
                            continue

                        provider = key_name.split("_")[0].lower()

                        if url := url_map.get(key_name):
                            fallback = FALLBACK_MODELS.get(provider, "openrouter/free")
                            model_var = (
                                "OPENROUTER_MODEL"
                                if provider == "openrouter"
                                else f"{provider.upper()}_MODEL"
                            )
                            body = {
                                "model": os.environ.get(model_var) or fallback,
                                "messages": messages,
                                "stream": True,
                            }
                            headers = {"Authorization": f"Bearer {val_clean}"}
                            timeout_val = 180 if provider in ("openrouter", "custom") else 45

                            if provider == "openrouter":
                                body["usage"] = {"include": True}
                                headers["HTTP-Referer"] = "https://github.com/j5onrf/py-agent"

                            # Append in top-down order to enable multi-cloud fallback
                            configs.append((url, headers, body, timeout_val))
    except (OSError, UnicodeDecodeError, KeyError, IndexError, ValueError):
        pass
    return configs
