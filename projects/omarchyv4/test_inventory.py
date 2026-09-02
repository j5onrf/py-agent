import unittest
from inventory import Inventory


class TestInventory(unittest.TestCase):
    def test_add_item(self):
        inv = Inventory()
        inv.add_item("apple", 5)
        self.assertEqual(inv.get_stock("apple"), 5)


if __name__ == "__main__":
    unittest.main()
