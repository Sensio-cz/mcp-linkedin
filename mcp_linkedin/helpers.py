"""Shared utility functions."""

import hashlib
import json
import logging
import time

from .config import COMMENT_TRACKING_DIR

logger = logging.getLogger(__name__)


def report_progress(ctx, current: int, total: int, message: str | None = None):
    """Log progress to MCP context."""
    try:
        if message:
            ctx.info(message)
    except Exception as e:
        logger.error("Error reporting progress: %s", e)


def handle_notification(ctx, notification_type: str, params: dict | None = None):
    """Handle MCP lifecycle notifications."""
    try:
        if notification_type == "initialized":
            logger.info("MCP Server initialized")
            if ctx:
                ctx.info("Server initialized and ready")
        elif notification_type == "cancelled":
            reason = (params or {}).get("reason", "Unknown reason")
            logger.warning("Operation cancelled: %s", reason)
            if ctx:
                ctx.warning(f"Operation cancelled: {reason}")
        else:
            logger.debug("Notification: %s – %s", notification_type, params)
    except Exception as e:
        logger.error("Error handling notification: %s", e)


# ── Comment tracking persistence ──────────────────────────────────────────

def get_comment_tracking_dir():
    """Return (and ensure) the comment tracking directory."""
    COMMENT_TRACKING_DIR.mkdir(parents=True, exist_ok=True)
    return COMMENT_TRACKING_DIR


def post_url_to_key(post_url: str) -> str:
    """Convert a post URL to a safe filename key (MD5 hash)."""
    return hashlib.md5(post_url.encode()).hexdigest()


def load_tracked_comments(post_url: str) -> dict:
    """Load previously tracked comments for a post."""
    tracking_dir = get_comment_tracking_dir()
    tracking_file = tracking_dir / f"{post_url_to_key(post_url)}.json"
    if tracking_file.exists():
        with open(tracking_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"post_url": post_url, "comments": [], "last_checked": None}


def save_tracked_comments(post_url: str, data: dict):
    """Persist tracked comments for a post."""
    tracking_dir = get_comment_tracking_dir()
    tracking_file = tracking_dir / f"{post_url_to_key(post_url)}.json"
    with open(tracking_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
