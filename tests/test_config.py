"""Tests for configuration defaults."""

from mcp_linkedin.config import (
    BROWSER_LAUNCH_ARGS,
    BROWSER_MAX_RETRIES,
    COOKIE_EXPIRY_SECONDS,
    DIR_PERMISSIONS,
    FILE_PERMISSIONS,
    MAX_SCROLL_FEED,
    RELEVANT_KEYWORDS,
    TRACK_MIN_INTERVAL,
)


def test_permissions_restrictive():
    assert DIR_PERMISSIONS == 0o700
    assert FILE_PERMISSIONS == 0o600


def test_cookie_expiry_is_7_days():
    assert COOKIE_EXPIRY_SECONDS == 604800


def test_browser_retries_positive():
    assert BROWSER_MAX_RETRIES >= 1


def test_browser_args_contain_no_sandbox():
    assert "--no-sandbox" in BROWSER_LAUNCH_ARGS


def test_max_scroll_feed():
    assert MAX_SCROLL_FEED >= 5


def test_track_min_interval():
    assert TRACK_MIN_INTERVAL >= 30


def test_relevant_keywords_not_empty():
    assert len(RELEVANT_KEYWORDS) > 5
    assert "ai" in RELEVANT_KEYWORDS
    assert "developer" in RELEVANT_KEYWORDS
    assert "ceo" in RELEVANT_KEYWORDS
