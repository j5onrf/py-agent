"""Simple inventory management module."""


class Inventory:
    def __init__(self):
        self.items: dict[str, int] = {}

    def add_item(self, name: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        self.items[name] = self.items.get(name, 0) + quantity

    def get_stock(self, name: str) -> int:
        return self.items.get(name, 0)
