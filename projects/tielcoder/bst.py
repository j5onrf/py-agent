"""Binary Search Tree (BST) implementation.

A BST is a binary tree where, for every node:
    - all keys in the left subtree are less than the node's key
    - all keys in the right subtree are greater than the node's key
    - both subtrees are also valid BSTs
"""
from typing import Any, Optional


class _Node:
    """A single node in the tree."""

    __slots__ = ("key", "left", "right")

    def __init__(self, key: Any) -> None:
        self.key = key
        self.left: Optional["_Node"] = None
        self.right: Optional["_Node"] = None


class BinarySearchTree:
    """A binary search tree supporting insert and search."""

    def __init__(self) -> None:
        self._root: Optional["_Node"] = None
        self._size: int = 0

    def insert(self, key: Any) -> None:
        """Insert a key into the tree.

        Duplicate keys are ignored to keep the invariant strict.
        """
        if self._root is None:
            self._root = _Node(key)
            self._size += 1
            return

        current = self._root
        while True:
            if key < current.key:
                if current.left is None:
                    current.left = _Node(key)
                    self._size += 1
                    return
                current = current.left
            elif key > current.key:
                if current.right is None:
                    current.right = _Node(key)
                    self._size += 1
                    return
                current = current.right
            else:
                # Duplicate key: nothing to do.
                return

    def search(self, key: Any) -> bool:
        """Return True if the key exists in the tree, else False."""
        current = self._root
        while current is not None:
            if key < current.key:
                current = current.left
            elif key > current.key:
                current = current.right
            else:
                return True
        return False

    def __contains__(self, key: Any) -> bool:
        return self.search(key)

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        return f"BinarySearchTree(size={self._size})"


if __name__ == "__main__":
    tree = BinarySearchTree()
    for value in [5, 3, 8, 1, 4, 7, 9, 2, 6]:
        tree.insert(value)

    print(tree)  # BinarySearchTree(size=9)
    print("search 8 ->", tree.search(8))   # True
    print("search 10 ->", tree.search(10))  # False
    print("6 in tree ->", 6 in tree)        # True
    print("100 in tree ->", 100 in tree)    # False