from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    # Delayed import to avoid circular deps; reads jwt_secret at call time
    from sebastian.config import settings

    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.sebastian_jwt_secret.encode()).digest()
    )
    return Fernet(key)


def encrypt(plain: str) -> str:
    """Encrypt a plaintext string. Returns URL-safe base64 ciphertext."""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(enc: str) -> str:
    """Decrypt a Fernet-encrypted string back to plaintext."""
    return _fernet().decrypt(enc.encode()).decode()
