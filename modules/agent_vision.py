#!/usr/bin/env python3
"""Vision Module - Multimodal Pre-processing, OCR & Vision Bridge [Production Ready]

Handles Gemini Flash Lite vision pre-processing for text-only local models,
featuring strict SSRF defense, 15 MB payload bounds, and workspace containment.
"""

import base64
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.request as urlreq
from typing import Any

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
MAX_IMAGE_BYTES: int = 15 * 1024 * 1024  # 15 MB cap

RE_ATTACHED_IMAGE = re.compile(
    r'\[(?:Attached\s+)?(?:image|file)[^\]]*?saved\s+at:\s*([^\]]+)\]',
    re.IGNORECASE
)

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}

FORBIDDEN_SENSITIVE_SUBDIRS = (
    ".ssh",
    ".gnupg",
    ".aws",
    ".config/py-agent",
)


def _get_img_config() -> tuple[str, str]:
    """Retrieves vision model and API key from environment or .env files."""
    k = (
        os.environ.get("IMG_VOICE", "")
        or os.environ.get("IMG_KEY", "")
        or os.environ.get("GEM_VOICE", "")
        or os.environ.get("GEMINI_API_KEY", "")
    )
    m = (
        os.environ.get("IMG_MODEL", "")
        or os.environ.get("GEM_MODEL", "")
        or "gemini-3.5-flash-lite"
    )
    if not k:
        for p in (os.path.join(CFG_DIR, ".env"), os.path.expanduser("~/.config/local-ai/.env"), ".env"):
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for l in f:
                            if (s := l.strip()) and not s.startswith("#"):
                                if (s.startswith("IMG_VOICE=") or s.startswith("IMG_KEY=") or s.startswith("GEM_VOICE=")) and not k:
                                    k = s.split("=", 1)[1].strip().strip("'\"")
                                if (s.startswith("IMG_MODEL=") or s.startswith("GEM_MODEL=")) and not os.environ.get("IMG_MODEL"):
                                    m = s.split("=", 1)[1].strip().strip("'\"")
                except Exception:
                    pass
    return k.strip(), m.strip() or "gemini-3.5-flash-lite"


