import unittest
from math_utils import power

class TestMath(unittest.TestCase):
    def test_power(self):
        self.assertEqual(power(2, 3), 8)
        self.assertEqual(power(5, 0), 1)
        self.assertEqual(power(3, 2), 9)

if __name__ == '__main__':
    unittest.main()
