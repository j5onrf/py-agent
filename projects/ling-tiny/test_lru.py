import unittest

from lru import LRUCache


class TestLRUCache(unittest.TestCase):
    def test_eviction(self):
        cache = LRUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        self.assertEqual(cache.get(1), 1)
        cache.put(3, 3)
        self.assertEqual(cache.get(2), -1)

    def test_update(self):
        cache = LRUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        cache.put(1, 1)
        self.assertEqual(cache.get(1), 1)

    def test_miss(self):
        cache = LRUCache(2)
        self.assertEqual(cache.get(1), -1)

    def test_size(self):
        cache = LRUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        self.assertEqual(cache.size(), 2)
        cache.put(3, 3)
        self.assertEqual(cache.size(), 2)
        self.assertEqual(cache.get(1), -1)
        self.assertEqual(cache.get(2), 2)
        self.assertEqual(cache.get(3), 3)

if __name__ == '__main__':
    unittest.main()