import unittest

from calculator import add, multiply, subtract, divide

class TestCalculator(unittest.TestCase):
    def test_divide(self):
        # Test normal case
        result = divide(10, 2)
        self.assertEqual(result, 5)
        # Test negative values
        result = divide(-10, 2)
        self.assertEqual(result, -5)
        # Test division by zero raises exception
        with self.assertRaises(ZeroDivisionError):
            divide(5, 0)

    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(3, 5), -2)
        self.assertEqual(subtract(0, 0), 0)
        self.assertEqual(subtract(-1, -1), 0)

    def test_multiply(self):
        self.assertEqual(multiply(2, 3), 6)
        self.assertEqual(multiply(-1, 1), -1)
        self.assertEqual(multiply(0, 5), 0)


if __name__ == "__main__":
    unittest.main()