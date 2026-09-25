import unittest

from bst import BST, Node


class TestBST(unittest.TestCase):
    def setUp(self):
        self.tree = BST()
        for v in [50, 30, 70, 20, 40, 60, 80]:
            self.tree.insert(v)

    def test_insert_builds_tree(self):
        self.assertIsInstance(self.tree.root, Node)
        self.assertEqual(self.tree.root.value, 50)
        self.assertEqual(self.tree.root.left.value, 30)
        self.assertEqual(self.tree.root.right.value, 70)

    def test_insert_duplicate_ignored(self):
        self.assertFalse(self.tree.insert(30))
        self.assertEqual(self.tree.inorder(), [20, 30, 40, 50, 60, 70, 80])

    def test_insert_recursive(self):
        t = BST()
        for v in [10, 5, 15, 5]:
            t.insert_recursive(v)
        self.assertEqual(t.inorder(), [5, 10, 15])

    def test_search_found(self):
        node = self.tree.search(60)
        self.assertIsNotNone(node)
        self.assertEqual(node.value, 60)
        self.assertIn(20, self.tree)

    def test_search_missing(self):
        self.assertIsNone(self.tree.search(45))
        self.assertNotIn(45, self.tree)

    def test_search_recursive(self):
        self.assertEqual(self.tree.search_recursive(80).value, 80)
        self.assertIsNone(self.tree.search_recursive(1))

    def test_inorder_sorted(self):
        self.assertEqual(self.tree.inorder(), [20, 30, 40, 50, 60, 70, 80])
        self.assertEqual(len(self.tree), 7)

    def test_empty_tree(self):
        t = BST()
        self.assertIsNone(t.search(1))
        self.assertEqual(t.inorder(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)