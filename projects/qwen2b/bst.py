class Node:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None


class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, value):
        """Insert a value into the BST."""
        if self.root is None:
            self.root = Node(value)
            return

        current = self.root
        while True:
            if value < current.value:
                if current.left is None:
                    current.left = Node(value)
                    break
                current = current.left
            elif value > current.value:
                if current.right is None:
                    current.right = Node(value)
                    break
                current = current.right
            else:
                break  # duplicate, skip

    def search(self, value):
        """Search for a value in the BST. Returns True if found, False otherwise."""
        current = self.root
        while current is not None:
            if value < current.value:
                current = current.left
            elif value > current.value:
                current = current.right
            else:
                return True
        return False

    def _inorder(self, node, result):
        """Helper for in-order traversal."""
        if node is None:
            return
        self._inorder(node.left, result)
        result.append(node.value)
        self._inorder(node.right, result)

    def inorder(self):
        """Return sorted list of all values."""
        result = []
        self._inorder(self.root, result)
        return result


# Demo
if __name__ == "__main__":
    bst = BinarySearchTree()
    for val in [5, 3, 7, 1, 4, 6, 8]:
        bst.insert(val)

    print("In-order traversal:", bst.inorder())
    print("Search 4:", bst.search(4))
    print("Search 9:", bst.search(9))
