def capitalize_words(s: str) -> str:
    return ' '.join(word.capitalize() for word in s.split())

def count_vowels(s: str) -> int:
    vowels = set('aeiou')
    return sum(1 for ch in s.lower() if ch in vowels)