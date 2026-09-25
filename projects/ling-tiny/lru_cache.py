from collections import OrderedDict


class LRUCache:
    """O(1) LRU Cache with get(key) and put(key, value) methods."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache = OrderedDict()

    def get(self, key):
        """Return value for key if present, else -1. Moves key to end (most recently used)."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return -1

    def put(self, key, value):
        """Insert or update key-value pair. Evicts least recently used item if capacity is exceeded."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)  # Evict oldest (least recently used)
        self._cache[key] = value