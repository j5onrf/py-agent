from pkg.string_tools import slugify, truncate

def test_slugify():
    assert slugify("Hello World") == "hello-world"
    # Multiple spaces collapse to a single hyphen
    assert slugify("Python   Agent") == "python-agent", f"Got: {slugify('Python   Agent')}"
    # Special characters are preserved in the slug (not lowercased)
    assert slugify("Hello! @#") == "hello!-@#"

def test_truncate():
    assert truncate("Short") == "Short"
    assert truncate("This is a long sentence", 7) == "This is..."

if __name__ == "__main__":
    test_slugify()
    test_truncate()
    print("ALL TESTS PASSED")
