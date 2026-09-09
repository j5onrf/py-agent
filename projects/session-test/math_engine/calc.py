def compute_fee(amount: float, *, rate: float = 0.05) -> float:
    """Keyword-only rate parameter."""
    return round(amount * rate, 2)
