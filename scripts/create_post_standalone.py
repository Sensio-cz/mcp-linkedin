"""
Zveřejnění příspěvku na LinkedIn.
Otevře prohlížeč, vyplní text a zveřejní. Uživatel vidí průběh a může zrušit.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(Path(__file__).parent / '.env')

async def load_cookies(context):
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
            return False
        await context.add_cookies(cookie_data["cookies"])
        return True
    except Exception:
        return False

async def create_post(content: str, dry_run: bool = False):
    """Vytvoří příspěvek na LinkedIn. dry_run=True jen otevře prohlížeč bez odeslání."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/96.0.4664.110'
        )
        await load_cookies(context)
        page = await context.new_page()
        await page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded', timeout=30000)
        
        if 'login' in page.url or 'authwall' in page.url:
            print('{"status": "error", "message": "Not logged in. Spusť login_standalone.py"}')
            await browser.close()
            return
        
        await page.wait_for_timeout(3000)
        
        # Kliknout na "Začít příspěvek" / "Start a post" - různé selektory
        clicked = False
        for sel in [
            'div.share-box-feed__open-up',
            'div[class*="share-box"]',
            '[placeholder*="Start a post"]',
            '[placeholder*="Začít příspěvek"]',
            '[placeholder*="What do you want to talk about"]',
            '[data-placeholder*="post"]',
            'button:has-text("Start a post")',
            'span:has-text("Start a post")',
            'span:has-text("Začít příspěvek")',
        ]:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(timeout=3000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            # Zkusit kliknout na první contenteditable v share oblasti
            await page.evaluate('''() => {
                const box = document.querySelector('[class*="share-box"]') || document.querySelector('[class*="feed-shared"]');
                if (box) {
                    const editable = box.querySelector('[contenteditable="true"]');
                    if (editable) editable.click();
                }
            }''')
        
        await page.wait_for_timeout(2500)
        
        # Vyplnit text do editoru
        editor_sel = 'div[contenteditable="true"][role="textbox"], .ql-editor[contenteditable="true"], div[contenteditable="true"]'
        editor = page.locator(editor_sel).first
        await editor.click()
        await editor.fill('')
        await editor.type(content, delay=30)
        await page.wait_for_timeout(500)
        
        if dry_run:
            print('Dry run: text vyplněn, prohlížeč zůstane otevřen. Zavři ho ručně.')
            await asyncio.sleep(300)  # 5 min na kontrolu
            await browser.close()
            return
        
        # Kliknout na "Post" / "Zveřejnit"
        try:
            post_btn = page.locator('button:has-text("Post"), button:has-text("Zveřejnit"), button:has-text("Publikovat"), [aria-label*="Post"]').first
            await post_btn.click(timeout=5000)
            await page.wait_for_timeout(3000)
            print('{"status": "success", "message": "Příspěvek zveřejněn."}')
        except Exception as e:
            print(f'{"status": "error", "message": "Nepodařilo se kliknout na Zveřejnit. Zkus to ručně.", "error": "{str(e)}"}')
        
        await asyncio.sleep(2)
        await browser.close()

if __name__ == "__main__":
    content = sys.argv[1] if len(sys.argv) > 1 else ""
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    if not content:
        print("Použití: python create_post_standalone.py \"Text příspěvku\" [--dry-run]")
        print("  --dry-run: vyplní text ale neodešle (pro kontrolu)")
        sys.exit(1)
    asyncio.run(create_post(content, dry_run=dry_run))
