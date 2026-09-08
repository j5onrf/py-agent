from pkg.string_tools import slugify, truncate

def test_slugify():
    assert slugify("Hello World") == "hello-world"
    # This assert will FAIL because replace(" ", "-") gives "python---agent"
    assert slugify("Python   Agent") == "python-agent", f"Got: {slugify('Python   Agent')}"

def test_truncate():
    assert truncate("Short") == "Short"
    assert truncate("This is a long sentence", 7) == "This is..."

if __name__ == "__main__":
    test_slugify()
    test_truncate()
    print("ALL TESTS PASSED")
