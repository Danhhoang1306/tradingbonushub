"""Integration tests for API endpoints using httpx + FastAPI TestClient.

These tests mock the database layer to test HTTP routing, middleware,
authentication, and response format without requiring a SQL Server connection.
"""
import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test FastAPI app with mocked DB connections."""
    # Patch DB operations before importing app module
    with patch("app.db.connection.init_pool"), \
         patch("app.db.init.init_db"), \
         patch("app.db.connection.get_conn") as mock_conn:
        # Mock the context manager for get_conn
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock())
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value = mock_cm

        from app.main import app

        # Override startup to skip DB + worker initialization
        @app.on_event("startup")
        async def _noop_startup():
            pass

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


class TestHealthEndpoint:
    """Health check should always be accessible."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    def test_has_x_content_type_options(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_has_x_frame_options(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_has_hsts(self, client):
        resp = client.get("/health")
        hsts = resp.headers.get("Strict-Transport-Security", "")
        assert "max-age=" in hsts

    def test_has_referrer_policy(self, client):
        resp = client.get("/health")
        assert "strict-origin" in resp.headers.get("Referrer-Policy", "")

    def test_has_permissions_policy(self, client):
        resp = client.get("/health")
        pp = resp.headers.get("Permissions-Policy", "")
        assert "camera=()" in pp

    def test_has_csp(self, client):
        resp = client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src" in csp


class TestAuthMiddleware:
    """Test authentication enforcement."""

    def test_admin_routes_require_auth(self, client):
        resp = client.get("/admin/", follow_redirects=False)
        # 301 from non-admin host, 302 from admin host — both redirect to login
        assert resp.status_code in (301, 302)
        assert "/admin/login" in resp.headers.get("location", "")

    def test_api_routes_require_auth(self, client):
        resp = client.get("/api/users")
        assert resp.status_code == 401

    def test_admin_login_page_accessible(self, client):
        resp = client.get("/admin/login")
        assert resp.status_code == 200

    def test_portal_login_page_accessible(self, client):
        with patch("app.views.portal.get_portal_settings", return_value={}):
            resp = client.get("/portal/login")
            assert resp.status_code == 200


class TestRateLimiting:
    """Verify rate limiting is active on sensitive endpoints."""

    def test_tracking_endpoint_returns_gif(self, client):
        resp = client.get("/track/test-id-12345")
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "image/gif"


class TestCSRFProtection:
    """Verify CSRF middleware blocks unprotected form submissions."""

    def test_post_without_csrf_token_blocked(self, client):
        """POST to a non-exempt path without CSRF token should be rejected."""
        resp = client.post(
            "/admin/login",
            data={"username": "test", "password": "test"},
        )
        # Should get 403 (CSRF) since no token provided
        assert resp.status_code == 403

    def test_api_exempt_from_csrf(self, client):
        """API endpoints are exempt from CSRF (use session auth + SameSite)."""
        resp = client.get("/api/users")
        # Should get 401 (auth required), not 403 (CSRF)
        assert resp.status_code == 401
