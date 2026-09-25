import unittest
from lru_cache import LRUCache


class TestLRUCache(unittest.TestCase):
    """Unit tests for LRUCache capacity eviction, update-in-place, and missing key handling."""

    # ---- Capacity eviction ----
    def test_capacity_eviction(self):
        """Evicts the least recently used item when capacity is exceeded."""
        cache = LRUCache(2)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")  # evicts key 1
        self.assertEqual(cache.get(1), -1)
        self.assertEqual(cache.get(2), "b")
        self.assertEqual(cache.get(3), "c")

    # ---- Update-in-place ----
    def test_update_in_place(self):
        """Updating an existing key should mark it as most recently used."""
        cache = LRUCache(3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(1, "updated")
        self.assertEqual(cache.get(1), "updated")
        self.assertEqual(cache.get(2), "b")

    # ---- Missing key handling ----
    def test_missing_key(self):
        """get on a missing key returns -1 without raising."""
        cache = LRUCache(2)
        cache.put(1, "a")
        self.assertEqual(cache.get(2), -1)
        self.assertEqual(cache.get(99), -1)

    # ---- Basic get/put ----
    def test_basic_get_put(self):
        """Simple get and put operations."""
        cache = LRUCache(3)
        cache.put(1, 10)
        cache.put(2, 20)
        self.assertEqual(cache.get(1), 10)
        self.assertEqual(cache.get(2), 20)

    # ---- Accessing a key moves it to the end ----
    def test_access_moves_to_end(self):
        """Getting a key should mark it as most recently used."""
        cache = LRUCache(2)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.get(1)  # makes 1 most recently used
        cache.put(3, "c")  # evicts key 2, keeps 1
        self.assertEqual(cache.get(1), "a")
        self.assertEqual(cache.get(2), -1)


if __name__ == "__main__":
    unittest.main()