"""BrowserSession context manager — Playwright lifecycle with retry logic."""

import asyncio
import logging

from playwright.async_api import async_playwright

from .config import (
    BROWSER_LAUNCH_ARGS,
    BROWSER_LAUNCH_TIMEOUT,
    BROWSER_MAX_RETRIES,
    BROWSER_SUB_ATTEMPTS,
    BROWSER_SUB_ATTEMPT_DELAY,
    BROWSER_USER_AGENT,
    BROWSER_VIEWPORT,
    NAV_TIMEOUT,
)
from .session_store import load_cookies, save_cookies, setup_sessions_directory

logger = logging.getLogger(__name__)


class BrowserSession:
    """Async context manager for Playwright browser sessions with cookie persistence."""

    def __init__(
        self,
        platform: str = "linkedin",
        headless: bool = True,
        launch_timeout: int = BROWSER_LAUNCH_TIMEOUT,
        max_retries: int = BROWSER_MAX_RETRIES,
    ):
        self.platform = platform
        self.headless = headless
        self.launch_timeout = launch_timeout
        self.max_retries = max_retries
        self.playwright = None
        self.browser = None
        self.context = None
        self._closed = False

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def __aenter__(self):
        if not setup_sessions_directory():
            raise RuntimeError("Failed to set up sessions directory")

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            if self._closed:
                break
            try:
                await self._cleanup()
                self.playwright = await asyncio.wait_for(
                    async_playwright().start(),
                    timeout=self.launch_timeout / 1000,
                )
                self.browser = await self._launch_browser()
                self.context = await self.browser.new_context(
                    viewport=BROWSER_VIEWPORT,
                    user_agent=BROWSER_USER_AGENT,
                )
                try:
                    loaded = await load_cookies(self.context, self.platform)
                    if loaded:
                        logger.info("Existing session loaded")
                except Exception as e:
                    logger.warning("Error loading cookies: %s", e)
                return self
            except Exception as e:
                last_error = e
                logger.error("Browser init attempt %d failed: %s", attempt, e)
                await self._cleanup()
                if attempt < self.max_retries and not self._closed:
                    await asyncio.sleep(2 * attempt)

        raise RuntimeError(
            f"Failed to initialise browser after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._closed = True
        await self._cleanup()

    # ── public helpers ─────────────────────────────────────────────────────

    async def new_page(self, url=None):
        if self._closed:
            raise RuntimeError("Browser session has been closed")
        page = await self.context.new_page()
        if url:
            await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        return page

    async def save_session(self, page):
        if self._closed:
            raise RuntimeError("Browser session has been closed")
        await save_cookies(page, self.platform)

    # ── internal ───────────────────────────────────────────────────────────

    async def _launch_browser(self):
        for sub in range(1, BROWSER_SUB_ATTEMPTS + 1):
            try:
                return await self.playwright.chromium.launch(
                    headless=self.headless,
                    timeout=self.launch_timeout,
                    args=BROWSER_LAUNCH_ARGS,
                )
            except Exception as e:
                logger.error("Browser launch sub-attempt %d failed: %s", sub, e)
                if sub < BROWSER_SUB_ATTEMPTS:
                    await asyncio.sleep(BROWSER_SUB_ATTEMPT_DELAY)
        raise RuntimeError("Failed to launch browser after sub-attempts")

    async def _cleanup(self):
        for resource, name in [(self.browser, "browser"), (self.playwright, "playwright")]:
            if resource:
                try:
                    await (resource.close() if name == "browser" else resource.stop())
                except Exception as e:
                    logger.error("Error closing %s: %s", name, e)
        self.browser = self.playwright = self.context = None
