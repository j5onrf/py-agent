import unittest
from array_utils import filter_even_numbers

class TestArray(unittest.TestCase):
    def test_filter_even(self):
        self.assertEqual(filter_even_numbers([1, 2, 3, 4, 5, 6]), [2, 4, 6])
        self.assertEqual(filter_even_numbers([1, 3, 5]), [])
        self.assertEqual(filter_even_numbers([]), [])

if __name__ == '__main__':
    unittest.main()
