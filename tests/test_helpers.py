"""Tests for helper utilities."""

import json
from unittest.mock import MagicMock

import pytest

from mcp_linkedin.helpers import (
    post_url_to_key,
    report_progress,
    load_tracked_comments,
    save_tracked_comments,
)


class TestPostUrlToKey:
    def test_returns_md5_hex(self):
        key = post_url_to_key("https://linkedin.com/posts/test-123")
        assert len(key) == 32  # MD5 hex digest length
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic(self):
        url = "https://linkedin.com/posts/abc"
        assert post_url_to_key(url) == post_url_to_key(url)

    def test_different_urls_different_keys(self):
        assert post_url_to_key("https://a.com") != post_url_to_key("https://b.com")


class TestReportProgress:
    def test_calls_ctx_info(self):
        ctx = MagicMock()
        report_progress(ctx, 5, 10, "halfway")
        ctx.info.assert_called_once_with("halfway")

    def test_no_message(self):
        ctx = MagicMock()
        report_progress(ctx, 5, 10)
        ctx.info.assert_not_called()

    def test_handles_error_gracefully(self):
        ctx = MagicMock()
        ctx.info.side_effect = RuntimeError("boom")
        # Should not raise
        report_progress(ctx, 1, 1, "msg")


class TestCommentTracking:
    def test_load_missing_returns_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mcp_linkedin.helpers.COMMENT_TRACKING_DIR", tmp_path)
        result = load_tracked_comments("https://example.com/post")
        assert result["comments"] == []
        assert result["last_checked"] is None

    def test_save_then_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mcp_linkedin.helpers.COMMENT_TRACKING_DIR", tmp_path)
        url = "https://linkedin.com/posts/xyz"
        data = {"post_url": url, "comments": [{"author": "A", "content": "hi"}], "last_checked": 12345}
        save_tracked_comments(url, data)
        loaded = load_tracked_comments(url)
        assert loaded["comments"][0]["author"] == "A"
        assert loaded["last_checked"] == 12345
