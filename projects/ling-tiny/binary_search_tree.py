class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None


class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, key):
        if self.root is None:
            self.root = Node(key)
        else:
            self._insert(self.root, key)

    def _insert(self, node, key):
        if key < node.key:
            if node.left is None:
                node.left = Node(key)
            else:
                self._insert(node.left, key)
        elif key > node.key:
            if node.right is None:
                node.right = Node(key)
            else:
                self._insert(node.right, key)

    def search(self, key):
        return self._search(self.root, key)

    def _search(self, node, key):
        if node is None:
            return False
        if key == node.key:
            return True
        elif key < node.key:
            return self._search(node.left, key)
        else:
            return self._search(node.right, key)

    def __repr__(self):
        return f"BinarySearchTree({self.root})"


if __name__ == "__main__":
    bst = BinarySearchTree()
    for key in [50, 30, 70, 20, 40, 60, 80]:
        bst.insert(key)

    print("Search 40:", bst.search(40))   # True
    print("Search 25:", bst.search(25))   # False
    print("Search 80:", bst.search(80))   # True
    print("Search 10:", bst.search(10))   # False