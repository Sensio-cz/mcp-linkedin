"""Tests for session_store — cookie encryption/decryption and expiration."""

import json
import os
import time
from unittest.mock import AsyncMock, patch

import pytest

from mcp_linkedin.config import COOKIE_EXPIRY_SECONDS, FILE_PERMISSIONS
from mcp_linkedin.session_store import (
    _get_encryption_key,
    setup_sessions_directory,
)


class TestSetupSessionsDirectory:
    def test_creates_directory(self, tmp_path):
        sessions = tmp_path / "sessions"
        with patch("mcp_linkedin.session_store.SESSIONS_DIR", sessions):
            assert setup_sessions_directory() is True
            assert sessions.exists()
            assert sessions.is_dir()

    def test_permissions_are_restrictive(self, tmp_path):
        sessions = tmp_path / "sessions"
        with patch("mcp_linkedin.session_store.SESSIONS_DIR", sessions):
            setup_sessions_directory()
            mode = os.stat(sessions).st_mode & 0o777
            assert mode == 0o700


class TestEncryptionKey:
    def test_generates_key_file(self, tmp_path):
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        with (
            patch("mcp_linkedin.session_store.SESSIONS_DIR", sessions),
            patch.dict(os.environ, {}, clear=True),
        ):
            # Remove COOKIE_ENCRYPTION_KEY if present
            os.environ.pop("COOKIE_ENCRYPTION_KEY", None)
            key = _get_encryption_key()
            assert len(key) > 0
            assert (sessions / ".cookie_key").exists()

    def test_uses_env_var(self, tmp_path):
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"COOKIE_ENCRYPTION_KEY": test_key}):
            key = _get_encryption_key()
            assert key == test_key.encode()

    def test_reuses_existing_key_file(self, tmp_path):
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        key_file = sessions / ".cookie_key"
        key_file.write_bytes(b"existing-key-content")
        with (
            patch("mcp_linkedin.session_store.SESSIONS_DIR", sessions),
            patch.dict(os.environ, {}, clear=True),
        ):
            os.environ.pop("COOKIE_ENCRYPTION_KEY", None)
            key = _get_encryption_key()
            assert key == b"existing-key-content"


class TestCookieExpiry:
    def test_expiry_constant(self):
        assert COOKIE_EXPIRY_SECONDS == 7 * 24 * 3600
