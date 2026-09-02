import unittest
from math_tools import power

class TestMathTools(unittest.TestCase):
    def test_power_positive(self):
        self.assertEqual(power(2.0, 3), 8)

    def test_power_zero_exponent(self):
        self.assertEqual(power(5.0, 0), 1)

    def test_power_negative(self):
        self.assertEqual(power(-2.0, 2), 4)

if __name__ == '__main__':
    unittest.main()