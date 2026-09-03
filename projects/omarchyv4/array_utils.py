def filter_even_numbers(numbers: list[int]) -> list[int]:
    return [n for n in numbers if n % 2 == 0]  # Bug: returning odd numbers
