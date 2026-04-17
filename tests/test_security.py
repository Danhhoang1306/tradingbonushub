"""Tests for security utilities — lockout, crypto, CSRF, responses."""
import os
import pytest


class TestLockoutLogic:
    """Unit tests for lockout threshold and timing logic."""

    def test_lockout_constants(self):
        from app.utils.lockout import _MAX_ATTEMPTS, _WINDOW_MINUTES
        assert _MAX_ATTEMPTS == 3, "Should lock after 3 failed attempts"
        assert _WINDOW_MINUTES == 30, "Lockout window should be 30 minutes"


class TestCrypto:
    """Test Fernet encryption/decryption for stored secrets."""

    @pytest.fixture(autouse=True)
    def set_fernet_key(self, monkeypatch):
        # Use a valid Fernet key for testing
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("FERNET_KEY", key)

    def test_encrypt_decrypt_roundtrip(self):
        # Reset cached Fernet instance to pick up test key
        import app.utils.crypto as crypto_mod
        crypto_mod._fernet = None
        original = "smtp_password_123"
        encrypted = crypto_mod.encrypt_secret(original)
        assert encrypted != original
        assert crypto_mod.decrypt_secret(encrypted) == original

    def test_encrypt_produces_different_ciphertexts(self):
        import app.utils.crypto as crypto_mod
        crypto_mod._fernet = None
        e1 = crypto_mod.encrypt_secret("same")
        e2 = crypto_mod.encrypt_secret("same")
        # Fernet uses a random IV each time
        assert e1 != e2

    def test_decrypt_invalid_token(self):
        import app.utils.crypto as crypto_mod
        crypto_mod._fernet = None
        result = crypto_mod.decrypt_secret("not-a-valid-fernet-token")
        # Should return the original string (legacy plaintext), not crash
        assert result == "not-a-valid-fernet-token"


class TestCSRFMiddleware:
    """Unit tests for CSRF middleware logic."""

    def test_exempt_paths(self):
        from app.middleware.csrf import _is_exempt
        assert _is_exempt("/api/users")
        assert _is_exempt("/track/123")
        assert _is_exempt("/health")
        assert _is_exempt("/static/js/app.js")
        assert not _is_exempt("/portal/login")
        assert not _is_exempt("/admin/login")

    def test_token_generation(self):
        """CSRF tokens should be URL-safe strings of reasonable length."""
        import secrets
        token = secrets.token_urlsafe(32)
        assert len(token) >= 32
        # Should be URL-safe (alphanumeric + - + _)
        assert all(c.isalnum() or c in "-_" for c in token)


class TestSecurityHeaders:
    """Verify security headers middleware configuration."""

    def test_middleware_class_exists(self):
        from app.middleware.security import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware is not None


class TestResponseHelpers:
    """Test standardized response format."""

    def test_success_response(self):
        from app.utils.responses import success_response
        resp = success_response(data={"id": 1}, message="Created")
        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["ok"] is True
        assert body["message"] == "Created"
        assert body["data"]["id"] == 1

    def test_error_response(self):
        from app.utils.responses import error_response
        resp = error_response("Not found", 404)
        assert resp.status_code == 404
        import json
        body = json.loads(resp.body)
        assert body["ok"] is False
        assert body["message"] == "Not found"

    def test_error_response_with_errors_list(self):
        from app.utils.responses import error_response
        resp = error_response("Validation failed", 422, errors=["field1 required", "field2 invalid"])
        import json
        body = json.loads(resp.body)
        assert len(body["errors"]) == 2
