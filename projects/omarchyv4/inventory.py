class Inventory:
    def __init__(self):
        self.items = []

    def is_empty(self) -> bool:
        return len(self.items) == 0