def to_title_case(text: str) -> str:
    return " ".join(word.capitalize() for word in text.split())

def clamp_length(text: str, max_len: int = 10) -> str:
    return text[:max_len]

def is_empty(text: str) -> bool:
    """Return True if the text is empty or only whitespace."""
    return not text.strip()