def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    """
    Divide two numbers.
    Raises ZeroDivisionError if divisor is zero.
    """
    try:
        result = a / b
    except ZeroDivisionError:
        raise ZeroDivisionError("Cannot divide by zero.")
    return result
