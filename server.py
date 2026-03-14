"""MCP LinkedIn Server — entry point.

Usage (Cursor / CLI):
    python server.py
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from mcp_linkedin.helpers import handle_notification
from mcp_linkedin.mcp_tools import mcp
from mcp_linkedin.session_store import setup_sessions_directory

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# ── Bootstrap ──────────────────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    logger.debug("Loaded environment from %s", env_path)

setup_sessions_directory()

# ── Run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        handle_notification(None, "initialized")
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        handle_notification(None, "cancelled", {"reason": "Server stopped by user"})
        logger.info("Server stopped by user")
    except Exception as e:
        handle_notification(None, "cancelled", {"reason": str(e)})
        logger.error("Server error: %s", e, exc_info=True)
        sys.exit(1)
