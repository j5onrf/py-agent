def strip_prefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix):]  # Fixed: removed +1 offset
    return text
