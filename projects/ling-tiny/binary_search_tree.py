class TreeNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None


class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, key):
        """Insert a key into the BST. Returns True if inserted, False if duplicate."""
        if self.root is None:
            self.root = TreeNode(key)
            return True
        return self._insert(self.root, key)

    def _insert(self, node, key):
        if node is None:
            return False  # shouldn't happen if called correctly, but handle gracefully
        if key == node.key:
            return False  # duplicate
        if key < node.key:
            if node.left is None:
                node.left = TreeNode(key)
                return True
            return self._insert(node.left, key)
        return self._insert(node.right, key)

    def search(self, key):
        """Search for a key in the BST. Returns True if found, False otherwise."""
        return self._search(self.root, key)

    def _search(self, node, key):
        if node is None:
            return False
        if key == node.key:
            return True
        if key < node.key:
            return self._search(node.left, key)
        return self._search(node.right, key)

    def __str__(self):
        result = []
        if self.root:
            self._inorder(self.root, result)
        return ", ".join(map(str, result))

    def _inorder(self, node, result):
        if node:
            self._inorder(node.left, result)
            result.append(node.key)
            self._inorder(node.right, result)


if __name__ == "__main__":
    bst = BinarySearchTree()
    for key in [15, 10, 20, 8, 12, 17, 25]:
        bst.insert(key)
    print("BST:", bst)
    print("Search 12:", bst.search(12))
    print("Search 99:", bst.search(99))
    print("Search 15:", bst.search(15))