import unittest
from string_utils import to_title_case, truncate

class TestStringUtils(unittest.TestCase):
    def test_title_case(self):
        self.assertEqual(to_title_case("hello world"), "Hello World")

    def test_truncate(self):
        self.assertEqual(truncate("hello", 10), "hello")
        self.assertEqual(truncate("hello world", 5), "hello...")

if __name__ == '__main__':
    unittest.main()