def _is_safe_url(url: str) -> bool:
    """SSRF guard: blocks internal/private IP ranges and dangerous URL schemes."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname or hostname.lower() in ("localhost", "localhost.localdomain"):
            return False

        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        return True
    except Exception:
        return False


def describe_image_gemini(target: Any) -> str:
    """Pre-processes images via Gemini Flash Lite vision for text-only local models."""
    key, model = _get_img_config()
    if not key:
        return "[Error: IMG_VOICE not configured in .env for vision]"
    mime, b64 = "image/png", ""
    try:
        if isinstance(target, dict):
            src = target.get("source", {}) if isinstance(target.get("source"), dict) else {}
            b64 = src.get("data") or target.get("data") or target.get("blob") or ""
            mime = src.get("media_type") or target.get("mimeType") or target.get("mime_type") or "image/png"
            if not b64 and (u := (target.get("image_url", {}).get("url") if isinstance(target.get("image_url"), dict) else target.get("image_url")) or target.get("url") or target.get("path") or src.get("url")):
                return describe_image_gemini(str(u))
        elif isinstance(target, str):
            c = target.strip().strip("'\"").strip()
            if c.startswith("data:image/"):
                h, b64 = c.split(",", 1)
                mime = h.split(";")[0].replace("data:", "")
            elif c.startswith(("http://", "https://")):
                url = c.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/") if ("github.com/" in c and "/blob/" in c) else c
                if not _is_safe_url(url):
                    return "[Error: URL access denied by SSRF security policy]"

                req = urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36", "Accept": "image/*,*/*;q=0.8"})
                with urlreq.urlopen(req, timeout=15) as resp:
                    raw_data = resp.read(MAX_IMAGE_BYTES + 1)
                    if len(raw_data) > MAX_IMAGE_BYTES:
                        return f"[Error: Image exceeds maximum allowed size ({MAX_IMAGE_BYTES // (1024 * 1024)} MB)]"
                    b64 = base64.b64encode(raw_data).decode("utf-8")
                    ct = resp.headers.get_content_type()
                    mime = ct if ct and ct.startswith("image/") else ("image/jpeg" if any(x in url.lower() for x in (".jpg", ".jpeg")) else ("image/webp" if ".webp" in url.lower() else "image/png"))
            else:
                p = urllib.parse.unquote(c[7:]) if c.startswith("file://") else c
                ws = os.path.realpath(os.environ.get("AI_WORKSPACE_PATH", os.getcwd()))
                home = os.path.realpath(os.path.expanduser("~"))

                cand_paths = []
                if not os.path.isabs(p) and not p.startswith("~"):
                    cand_paths.append(os.path.realpath(os.path.join(ws, p)))
                else:
                    cand_paths.append(os.path.realpath(os.path.expanduser(p)))

                rf = None
                for cand in cand_paths:
                    if os.path.isfile(cand):
                        # Strict workspace containment check: must reside inside active workspace
                        if cand == ws or cand.startswith(ws + os.sep):
                            is_sensitive = any(
                                cand == os.path.join(home, sub) or cand.startswith(os.path.join(home, sub) + os.sep)
                                for sub in FORBIDDEN_SENSITIVE_SUBDIRS
                            )
                            if not is_sensitive:
                                rf = cand
                                break

                if rf:
                    ext = os.path.splitext(rf)[1].lower()
                    if ext not in ALLOWED_IMAGE_EXTENSIONS:
                        return f"[Error: Unsupported image file format '{ext}']"
                    if os.path.getsize(rf) > MAX_IMAGE_BYTES:
                        return f"[Error: File exceeds maximum allowed size ({MAX_IMAGE_BYTES // (1024 * 1024)} MB)]"
                    mime = ALLOWED_IMAGE_EXTENSIONS[ext]
                    with open(rf, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                elif len(c) > 100 and not any(c.startswith(x) for x in ("/", "~", ".", "file:")):
                    b64 = c
                else:
                    return f"[Error: Image file access denied or not found at '{target}']"
    except Exception as e:
        return f"[Error loading image: {e}]"

    if not b64:
        return "[Error: Empty image payload]"

    sys_p = (
        "Provide a comprehensive, accurate, and objective description of the image. "
        "Transcribe any visible text, code, terminal logs, error messages, line numbers, "
        "or data verbatim with exact formatting. Describe all visual subjects, objects, "
        "UI layouts, diagrams, charts, colors, and scenes in clear, precise detail."
    )
    payload = {
        "contents": [{"parts": [{"text": sys_p}, {"inline_data": {"mime_type": mime, "data": b64}}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }
    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urlreq.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST"
        )
        with urlreq.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if "text" in p).strip() or "[No visual elements detected]"
    except Exception as e:
        err_msg = str(e).replace(key, "[REDACTED]")
        return f"[Vision Exception: {err_msg}]"


def preprocess_multimodal_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Inspects messages for attached images and runs Gemini OCR/Vision pre-processing."""
    processed, (_, model) = [], _get_img_config()
    for msg in messages:
        c = msg.get("content")
        if isinstance(c, str):
            if paths := RE_ATTACHED_IMAGE.findall(c):
                va = [f"[Visual Analysis ({model})]:\n{describe_image_gemini(p.strip().strip('\'\"'))}" for p in paths]
                txt = RE_ATTACHED_IMAGE.sub("", c).strip()
                processed.append({**msg, "content": "\n\n".join(va + ([f"User Question: {txt}"] if txt else []))})
            else:
                processed.append(msg)
        elif isinstance(c, list):
            tp, va = [], []
            for it in c:
                if isinstance(it, str):
                    if paths := RE_ATTACHED_IMAGE.findall(it):
                        va.extend(f"[Visual Analysis ({model})]:\n{describe_image_gemini(p.strip().strip('\'\"'))}" for p in paths)
                        if clean := RE_ATTACHED_IMAGE.sub("", it).strip():
                            tp.append(clean)
                    else:
                        tp.append(it)
                elif isinstance(it, dict):
                    if it.get("type") == "text":
                        raw = it.get("text", "")
                        if paths := RE_ATTACHED_IMAGE.findall(raw):
                            va.extend(f"[Visual Analysis ({model})]:\n{describe_image_gemini(p.strip().strip('\'\"'))}" for p in paths)
                            if clean := RE_ATTACHED_IMAGE.sub("", raw).strip():
                                tp.append(clean)
                        elif raw:
                            tp.append(raw)
                    else:
                        res = describe_image_gemini(it)
                        if not res.startswith("[Error: Empty image"):
                            va.append(f"[Visual Analysis ({model})]:\n{res}")
            user_txt = "\n".join(t.strip() for t in tp if t.strip())
            processed.append({**msg, "content": "\n\n".join(va + ([f"User Question: {user_txt}"] if (user_txt and va) else ([user_txt] if user_txt else [])))})
        else:
            processed.append(msg)
    return processed
