"""Password hashing with bcrypt."""

import bcrypt

# bcrypt only uses the first 72 bytes; 4.x truncated silently, 5.x raises ValueError.
BCRYPT_MAX_PASSWORD_BYTES = 72


def ensure_password_byte_length(password: str) -> str:
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("密码过长")
    return password


def _legacy_password_bytes(password: str) -> bytes:
    """Truncate to 72 bytes for verifying hashes created before byte-length validation."""
    return password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]


def hash_password(password: str) -> str:
    ensure_password_byte_length(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            _legacy_password_bytes(password), password_hash.encode("utf-8")
        )
    except ValueError:
        return False
