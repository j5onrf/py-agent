def reverse_words(text):
    """Reverses the order of words in a given text string."""
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    words = text.split()
    return " ".join(reversed(words))

def count_vowels(text):
    """Counts the number of vowels (a, e, i, o, u, case-insensitive) in text."""
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    vowels = "aeiouAEIOU"
    return sum(1 for char in text if char in vowels)
