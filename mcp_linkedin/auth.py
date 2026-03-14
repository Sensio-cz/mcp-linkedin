"""LinkedIn authentication flows."""

import asyncio
import logging
import os

from .browser import BrowserSession
from .config import LOGIN_TIMEOUT

logger = logging.getLogger(__name__)


async def login_linkedin(
    username: str | None = None,
    password: str | None = None,
    ctx=None,
) -> dict:
    """Open LinkedIn login page for manual login.

    Credentials are optional — if provided they are pre-filled.
    """
    logger.info("Starting LinkedIn login")

    async with BrowserSession(platform="linkedin", headless=False) as session:
        try:
            page = await session.new_page()
            await page.set_viewport_size({"width": 1280, "height": 800})
            await page.goto("https://www.linkedin.com/login", wait_until="networkidle")

            if "feed" in page.url:
                await session.save_session(page)
                return {"status": "success", "message": "Already logged in"}

            if ctx:
                ctx.info("Please log in manually through the browser window...")
                ctx.info("The browser will wait for up to 5 minutes.")

            try:
                if username:
                    await page.fill("#username", username)
                if password:
                    await page.fill("#password", password)
            except Exception as e:
                logger.warning("Failed to pre-fill credentials: %s", e)

            try:
                await page.wait_for_url("**/feed/**", timeout=LOGIN_TIMEOUT)
                if ctx:
                    ctx.info("Login successful!")
                await session.save_session(page)
                await asyncio.sleep(3)
                return {"status": "success", "message": "Manual login successful"}
            except Exception:
                return {
                    "status": "error",
                    "message": "Login timeout. Please try again and complete login within 5 minutes.",
                }
        except Exception as e:
            logger.error("Login process error: %s", e)
            return {"status": "error", "message": f"Login process error: {e}"}


async def login_linkedin_secure(ctx=None) -> dict:
    """Login using credentials from environment variables."""
    username = os.getenv("LINKEDIN_USERNAME", "").strip() or None
    password = os.getenv("LINKEDIN_PASSWORD", "").strip() or None
    return await login_linkedin(username, password, ctx)
