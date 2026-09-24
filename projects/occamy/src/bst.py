"""Binary Search Tree (BST) implementation with insert and search methods."""


class Node:
    """A single node in the BST."""

    __slots__ = ("value", "left", "right")

    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None


class BinarySearchTree:
    """A Binary Search Tree where left children are <= parent and
    right children are > parent.

    Duplicate values are placed in the right subtree (consistent with the
    "right > parent" convention, equal values go right).
    """

    def __init__(self):
        self.root = None

    # ------------------------------------------------------------------ #
    # Insert
    # ------------------------------------------------------------------ #
    def insert(self, value):
        """Insert *value* into the BST.

        Returns the tree itself to allow fluent chaining, e.g.
        ``bst.insert(5).insert(3)``.
        """
        new_node = Node(value)

        if self.root is None:
            self.root = new_node
            return self

        current = self.root
        while True:
            if value <= current.value:
                if current.left is None:
                    current.left = new_node
                    break
                current = current.left
            else:
                if current.right is None:
                    current.right = new_node
                    break
                current = current.right

        return self

    # Recursive variant (useful for interviews / functional style):
    def insert_recursive(self, value):
        """Insert *value* into the BST using recursion."""
        self.root = self._insert_rec(self.root, value)
        return self

    @staticmethod
    def _insert_rec(node, value):
        if node is None:
            return Node(value)
        if value <= node.value:
            node.left = BinarySearchTree._insert_rec(node.left, value)
        else:
            node.right = BinarySearchTree._insert_rec(node.right, value)
        return node

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def search(self, value):
        """Return ``True`` if *value* exists in the BST, else ``False``."""
        current = self.root
        while current is not None:
            if value == current.value:
                return True
            elif value < current.value:
                current = current.left
            else:
                current = current.right
        return False

    # Recursive variant:
    def search_recursive(self, value):
        """Return ``True`` if *value* exists in the BST (recursive)."""
        return self._search_rec(self.root, value)

    @staticmethod
    def _search_rec(node, value):
        if node is None:
            return False
        if value == node.value:
            return True
        return BinarySearchTree._search_rec(
            node.left if value < node.value else node.right, value
        )

    # ------------------------------------------------------------------ #
    # Helpers (convenience / testing)
    # ------------------------------------------------------------------ #
    def in_order(self):
        """Return the tree's values in sorted (in-order) order."""
        result = []
        self._in_order_rec(self.root, result)
        return result

    @staticmethod
    def _in_order_rec(node, accumulator):
        if node is not None:
            BinarySearchTree._in_order_rec(node.left, accumulator)
            accumulator.append(node.value)
            BinarySearchTree._in_order_rec(node.right, accumulator)

    def min_value(self):
        """Return the smallest value in the tree, or ``None`` if empty."""
        if self.root is None:
            return None
        current = self.root
        while current.left is not None:
            current = current.left
        return current.value

    def max_value(self):
        """Return the largest value in the tree, or ``None`` if empty."""
        if self.root is None:
            return None
        current = self.root
        while current.right is not None:
            current = current.right
        return current.value


# ---------------------------------------------------------------------- #
# Demo / simple self-test
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    bst = BinarySearchTree()
    values = [5, 3, 7, 1, 4, 6, 9, 8, 5]

    for v in values:
        bst.insert(v)

    print("In-order (should be sorted):", bst.in_order())
    print("Min:", bst.min_value())
    print("Max:", bst.max_value())

    for target in [1, 4, 6, 9, 5, 2]:
        found_iter = bst.search(target)
        found_rec = bst.search_recursive(target)
        assert found_iter == found_rec, (target, found_iter, found_rec)
        print(f"search({target:>2}) -> {found_iter}")

    # Fluent insertion
    bst2 = BinarySearchTree()
    for v in [10, 5, 15]:
        bst2.insert(v)

    assert bst2.search(10)
    assert bst2.search(5)
    assert bst2.search(15)
    assert not bst2.search(100)

    # Recursive insert + search
    bst3 = BinarySearchTree()
    bst3.insert_recursive(5).insert_recursive(3).insert_recursive(7)
    assert bst3.search(3)
    assert bst3.search(7)
    assert not bst3.search(4)

    print("\nAll assertions passed.")