import unittest
from math_utils import calculate_discount, clamp

class TestMathUtils(unittest.TestCase):
    def test_calculate_discount(self):
        # A $100 item with a 20% discount should cost $80.00
        self.assertAlmostEqual(calculate_discount(100.0, 20.0), 80.0)
        self.assertAlmostEqual(calculate_discount(50.0, 0.0), 50.0)
        self.assertAlmostEqual(calculate_discount(200.0, 50.0), 100.0)

    def test_clamp(self):
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-5, 0, 10), 0)
        self.assertEqual(clamp(15, 0, 10), 10)

if __name__ == '__main__':
    unittest.main()
