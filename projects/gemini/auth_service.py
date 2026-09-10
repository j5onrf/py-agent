import hashlib

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()