def add(a, b):
    """Return the sum of two numbers."""
    return a + b


def subtract(a, b):
    """Return the difference of two numbers."""
    return a - b


def multiply(a, b):
    """Return the product of two numbers."""
    return a * b


def divide(a, b):
    """Return the quotient of two numbers.

    Raises ValueError if b is zero.
    """
    if b == 0:
        raise ValueError("division by zero")
    return a / b


# Simple assert tests
assert add(2, 3) == 5, "add(2, 3) should be 5"
assert subtract(10, 4) == 6, "subtract(10, 4) should be 6"
assert add(-1, 1) == 0, "add(-1, 1) should be 0"
assert subtract(5, 5) == 0, "subtract(5, 5) should be 0"
assert multiply(3, 4) == 12, "multiply(3, 4) should be 12"
assert divide(8, 2) == 4.0, "divide(8, 2) should be 4.0"
try:
    divide(5, 0)
except ValueError:
    pass
else:
    raise AssertionError("divide(5, 0) should raise ValueError")
print("All tests passed!")