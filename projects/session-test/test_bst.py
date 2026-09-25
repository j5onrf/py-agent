"""Test suite for bst.BinarySearchTree. Run: python3 -m unittest test_bst -v"""

import random
import unittest

from bst import BinarySearchTree


class TestInsertSearch(unittest.TestCase):
    def setUp(self):
        self.tree = BinarySearchTree()

    def test_empty_tree(self):
        self.assertTrue(self.tree.is_empty())
        self.assertEqual(len(self.tree), 0)
        self.assertIsNone(self.tree.root)
        self.assertIsNone(self.tree.search(1))

    def test_insert_into_empty_tree(self):
        self.assertTrue(self.tree.insert(5))
        self.assertFalse(self.tree.is_empty())
        self.assertEqual(self.tree.root.key, 5)
        self.assertEqual(len(self.tree), 1)

    def test_search_finds_root(self):
        self.tree.insert(5)
        self.assertTrue(self.tree.contains(5))
        self.assertEqual(self.tree.search(5).key, 5)

    def test_search_misses_absent_key(self):
        self.tree.insert(5)
        self.assertIsNone(self.tree.search(4))
        self.assertFalse(self.tree.contains(4))

    def test_bst_structure_is_correct(self):
        # Insertion order deliberately skewed to exercise the left spine.
        for key in [50, 30, 70, 20, 40, 60, 80]:
            self.tree.insert(key)

        root = self.tree.root
        self.assertEqual(root.key, 50)
        self.assertEqual(root.left.key, 30)
        self.assertEqual(root.right.key, 70)
        self.assertEqual(root.left.left.key, 20)
        self.assertEqual(root.left.right.key, 40)
        self.assertEqual(root.right.left.key, 60)
        self.assertEqual(root.right.right.key, 80)

    def test_duplicate_rejected_and_size_unchanged(self):
        self.tree.insert(5)
        self.assertFalse(self.tree.insert(5))
        self.assertEqual(len(self.tree), 1)

    def test_values_round_trip(self):
        self.tree.insert("a", 1)
        self.tree.insert("b", 2)
        self.assertEqual(self.tree.get("a"), 1)
        self.assertEqual(self.tree.get("b"), 2)
        self.assertIsNone(self.tree.get("zzz"))

    def test_get_default(self):
        self.tree.insert("a", 1)
        self.assertEqual(self.tree.get("b", default=-1), -1)

    def test_put_updates_existing(self):
        self.tree.put("a", 1)
        self.tree.put("a", 99)
        self.assertEqual(self.tree.get("a"), 99)
        self.assertEqual(len(self.tree), 1)

    def test_string_keys(self):
        tree = BinarySearchTree()
        for word in ["pear", "apple", "fig", "banana"]:
            tree.insert(word)
        self.assertEqual(list(tree), ["apple", "banana", "fig", "pear"])

    def test_negative_and_float_keys(self):
        for key in [-3, 2.5, 0, -10.25, 7]:
            self.tree.insert(key)
        self.assertEqual(list(self.tree), sorted([-3, 2.5, 0, -10.25, 7]))
        self.assertTrue(self.tree.contains(-10.25))


class TestTraversal(unittest.TestCase):
    def test_inorder_is_sorted(self):
        tree = BinarySearchTree()
        keys = [5, 3, 8, 1, 4, 7, 9]
        for k in keys:
            tree.insert(k)
        self.assertEqual(list(tree.inorder()), sorted(keys))

    def test_preorder_root_first(self):
        tree = BinarySearchTree()
        for k in [5, 3, 8, 1]:
            tree.insert(k)
        self.assertEqual(list(tree.preorder()), [5, 3, 1, 8])

    def test_in_operator_and_iteration(self):
        tree = BinarySearchTree()
        for k in [2, 1, 3]:
            tree.insert(k)
        self.assertIn(2, tree)
        self.assertNotIn(99, tree)
        self.assertEqual(list(tree), [1, 2, 3])


class TestRandomised(unittest.TestCase):
    def test_matches_sorted_reference(self):
        """Insert random keys; inorder must equal the sorted reference set."""
        rng = random.Random(1234)
        for trial in range(20):
            keys = [rng.randint(-500, 500) for _ in range(200)]
            unique = set(keys)
            tree = BinarySearchTree()
            for k in keys:
                tree.insert(k)
            self.assertEqual(len(tree), len(unique))
            self.assertEqual(list(tree.inorder()), sorted(unique))

    def test_search_matches_set_membership(self):
        rng = random.Random(99)
        keys = [rng.randint(0, 1000) for _ in range(300)]
        tree = BinarySearchTree()
        for k in keys:
            tree.insert(k)
        present = set(keys)
        for probe in range(-20, 1020):
            self.assertEqual(tree.contains(probe), probe in present, probe)


class TestDegenerateTree(unittest.TestCase):
    def test_sorted_insertion_does_not_recurse_overflow(self):
        """A fully skewed tree must not hit Python's recursion limit.

        This is the regression test for using an iterative insert/search: a
        recursive implementation raises RecursionError well before 10k nodes.
        """
        tree = BinarySearchTree()
        n = 10_000
        for i in range(n):
            tree.insert(i)
        self.assertEqual(len(tree), n)
        for i in range(n):
            self.assertTrue(tree.contains(i))
        self.assertEqual(list(tree.inorder()), list(range(n)))


if __name__ == "__main__":
    unittest.main()
