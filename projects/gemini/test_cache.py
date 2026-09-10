import unittest
from lru_cache import LRUCache

class TestLRUCache(unittest.TestCase):
    def test_capacity_eviction(self):
        cache = LRUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        self.assertEqual(cache.get(1), 1)
        cache.put(3, 3) # Should evict key 2
        self.assertEqual(cache.get(2), -1)
        self.assertEqual(cache.get(3), 3)

    def test_recency_ordering(self):
        cache = LRUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        # Access key 1 so it becomes most recently used
        self.assertEqual(cache.get(1), 1)
        # Put key 3, which should evict key 2 (since 1 was accessed and is now recent)
        cache.put(3, 3)
        self.assertEqual(cache.get(2), -1)
        self.assertEqual(cache.get(1), 1)
        self.assertEqual(cache.get(3), 3)

if __name__ == '__main__':
    unittest.main()