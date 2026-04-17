"""Tests for password hashing service (auth.py)."""
import pytest

from app.services.auth import (
    hash_pw,
    verify_pw,
    needs_rehash,
    _hash_pbkdf2,
    _verify_pbkdf2,
    _is_pbkdf2,
    _HAS_ARGON2,
)


class TestPBKDF2Legacy:
    """Ensure legacy PBKDF2 hashing still works for existing users."""

    def test_hash_and_verify(self):
        h = _hash_pbkdf2("mypassword123")
        assert _verify_pbkdf2("mypassword123", h)

    def test_wrong_password(self):
        h = _hash_pbkdf2("correct")
        assert not _verify_pbkdf2("wrong", h)

    def test_is_pbkdf2_format(self):
        h = _hash_pbkdf2("test")
        assert _is_pbkdf2(h)
        # salt:key — 32 hex chars : 64 hex chars
        salt, key = h.split(":")
        assert len(salt) == 32
        assert len(key) == 64

    def test_is_pbkdf2_rejects_argon2(self):
        # Argon2 hashes start with $argon2
        assert not _is_pbkdf2("$argon2id$v=19$m=65536,t=2,p=1$...")

    def test_empty_password(self):
        h = _hash_pbkdf2("")
        assert _verify_pbkdf2("", h)
        assert not _verify_pbkdf2("notempty", h)

    def test_unicode_password(self):
        h = _hash_pbkdf2("mật_khẩu_tiếng_việt")
        assert _verify_pbkdf2("mật_khẩu_tiếng_việt", h)

    def test_corrupted_hash(self):
        assert not _verify_pbkdf2("test", "corrupted")
        assert not _verify_pbkdf2("test", "")
        assert not _verify_pbkdf2("test", "abc:def:ghi")

    def test_unique_salts(self):
        """Each hash should use a different random salt."""
        h1 = _hash_pbkdf2("same_password")
        h2 = _hash_pbkdf2("same_password")
        assert h1 != h2  # different salts


class TestHashPw:
    """Test the primary hash_pw / verify_pw functions."""

    def test_hash_and_verify(self):
        h = hash_pw("enterprise_password!")
        assert verify_pw("enterprise_password!", h)

    def test_wrong_password(self):
        h = hash_pw("correct")
        assert not verify_pw("wrong", h)

    def test_verify_legacy_pbkdf2(self):
        """New verify_pw should still handle old PBKDF2 hashes."""
        legacy_hash = _hash_pbkdf2("old_password")
        assert verify_pw("old_password", legacy_hash)

    def test_long_password(self):
        pw = "a" * 1000
        h = hash_pw(pw)
        assert verify_pw(pw, h)

    def test_special_characters(self):
        pw = "p@$$w0rd!#%^&*()_+-=[]{}|;':\",./<>?"
        h = hash_pw(pw)
        assert verify_pw(pw, h)


class TestNeedsRehash:
    """Test the transparent rehash detection."""

    def test_pbkdf2_needs_rehash(self):
        h = _hash_pbkdf2("test")
        if _HAS_ARGON2:
            assert needs_rehash(h), "PBKDF2 should be rehashed when Argon2 is available"
        else:
            assert not needs_rehash(h)

    @pytest.mark.skipif(not _HAS_ARGON2, reason="argon2-cffi not installed")
    def test_argon2_current_no_rehash(self):
        h = hash_pw("test")
        assert not needs_rehash(h), "Fresh Argon2 hash should not need rehash"


@pytest.mark.skipif(not _HAS_ARGON2, reason="argon2-cffi not installed")
class TestArgon2:
    """Test Argon2-specific behavior."""

    def test_hash_starts_with_argon2(self):
        h = hash_pw("test")
        assert h.startswith("$argon2")

    def test_cross_verify_pbkdf2_then_argon2(self):
        """Simulate a migration: old hash verified, then rehashed."""
        old_hash = _hash_pbkdf2("migrate_me")
        assert verify_pw("migrate_me", old_hash)

        new_hash = hash_pw("migrate_me")
        assert verify_pw("migrate_me", new_hash)
        assert new_hash.startswith("$argon2")
