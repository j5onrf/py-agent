import str_utils

def test_bug():
    # Fails on mixed case: "Aba" should be a palindrome but fails
    assert str_utils.is_palindrome("Aba") == False, "Mixed case should be a palindrome"

def test_fix():
    # Passes once the fix is applied
    assert str_utils.is_palindrome("Aba") == True, "Mixed case should be a palindrome"
