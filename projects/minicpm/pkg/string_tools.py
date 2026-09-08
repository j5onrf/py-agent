import re

def slugify(text: str) -> str:
    """Convert text to a lowercase hyphenated slug."""
    # FIX: collapse all whitespace runs into a single hyphen
    return re.sub(r"\s+", "-", text).lower()

def truncate(text: str, max_len: int = 10) -> str:
    """Truncate text to max_len with ellipsis."""
    return text[:max_len] + "..." if len(text) > max_len else text
