"""Centralized configuration constants."""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = BASE_DIR / "sessions"
DATA_DIR = BASE_DIR / "data"
COMMENT_TRACKING_DIR = DATA_DIR / "comment_tracking"

# ── File permissions ───────────────────────────────────────────────────────
DIR_PERMISSIONS = 0o700   # rwx------  (owner only)
FILE_PERMISSIONS = 0o600  # rw-------  (owner only)

# ── Browser ────────────────────────────────────────────────────────────────
BROWSER_VIEWPORT = {"width": 1280, "height": 800}
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/96.0.4664.110 Safari/537.36"
)
BROWSER_LAUNCH_ARGS = [
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--start-maximized",
]
BROWSER_LAUNCH_TIMEOUT = 30_000        # ms
BROWSER_MAX_RETRIES = 3
BROWSER_SUB_ATTEMPTS = 3
BROWSER_SUB_ATTEMPT_DELAY = 2          # seconds

# ── Navigation / scraping ─────────────────────────────────────────────────
NAV_TIMEOUT = 60_000                   # ms – page.goto
SELECTOR_TIMEOUT = 10_000              # ms – wait_for_selector default
SELECTOR_TIMEOUT_LONG = 60_000         # ms – comment post load
LOGIN_TIMEOUT = 300_000                # ms – 5 min manual login
SCROLL_DELAY = 1_000                   # ms between scrolls
SCROLL_DELAY_COMMENTS = 1_500          # ms between comment loads
MAX_SCROLL_FEED = 20
MAX_SCROLL_POSTS = 50
MAX_COMMENT_LOAD_ITERATIONS = 20
MAX_REPLY_EXPAND_PASSES = 3
MAX_REPLY_BUTTONS_PER_PASS = 50

# ── Cookie session ─────────────────────────────────────────────────────────
COOKIE_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days

# ── Comment tracking ──────────────────────────────────────────────────────
TRACK_MIN_INTERVAL = 30                # seconds
TRACK_MAX_CHECKS = 50

# ── Profile viewers ───────────────────────────────────────────────────────
RELEVANT_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
    "automation", "automat",  # covers CZ "automatizace" too
    "ceo", "founder", "owner", "majitel", "jednatel", "spolumajitel",
    "cto", "coo", "managing director", "ředitel",
    "developer", "engineer", "vývojář", "programátor", "software",
    "data scientist", "data engineer", "devops", "sre",
]
