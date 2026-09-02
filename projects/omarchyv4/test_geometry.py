import unittest
from geometry import circle_area


class TestCircleArea(unittest.TestCase):
    """Test cases for the circle_area function."""

    def test_circle_area_positive_radius(self):
        """Test that circle_area returns the correct area for a positive radius."""
        self.assertAlmostEqual(circle_area(1), 3.141592653589793)

    def test_circle_area_zero_radius(self):
        """Test that circle_area returns 0 when radius is zero."""
        self.assertEqual(circle_area(0), 0)


if __name__ == "__main__":
    unittest.main()