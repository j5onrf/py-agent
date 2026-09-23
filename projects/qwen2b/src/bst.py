"""Binary Search Tree (BST) implementation with insert and search."""


class Node:
    """A single node in the BST."""

    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None


class BinarySearchTree:
    """Binary Search Tree supporting insert and search operations."""

    def __init__(self):
        self.root = None

    def insert(self, value) -> None:
        """Insert a value into the BST.

        Args:
            value: The integer value to insert.
        """
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
                # Duplicate values are not inserted
                break

    def search(self, value) -> bool:
        """Search for a value in the BST.

        Args:
            value: The integer value to search for.

        Returns:
            True if the value exists in the tree, False otherwise.
        """
        current = self.root
        while current is not None:
            if value < current.value:
                current = current.left
            elif value > current.value:
                current = current.right
            else:
                return True
        return False

    def delete(self, value) -> None:
        """Delete a value from the BST.

        Args:
            value: The integer value to delete.
        """
        self.root = self._delete_recursive(self.root, value)

    def _delete_recursive(self, node, value):
        """Helper for recursive deletion."""
        if node is None:
            return None

        if value < node.value:
            node.left = self._delete_recursive(node.left, value)
        elif value > node.value:
            node.right = self._delete_recursive(node.right, value)
        else:
            # Node found — handle three cases
            if node.left is None:
                return node.right
            elif node.right is None:
                return node.left
            else:
                # Two children: replace with inorder successor
                successor = self._find_min(node.right)
                node.value = successor.value
                node.right = self._delete_recursive(node.right, successor.value)
        return node

    def _find_min(self, node):
        """Find the minimum value node in a subtree."""
        current = node
        while current.left is not None:
            current = current.left
        return current

    def inorder(self) -> list:
        """Return values in sorted order via inorder traversal."""
        result = []
        self._inorder_recursive(self.root, result)
        return result

    def _inorder_recursive(self, node, result):
        if node is not None:
            self._inorder_recursive(node.left, result)
            result.append(node.value)
            self._inorder_recursive(node.right, result)


# --- Demo / Quick Test ---
if __name__ == "__main__":
    bst = BinarySearchTree()

    # Insert values
    for val in [50, 30, 70, 20, 40, 60, 80]:
        bst.insert(val)

    print("Inorder traversal:", bst.inorder())

    # Search
    print("Search 40:", bst.search(40))   # True
    print("Search 99:", bst.search(99))   # False

    # Delete
    bst.delete(30)
    print("After deleting 30:", bst.inorder())
