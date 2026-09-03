def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculates discounted price. Discount percent is between 0 and 100."""
    if price < 0 or discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid price or discount")
    return price * (1 - discount_percent / 100.0)

def clamp(val: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(val, max_val))
