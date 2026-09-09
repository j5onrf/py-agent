class DataVault:
    def __init__(self, key: str):
        self.key = key
        self.locked = True

    def process_payload(self, data: str) -> str:
        # Step 1: validate
        if not data:
            return "EMPTY"
        return f"PROCESSED_{data}"

    def export_payload(self, data: str) -> str:
        # Step 1: validate
        if not data:
            return "EMPTY"
        return f"ENCRYPTED_{data}"

if __name__ == "__main__":
    vault = DataVault("secret")
    assert vault.process_payload("test") == "PROCESSED_test"
    assert vault.export_payload("test") == "ENCRYPTED_test"
    print("VAULT PASSED")
