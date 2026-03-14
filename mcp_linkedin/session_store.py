"""Cookie encryption, persistence and session expiration management."""

import json
import logging
import os
import time

from cryptography.fernet import Fernet

from .config import (
    COOKIE_EXPIRY_SECONDS,
    DIR_PERMISSIONS,
    FILE_PERMISSIONS,
    SESSIONS_DIR,
)

logger = logging.getLogger(__name__)


def setup_sessions_directory() -> bool:
    """Create sessions directory with restrictive permissions (owner-only)."""
    try:
        SESSIONS_DIR.mkdir(mode=DIR_PERMISSIONS, parents=True, exist_ok=True)
        os.chmod(SESSIONS_DIR, DIR_PERMISSIONS)
        logger.debug("Sessions directory ready at %s", SESSIONS_DIR)
        return True
    except Exception as e:
        logger.error("Failed to set up sessions directory: %s", e)
        return False


def _get_encryption_key() -> bytes:
    """Return Fernet key from env, key-file, or generate a new one."""
    key = os.getenv("COOKIE_ENCRYPTION_KEY")
    if key:
        return key.encode() if isinstance(key, str) else key

    key_file = SESSIONS_DIR / ".cookie_key"
    if key_file.exists():
        return key_file.read_bytes()

    new_key = Fernet.generate_key()
    setup_sessions_directory()
    key_file.write_bytes(new_key)
    os.chmod(key_file, FILE_PERMISSIONS)
    return new_key


async def save_cookies(page, platform: str) -> None:
    """Encrypt and persist browser cookies for *platform*."""
    cookies = await page.context.cookies()
    if not cookies or not isinstance(cookies, list):
        raise ValueError("Invalid cookie format")

    cookie_data = {"timestamp": int(time.time()), "cookies": cookies}

    if not setup_sessions_directory():
        raise RuntimeError("Failed to set up sessions directory")

    fernet = Fernet(_get_encryption_key())
    encrypted = fernet.encrypt(json.dumps(cookie_data).encode())

    cookie_file = SESSIONS_DIR / f"{platform}_cookies.json"
    cookie_file.write_bytes(encrypted)
    os.chmod(cookie_file, FILE_PERMISSIONS)


async def load_cookies(context, platform: str) -> bool:
    """Load and decrypt cookies into *context*. Returns True on success."""
    cookie_file = SESSIONS_DIR / f"{platform}_cookies.json"
    try:
        encrypted = cookie_file.read_bytes()
    except FileNotFoundError:
        return False

    try:
        fernet = Fernet(_get_encryption_key())
        cookie_data = json.loads(fernet.decrypt(encrypted))

        if int(time.time()) - cookie_data["timestamp"] > COOKIE_EXPIRY_SECONDS:
            cookie_file.unlink(missing_ok=True)
            return False

        await context.add_cookies(cookie_data["cookies"])
        return True
    except Exception:
        cookie_file.unlink(missing_ok=True)
        return False
