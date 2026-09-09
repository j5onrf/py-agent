from math_engine.calc import compute_fee

def test_billing():
    # FIX: pass rate as keyword argument to match calc.py signature
    fee = compute_fee(amount=200.0, rate=0.10)
    assert fee == 20.0

if __name__ == "__main__":
    test_billing()
    print("BILLING PASSED")
