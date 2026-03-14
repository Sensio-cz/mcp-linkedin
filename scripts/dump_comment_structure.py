#!/usr/bin/env python3
"""Debug: dump HTML structure of first few comments for selector development.
Usage: python dump_comment_structure.py <post_url>"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linkedin_browser_mcp import BrowserSession, load_cookies
from playwright.async_api import async_playwright


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("Usage: python dump_comment_structure.py <post_url>")
        sys.exit(1)
    base_url = url.split("?")[0].rstrip("/")

    async with BrowserSession(platform="linkedin", headless=False) as session:
        page = await session.new_page(base_url)
        if "login" in page.url:
            print("Not logged in. Run login_standalone.py first.")
            return
        await page.wait_for_selector(".feed-shared-update-v2", timeout=60000)
        await page.wait_for_timeout(3000)

        # Click to expand comments
        try:
            btn = page.locator("button.social-details-social-counts__comments, [class*='comments-count']").first
            await btn.click(timeout=5000)
            await page.wait_for_timeout(3000)
        except Exception:
            pass

        # Dump HTML of first 3 comment CONTAINER elements (not __main-content etc)
        html_dump = await page.evaluate(
            """() => {
            const els = document.querySelectorAll('.comments-comment-item, article[data-id]');
            const filtered = Array.from(els).filter(el => !(el.className || '').includes('comments-comment-item__'));
            return filtered.slice(0, 3).map((el, i) => ({
                index: i,
                className: el.className,
                innerHTML: el.innerHTML.substring(0, 5000),
                innerText: el.innerText.substring(0, 500)
            }));
        }"""
        )

        out = Path(__file__).parent / "data" / "comment_structure_dump.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for item in html_dump:
                f.write(f"\n=== Comment {item['index']} ===\n")
                f.write(f"Class: {item['className']}\n")
                f.write(f"innerText (first 500):\n{item['innerText']}\n")
                f.write(f"innerHTML (first 3000):\n{item['innerHTML']}\n")
        print(f"Dump saved to {out}")
        await session.save_session(page)


if __name__ == "__main__":
    asyncio.run(main())
