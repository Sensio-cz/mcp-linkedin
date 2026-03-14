"""FastMCP tool definitions — thin wrappers around linkedin_client functions."""

from fastmcp import FastMCP, Context

from .auth import login_linkedin as _login, login_linkedin_secure as _login_secure
from .browser import BrowserSession
from . import linkedin_client as client

mcp = FastMCP("linkedin")


# ── Auth ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def login_linkedin(
    username: str | None = None,
    password: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Open LinkedIn login page in browser for manual login.
    Username and password are optional - if not provided, user will need to enter them manually."""
    return await _login(username, password, ctx)


@mcp.tool()
async def login_linkedin_secure(ctx: Context | None = None) -> dict:
    """Open LinkedIn login page in browser for manual login using environment credentials as default values.

    Optional environment variables:
    - LINKEDIN_USERNAME: Your LinkedIn email/username (will be pre-filled if provided)
    - LINKEDIN_PASSWORD: Your LinkedIn password (will be pre-filled if provided)
    """
    return await _login_secure(ctx)


# ── Feed ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def browse_linkedin_feed(ctx: Context, count: int = 5) -> dict:
    """Browse LinkedIn feed and return recent posts.

    Args:
        ctx: MCP context for logging and progress reporting
        count: Number of posts to retrieve (default: 5)
    """
    async with BrowserSession(platform="linkedin") as session:
        return await client.browse_feed(session, ctx, count)


# ── Search ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_linkedin_profiles(query: str, ctx: Context, count: int = 5) -> dict:
    """Search for LinkedIn profiles matching a query."""
    async with BrowserSession(platform="linkedin") as session:
        return await client.search_profiles(session, ctx, query, count)


# ── Profile ────────────────────────────────────────────────────────────────

@mcp.tool()
async def view_linkedin_profile(profile_url: str, ctx: Context) -> dict:
    """Visit and extract data from a specific LinkedIn profile."""
    async with BrowserSession(platform="linkedin") as session:
        return await client.view_profile(session, ctx, profile_url)


@mcp.tool()
async def get_profile_posts(profile_url: str, ctx: Context, count: int = 10) -> dict:
    """Fetch recent posts/activity from a specific LinkedIn profile.

    Args:
        profile_url: LinkedIn profile URL (e.g. https://www.linkedin.com/in/jantobolik)
        ctx: MCP context for logging and progress reporting
        count: Number of posts to retrieve (default: 10, max: 50)
    """
    async with BrowserSession(platform="linkedin") as session:
        return await client.get_profile_posts(session, ctx, profile_url, count)


# ── Comments ───────────────────────────────────────────────────────────────

@mcp.tool()
async def get_post_comments(
    post_url: str, ctx: Context,
    save_to_file: bool = False, load_all: bool = True,
) -> dict:
    """Load all comments from a LinkedIn post.
    Expands threads, clicks 'load more', extracts author, content, timestamp,
    likes/reactions count, and reply count for each comment.
    Optionally saves to data/comment_tracking/ as JSON."""
    async with BrowserSession(platform="linkedin", headless=False) as session:
        return await client.get_post_comments(session, ctx, post_url, save_to_file, load_all)


@mcp.tool()
async def track_post_comments(
    post_url: str, ctx: Context,
    auto_refresh: bool = False,
    interval_seconds: int = 60,
    max_checks: int = 10,
) -> dict:
    """Track comments on a LinkedIn post — detect new comments since last check.

    First call loads all comments and saves them. Subsequent calls return only NEW comments.
    With auto_refresh=True, polls repeatedly at the given interval.

    Args:
        post_url: LinkedIn post URL
        ctx: MCP context for logging and progress reporting
        auto_refresh: If True, automatically re-check for new comments (default: False)
        interval_seconds: Seconds between checks when auto_refresh=True (default: 60, min: 30)
        max_checks: Maximum number of auto-refresh checks (default: 10, max: 50)
    """
    async with BrowserSession(platform="linkedin", headless=False) as session:
        return await client.track_post_comments(
            session, ctx, post_url, auto_refresh, interval_seconds, max_checks,
        )


# ── Post interaction ──────────────────────────────────────────────────────

@mcp.tool()
async def interact_with_linkedin_post(
    post_url: str, ctx: Context,
    action: str = "like", comment: str = None,
) -> dict:
    """Interact with a LinkedIn post (like, comment, read)."""
    async with BrowserSession(platform="linkedin", headless=False) as session:
        return await client.interact_with_post(session, ctx, post_url, action, comment)


# ── Profile viewers (NEW) ────────────────────────────────────────────────

@mcp.tool()
async def get_profile_viewers(
    ctx: Context,
    only_relevant: bool = True,
    only_not_connected: bool = True,
) -> dict:
    """Get people who viewed my LinkedIn profile, filtered by relevance.

    Returns viewers whose headline matches relevant keywords (AI, founders,
    developers, automation) and who are NOT already 1st-degree connections.

    Args:
        ctx: MCP context for logging and progress reporting
        only_relevant: If True, return only viewers matching relevant keywords (default: True)
        only_not_connected: If True, exclude 1st-degree connections (default: True)
    """
    async with BrowserSession(platform="linkedin", headless=False) as session:
        return await client.get_profile_viewers(session, ctx, only_relevant, only_not_connected)


@mcp.tool()
async def send_connection_request(
    profile_url: str, ctx: Context,
    note: str | None = None,
) -> dict:
    """Send a connection request to a LinkedIn profile.

    Args:
        profile_url: Full LinkedIn profile URL (e.g. https://www.linkedin.com/in/username)
        ctx: MCP context for logging and progress reporting
        note: Optional personalised message to include with the request
    """
    async with BrowserSession(platform="linkedin", headless=False) as session:
        return await client.send_connection_request(session, ctx, profile_url, note)
