"""Standalone přihlášení na LinkedIn - otevře prohlížeč, uloží session."""
import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from cryptography.fernet import Fernet

load_dotenv(Path(__file__).parent / '.env')

async def main():
    (Path(__file__).parent / 'sessions').mkdir(exist_ok=True)
    print("Otevírám prohlížeč - přihlas se na LinkedIn...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/96.0.4664.110'
        )
        page = await context.new_page()
        await page.goto('https://www.linkedin.com/login', wait_until='networkidle')
        
        if 'feed' in page.url:
            print("Už jsi přihlášen.", flush=True)
            await browser.close()
            return
        
        # Předvyplnit credentials
        username = os.getenv('LINKEDIN_USERNAME', '').strip()
        password = os.getenv('LINKEDIN_PASSWORD', '').strip()
        if username:
            await page.fill('#username', username)
        if password:
            await page.fill('#password', password)
        
        print("Přihlas se v prohlížeči (max 5 min)...", flush=True)
        try:
            await page.wait_for_url('**/feed/**', timeout=300000)
            print("Přihlášení úspěšné! Ukládám session...", flush=True)
            
            # Uložit cookies
            cookies = await context.cookies()
            key_file = Path(__file__).parent / 'sessions' / '.cookie_key'
            key = os.getenv('COOKIE_ENCRYPTION_KEY')
            if not key:
                if key_file.exists():
                    key = key_file.read_bytes()
                else:
                    key = Fernet.generate_key()
                    key_file.write_bytes(key)
            elif isinstance(key, str):
                key = key.encode()
            f = Fernet(key)
            cookie_data = {"timestamp": int(time.time()), "cookies": cookies}
            cookie_file = Path(__file__).parent / 'sessions' / 'linkedin_cookies.json'
            with open(cookie_file, 'wb') as out:
                out.write(f.encrypt(json.dumps(cookie_data).encode()))
            
            print("Session uložena. Příště bude browse fungovat bez přihlášení.", flush=True)
        except Exception as e:
            print(f"Timeout nebo chyba: {e}", flush=True)
        
        await asyncio.sleep(2)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
