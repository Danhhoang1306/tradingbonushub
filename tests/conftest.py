"""Shared pytest fixtures for TradingBonusHub tests."""
import os
import sys

import pytest

# Ensure app module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set test environment variables before any app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("FERNET_KEY", "dGVzdC1mZXJuZXQta2V5LWRvLW5vdC11c2U=")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DB_SERVER", "")
os.environ.setdefault("DB_NAME", "TestDB")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
