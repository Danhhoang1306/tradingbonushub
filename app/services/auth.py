"""Password hashing with Argon2 (primary) and PBKDF2 (legacy) support.

New passwords are hashed with Argon2id. Existing PBKDF2 hashes are still
verified — and transparently rehashed to Argon2 on next successful login
(the caller should persist the new hash).
"""
import asyncio
import hashlib
import os

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    _argon2 = PasswordHasher(
        time_cost=2,        # iterations
        memory_cost=65536,  # 64 MB
        parallelism=1,
    )
    _HAS_ARGON2 = True
except ImportError:
    _HAS_ARGON2 = False


# ── PBKDF2 (legacy) ─────────────────────────────────────────────────────────

def _hash_pbkdf2(pw: str) -> str:
    salt = os.urandom(16)
    k = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 100_000)
    return salt.hex() + ":" + k.hex()


def _verify_pbkdf2(pw: str, stored: str) -> bool:
    try:
        salt_hex, k_hex = stored.split(":")
        k = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 100_000)
        return k.hex() == k_hex
    except Exception:
        return False


def _is_pbkdf2(stored: str) -> bool:
    """PBKDF2 hashes are formatted as hex_salt:hex_key."""
    parts = stored.split(":")
    return len(parts) == 2 and len(parts[0]) == 32 and len(parts[1]) == 64


# ── Public API ───────────────────────────────────────────────────────────────

def hash_pw(pw: str) -> str:
    """Hash a password — uses Argon2id if available, falls back to PBKDF2."""
    if _HAS_ARGON2:
        return _argon2.hash(pw)
    return _hash_pbkdf2(pw)


def verify_pw(pw: str, stored: str) -> bool:
    """Verify a password against a stored hash (Argon2 or legacy PBKDF2)."""
    if _is_pbkdf2(stored):
        return _verify_pbkdf2(pw, stored)
    if _HAS_ARGON2:
        try:
            return _argon2.verify(stored, pw)
        except (VerifyMismatchError, InvalidHashError, Exception):
            return False
    return False


def needs_rehash(stored: str) -> bool:
    """Check if the stored hash should be upgraded to Argon2."""
    if _is_pbkdf2(stored):
        return _HAS_ARGON2
    if _HAS_ARGON2:
        return _argon2.check_needs_rehash(stored)
    return False


async def hash_pw_async(pw: str) -> str:
    """Hash in thread — both Argon2 and PBKDF2 are CPU-bound."""
    return await asyncio.to_thread(hash_pw, pw)


async def verify_pw_async(pw: str, stored: str) -> bool:
    """Verify in thread — CPU-bound."""
    return await asyncio.to_thread(verify_pw, pw, stored)
