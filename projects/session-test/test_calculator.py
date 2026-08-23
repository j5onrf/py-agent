import unittest

from calculator import add, divide, multiply, subtract


class TestCalculator(unittest.TestCase):
    """Test cases for calculator module."""

    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(-5, -3), -8)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(0, 0), 0)
        self.assertEqual(subtract(-1, -1), 0)
        self.assertEqual(subtract(3, 5), -2)

    def test_multiply(self):
        self.assertEqual(multiply(2, 3), 6)
        self.assertEqual(multiply(0, 5), 0)
        self.assertEqual(multiply(-1, 5), -5)
        self.assertEqual(multiply(-2, -3), 6)

    def test_divide(self):
        self.assertEqual(divide(6, 3), 2.0)
        self.assertEqual(divide(5, 2), 2.5)
        self.assertEqual(divide(0, 1), 0.0)
        self.assertEqual(divide(-6, 3), -2.0)

    def test_divide_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            divide(1, 0)

    def test_divide_negative_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            divide(-5, 0)


if __name__ == "__main__":
    unittest.main()
