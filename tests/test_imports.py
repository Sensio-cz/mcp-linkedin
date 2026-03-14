"""Smoke tests — verify all modules import without errors."""

import pytest


def test_import_config():
    from mcp_linkedin import config
    assert config.DIR_PERMISSIONS == 0o700
    assert config.FILE_PERMISSIONS == 0o600


def test_import_selectors():
    from mcp_linkedin import selectors
    assert selectors.FEED_POST == ".feed-shared-update-v2"
    assert selectors.VIEW_REPLIES_RE is not None


def test_import_session_store():
    from mcp_linkedin import session_store
    assert callable(session_store.setup_sessions_directory)
    assert callable(session_store.save_cookies)
    assert callable(session_store.load_cookies)


def test_import_browser():
    from mcp_linkedin.browser import BrowserSession
    assert BrowserSession is not None


def test_import_auth():
    from mcp_linkedin import auth
    assert callable(auth.login_linkedin)
    assert callable(auth.login_linkedin_secure)


def test_import_helpers():
    from mcp_linkedin import helpers
    assert callable(helpers.report_progress)
    assert callable(helpers.post_url_to_key)
    assert callable(helpers.load_tracked_comments)


def test_import_linkedin_client():
    from mcp_linkedin import linkedin_client
    assert callable(linkedin_client.browse_feed)
    assert callable(linkedin_client.search_profiles)
    assert callable(linkedin_client.get_post_comments)
    assert callable(linkedin_client.get_profile_viewers)
    assert callable(linkedin_client.send_connection_request)


def test_import_mcp_tools():
    from mcp_linkedin import mcp_tools
    assert mcp_tools.mcp is not None
