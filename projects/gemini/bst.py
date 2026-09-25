class Node:
    """A single node in the binary search tree."""

    __slots__ = ("key", "left", "right")

    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None

    def __repr__(self):
        return f"Node({self.key!r})"


class BST:
    """Binary search tree: every left child is < key, every right child is >= key."""

    def __init__(self):
        self.root = None
        self.size = 0

    def insert(self, key):
        """Insert a key. Returns the created Node. O(h) time."""
        if self.root is None:
            self.root = Node(key)
            self.size += 1
            return self.root

        current = self.root
        while True:
            if key < current.key:
                if current.left is None:
                    new_node = Node(key)
                    current.left = new_node
                    break
                current = current.left
            else:
                if current.right is None:
                    new_node = Node(key)
                    current.right = new_node
                    break
                current = current.right

        self.size += 1
        return new_node

    def search(self, key):
        """Return the Node with key, or None. O(h) time."""
        current = self.root
        while current is not None:
            if key == current.key:
                return current
            current = current.left if key < current.key else current.right
        return None

    def contains(self, key):
        return self.search(key) is not None

    def inorder(self):
        """Yield keys in sorted order (iterative)."""
        stack, current = [], self.root
        while stack or current is not None:
            while current is not None:
                stack.append(current)
                current = current.left
            current = stack.pop()
            yield current.key
            current = current.right
