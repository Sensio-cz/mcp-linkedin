"""
Standalone načtení LinkedIn feedu - bez fastmcp (obchází jsonschema problém na sync discích).
Pouze: playwright, python-dotenv, cryptography
"""
import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(Path(__file__).parent / '.env')

async def load_cookies(context):
    """Načti uložené cookies."""
    (Path(__file__).parent / 'sessions').mkdir(exist_ok=True)
    try:
        from cryptography.fernet import Fernet
        cookie_file = Path(__file__).parent / 'sessions' / 'linkedin_cookies.json'
        key_file = Path(__file__).parent / 'sessions' / '.cookie_key'
        if not cookie_file.exists():
            return False
        with open(cookie_file, 'rb') as f:
            encrypted_data = f.read()
        key = os.getenv('COOKIE_ENCRYPTION_KEY')
        if not key and key_file.exists():
            key = key_file.read_bytes()
        if not key:
            return False
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        cookie_data = json.loads(fernet.decrypt(encrypted_data))
        if int(time.time()) - cookie_data["timestamp"] > 86400:
            cookie_file.unlink()
            return False
        await context.add_cookies(cookie_data["cookies"])
        return True
    except Exception:
        return False

async def main():
    print("Načítám LinkedIn feed...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/96.0.4664.110'
        )
        await load_cookies(context)
        page = await context.new_page()
        await page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded', timeout=30000)
        
        if 'login' in page.url or 'authwall' in page.url:
            print(json.dumps({"status": "error", "message": "Not logged in. Spusť login_cli.py pro přihlášení."}, indent=2, ensure_ascii=False))
            await browser.close()
            return
        
        posts = []
        for i in range(10):
            try:
                try:
                    await page.wait_for_selector('[data-urn^="urn:li:activity:"]', timeout=5000)
                except:
                    await page.wait_for_selector('.feed-shared-update-v2', timeout=5000)
                new_posts = await page.evaluate('''() => {
                    let nodes = document.querySelectorAll('[data-urn^="urn:li:activity:"]');
                    if (!nodes.length) nodes = document.querySelectorAll('.feed-shared-update-v2');
                    return Array.from(nodes).map(post => {
                        const getText = (sel) => {
                            const el = post.querySelector(sel);
                            return el ? el.innerText.trim() : '';
                        };
                        const author = getText('.update-components-actor__name') || getText('.feed-shared-actor__name') || getText('[class*="actor__name"]');
                        const headline = getText('.update-components-actor__description') || getText('.feed-shared-actor__description') || getText('[class*="actor__description"]');
                        const content = getText('.feed-shared-inline-show-more-text') || getText('.update-components-text') || getText('.feed-shared-text') || getText('[class*="update-components-text"]') || getText('[class*="feed-shared-text"]');
                        const timestamp = getText('.update-components-actor__sub-description') || getText('.feed-shared-actor__sub-description') || getText('[class*="sub-description"]');
                        const likes = getText('.social-details-social-counts__reactions-count') || getText('[class*="reactions-count"]') || '0';
                        return { author: author || 'Unknown', headline, content, timestamp, likes };
                    });
                }''')
                for p in new_posts:
                    if p not in posts:
                        posts.append(p)
                if len(posts) >= 10:
                    break
                await page.evaluate('window.scrollBy(0, 800)')
                await page.wait_for_timeout(1000)
            except Exception as e:
                print(f"Varování: {e}", file=__import__('sys').stderr)
        
        await browser.close()
        out = json.dumps({"status": "success", "posts": posts[:10], "count": len(posts)}, indent=2, ensure_ascii=True)
        print(out)

if __name__ == "__main__":
    asyncio.run(main())
