import unittest
from text_parser import strip_prefix

class TestParser(unittest.TestCase):
    def test_strip_prefix(self):
        self.assertEqual(strip_prefix("Bearer token123", "Bearer "), "token123")
        self.assertEqual(strip_prefix("hello", "world"), "hello")

if __name__ == '__main__':
    unittest.main()
