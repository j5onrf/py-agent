class BSTNode:
    """A node in a binary search tree."""

    def __init__(self, value):
        self.value = value
        self.left: BSTNode | None = None
        self.right: BSTNode | None = None


class BinarySearchTree:
    """A binary search tree with insert and search methods."""

    def __init__(self):
        self.root: BSTNode | None = None

    def insert(self, value: int) -> None:
        """Insert a value into the BST. If the tree is empty, the value becomes the root."""
        if self.root is None:
            self.root = BSTNode(value)
            return

        self._insert_recursive(self.root, value)

    def _insert_recursive(self, node: BSTNode, value: int) -> None:
        if value < node.value:
            if node.left is None:
                node.left = BSTNode(value)
            else:
                self._insert_recursive(node.left, value)
        elif value > node.value:
            if node.right is None:
                node.right = BSTNode(value)
            else:
                self._insert_recursive(node.right, value)

    def search(self, value: int) -> bool:
        """Search for a value in the BST. Returns True if found, False otherwise."""
        return self._search_recursive(self.root, value)

    def _search_recursive(self, node: BSTNode | None, value: int) -> bool:
        if node is None:
            return False
        if value == node.value:
            return True
        elif value < node.value:
            return self._search_recursive(node.left, value)
        else:
            return self._search_recursive(node.right, value)

    def __repr__(self) -> str:
        elements = []
        self._inorder(self.root, elements)
        return f"BinarySearchTree({elements})"

    def _inorder(self, node: BSTNode | None, elements: list[str]) -> None:
        if node is not None:
            self._inorder(node.left, elements)
            elements.append(str(node.value))
            self._inorder(node.right, elements)


# --- Demo / usage ---
if __name__ == "__main__":
    bst = BinarySearchTree()
    values = [50, 30, 70, 20, 40, 60, 80]
    for v in values:
        bst.insert(v)

    print("Tree:", bst)

    # Search tests
    print("Search 40:", bst.search(40))  # True
    print("Search 99:", bst.search(99))  # False
    print("Search 50:", bst.search(50))  # True
    print("Search 20:", bst.search(20))  # True
    print("Search 15:", bst.search(15))  # False

    # Insert more and verify
    bst.insert(35)
    print("After inserting 35:", bst)
    print("Search 35:", bst.search(35))  # True