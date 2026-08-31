def add(a, b):
    """Return the sum of a and b."""
    return a + b


def subtract(a, b):
    """Return the difference of a and b."""
    return a - b


def multiply(a, b):
    """Return the product of a and b."""
    return a * b


def divide(a, b):
    """Return the quotient of a divided by b. Raises ZeroDivisionError if b is zero."""
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def power(a, b):
    """Return a raised to the power of b (a ** b)."""
    return a ** b


def modulo(a, b):
    """Return a modulo b (a % b). Raises ZeroDivisionError if b is 0."""
    if b == 0:
        raise ZeroDivisionError("Cannot modulo by zero")
    return a % b


def average(*args):
    """Return the arithmetic mean of given numbers.
    Raises ValueError("Cannot compute average of empty values") if no arguments are provided.
    """
    if len(args) == 0:
        raise ValueError("Cannot compute average of empty values")
    return sum(args) / len(args)


def median(numbers):
    """Return the median of a list of numbers (handling both even and odd length lists).
    Raises ValueError("Cannot compute median of empty list") if the list is empty.
    """
    if not numbers:
        raise ValueError("Cannot compute median of empty list")
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    mid = n // 2
    if n % 2 == 1:
        return sorted_nums[mid]
    else:
        return (sorted_nums[mid - 1] + sorted_nums[mid]) / 2
