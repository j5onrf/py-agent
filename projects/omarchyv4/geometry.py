import math


def circle_area(radius: float) -> float:
    """Calculate the area of a circle given its radius."""
    return round(math.pi * radius ** 2, 2)