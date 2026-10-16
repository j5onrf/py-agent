def is_palindrome(text):
    """Check if a given string is a palindrome (case-sensitive)."""
    cleaned = text.lower()
    return cleaned == cleaned[::-1]
