import unittest

from string_utils import count_vowels, reverse_words


class TestStringUtils(unittest.TestCase):
    def test_reverse_words_basic(self):
        self.assertEqual(reverse_words("hello world"), "world hello")
        self.assertEqual(reverse_words("python is awesome"), "awesome is python")

    def test_reverse_words_single_and_empty(self):
        self.assertEqual(reverse_words("hello"), "hello")
        self.assertEqual(reverse_words(""), "")
        self.assertEqual(reverse_words("   "), "")

    def test_reverse_words_type_error(self):
        with self.assertRaises(TypeError):
            reverse_words(123)

    def test_count_vowels_basic(self):
        self.assertEqual(count_vowels("hello"), 2)
        self.assertEqual(count_vowels("PYTHON"), 1)
        self.assertEqual(count_vowels("AEIOUaeiou"), 10)

    def test_count_vowels_none_and_empty(self):
        self.assertEqual(count_vowels("rhythm"), 0)
        self.assertEqual(count_vowels(""), 0)

    def test_count_vowels_type_error(self):
        with self.assertRaises(TypeError):
            count_vowels(None)


if __name__ == "__main__":
    unittest.main()
