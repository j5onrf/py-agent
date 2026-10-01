"""Binary Search Tree with insert and search methods."""


class Node:
    """A node in the binary search tree."""

    __slots__ = ("key", "left", "right")

    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None


class BinarySearchTree:
    """A simple binary search tree.

    Supports insert(key) and search(key) operations.
    """

    def __init__(self):
        self.root = None

    # ------------------------------------------------------------------ #
    # Insertion
    # ------------------------------------------------------------------ #

    def insert(self, key):
        """Insert *key* into the tree. Duplicates are ignored."""
        if self.root is None:
            self.root = Node(key)
            return

        self._insert_recursive(self.root, key)

    def _insert_recursive(self, node, key):
        if key < node.key:
            if node.left is None:
                node.left = Node(key)
            else:
                self._insert_recursive(node.left, key)
        elif key > node.key:
            if node.right is None:
                node.right = Node(key)
            else:
                self._insert_recursive(node.right, key)
        # If key == node.key, do nothing (duplicate)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search(self, key):
        """Return the key if found, else None."""
        return self._search_recursive(self.root, key)

    def _search_recursive(self, node, key):
        if node is None:
            return None
        if key == node.key:
            return node.key
        elif key < node.key:
            return self._search_recursive(node.left, key)
        else:
            return self._search_recursive(node.right, key)

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #

    def inorder(self):
        """Return all keys in sorted (inorder) order."""
        result = []
        self._inorder_recursive(self.root, result)
        return result

    def _inorder_recursive(self, node, result):
        if node is None:
            return
        self._inorder_recursive(node.left, result)
        result.append(node.key)
        self._inorder_recursive(node.right, result)

    def __len__(self):
        return len(self._count_recursive(self.root))

    def _count_recursive(self, node):
        if node is None:
            return 0
        return 1 + self._count_recursive(node.left) + self._count_recursive(node.right)

    def __iter__(self):
        """Iterate over keys in sorted order."""
        return (key for key in self.inorder())


# ---------------------------------------------------------------------- #
# Demo
# ---------------------------------------------------------------------- #

if __name__ == "__main__":
    bst = BinarySearchTree()
    for value in [50, 30, 70, 20, 40, 60, 80]:
        bst.insert(value)

    print("Inorder:", bst.inorder())
    print("Search 40:", bst.search(40))
    print("Search 99:", bst.search(99))