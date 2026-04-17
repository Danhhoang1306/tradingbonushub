"""Fernet symmetric encryption for secrets stored in the database.

Usage:
    from app.utils.crypto import encrypt_secret, decrypt_secret

    ciphertext = encrypt_secret("my-smtp-password")
    plaintext  = decrypt_secret(ciphertext)

Key management:
    - FERNET_KEY env var holds a URL-safe base64-encoded 32-byte key.
    - Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    - Store in .env and back up securely — losing the key means losing access to all encrypted secrets.
"""
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

_fernet: Fernet | None = None
_logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("FERNET_KEY")
        if not key:
            raise RuntimeError(
                "FERNET_KEY is not set. "
                "Generate a new key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Encrypt plaintext → Fernet token string. Returns plaintext unchanged if empty."""
    if not plaintext:
        return plaintext
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt Fernet token → plaintext.

    - If decryption succeeds: return plaintext.
    - If InvalidToken: may be a legacy plaintext value not yet migrated — log warning, return as-is.
    - If other error (malformed key, FERNET_KEY not set...): raise to surface the error clearly.
    """
    if not ciphertext:
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Value is not encrypted (legacy plaintext). Log for tracking — should be re-encrypted.
        _logger.warning(
            "decrypt_secret: cannot decrypt value (may be legacy plaintext). "
            "Run scripts/encrypt_existing_secrets.py to migrate."
        )
        return ciphertext
