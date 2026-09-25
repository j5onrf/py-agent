"""Binary Search Tree with iterative and recursive insert/search."""


class Node:
    """A single node in the binary search tree."""

    __slots__ = ("value", "left", "right")

    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None

    def __repr__(self):
        return f"Node({self.value!r})"


class BST:
    """Binary Search Tree: left < root < right."""

    def __init__(self):
        self.root = None

    # ------------------------------------------------------------------ insert
    def insert(self, value):
        """Insert value; duplicates are ignored. Returns True if inserted."""
        if self.root is None:
            self.root = Node(value)
            return True

        current = self.root
        while True:
            if value == current.value:
                return False  # duplicate
            if value < current.value:
                if current.left is None:
                    current.left = Node(value)
                    return True
                current = current.left
            else:
                if current.right is None:
                    current.right = Node(value)
                    return True
                current = current.right

    def insert_recursive(self, value):
        """Recursive insert; duplicates are ignored. Returns True if inserted."""
        if self.root is None:
            self.root = Node(value)
            return True

        def _insert(node, val):
            if val == node.value:
                return False
            if val < node.value:
                if node.left is None:
                    node.left = Node(val)
                    return True
                return _insert(node.left, val)
            if node.right is None:
                node.right = Node(val)
                return True
            return _insert(node.right, val)

        return _insert(self.root, value)

    # ------------------------------------------------------------------ search
    def search(self, value):
        """Return the Node holding value, or None."""
        current = self.root
        while current is not None:
            if value == current.value:
                return current
            current = current.left if value < current.value else current.right
        return None

    def search_recursive(self, value):
        """Recursive search; returns the Node or None."""

        def _search(node):
            if node is None:
                return None
            if value == node.value:
                return node
            return _search(node.left if value < node.value else node.right)

        return _search(self.root)

    def __contains__(self, value):
        return self.search(value) is not None

    # ------------------------------------------------------------------ output
    def inorder(self):
        """Return values in sorted order (also proves the BST property)."""
        result, stack, current = [], [], self.root
        while stack or current is not None:
            while current is not None:
                stack.append(current)
                current = current.left
            current = stack.pop()
            result.append(current.value)
            current = current.right
        return result

    def __len__(self):
        return len(self.inorder())


if __name__ == "__main__":
    tree = BST()
    for v in [50, 30, 70, 20, 40, 60, 80]:
        tree.insert(v)

    print("inorder:", tree.inorder())
    print("search 40:", tree.search(40))
    print("search 99:", tree.search(99))