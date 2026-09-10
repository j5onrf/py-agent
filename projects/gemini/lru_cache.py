class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}
        self.order = []

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.order.remove(key)
        self.order.append(key)
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache[key] = value
            self.order.remove(key)
            self.order.append(key)
            return
        
        if len(self.cache) >= self.capacity:
            oldest = self.order.pop(0)
            del self.cache[oldest]
            
        self.cache[key] = value
        self.order.append(key)