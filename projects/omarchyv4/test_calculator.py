import unittest

from calculator import add, multiply, subtract, divide, power, modulo, average, median

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

    def test_power(self):
        self.assertEqual(power(2, 3), 8)
        self.assertEqual(power(0, 5), 0)
        self.assertEqual(power(-2, 2), 4)

    def test_modulo(self):
        self.assertEqual(modulo(10, 3), 1)
        self.assertEqual(modulo(-10, 3), 2)  # Python's modulo behavior
        with self.assertRaises(ZeroDivisionError):
            result = modulo(5, 0)

    def test_average(self):
        # Test normal cases
        self.assertAlmostEqual(average(1, 2, 3, 4, 5), 3.0)
        self.assertAlmostEqual(average(10, 20), 15.0)
        self.assertAlmostEqual(average(7), 7.0)
        # Test negative values
        self.assertAlmostEqual(average(-1, -2, -3), -2.0)
        # Test empty input raises ValueError
        with self.assertRaises(ValueError) as context:
            average()
        self.assertEqual(str(context.exception), "Cannot compute average of empty values")

    def test_median(self):
        # Test odd-length list
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([5, 3, 1, 4, 2]), 3)
        # Test even-length list
        self.assertEqual(median([4, 1, 3, 2]), 2.5)
        self.assertEqual(median([1, 2, 3, 4]), 2.5)
        # Test single element
        self.assertEqual(median([7]), 7)
        # Test empty list raises ValueError
        with self.assertRaises(ValueError) as context:
            median([])
        self.assertEqual(str(context.exception), "Cannot compute median of empty list")


if __name__ == "__main__":
    unittest.main()