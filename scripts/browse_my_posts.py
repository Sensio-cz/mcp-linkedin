"""
Načtení vlastních příspěvků z LinkedIn profilu (sekce Aktivita).
Rozšířená verze: datum, typ příspěvku, pořadové číslo, maximum informací.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(Path(__file__).parent / '.env')


def decode_linkedin_timestamp(activity_id: int) -> str | None:
    """Z activity ID (Snowflake) zkusit dekódovat datum publikace."""
    try:
        # LinkedIn Snowflake: prvních 41 bitů = timestamp v ms od epochy
        ts_ms = activity_id >> 22
        if ts_ms < 1e12:  # pravděpodobně sekundy
            ts_ms = ts_ms * 1000
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")  # UTC
    except Exception:
        return None

# Cesta k datům mimo repo
DATA_DIR = Path(os.getenv('LINKEDIN_POSTS_DATA_PATH', r'C:\temp\mcp-linkedin\data'))


def get_output_file(profile_slug: str | None) -> Path:
    """Výstupní soubor podle profilu."""
    base = 'linkedin-posts-raw'
    if profile_slug and profile_slug != 'jantobolik':
        return DATA_DIR / f'{base}-{profile_slug}.json'
    return DATA_DIR / f'{base}.json'

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

async def main():
    save_to_file = '--save' in sys.argv or '-s' in sys.argv
    max_scrolls = 500  # pro ~400 příspěvků potřebujeme více scrollů
    stop_on_2y = True  # zastavit když uvidíme "2 roky" / "2y"
    scroll_wait_ms = 3500  # delší čekání pro načtení starších příspěvků

    # --profile / -p janastepanikova pro jiný profil
    profile_arg = None
    for i, a in enumerate(sys.argv):
        if a in ('--profile', '-p') and i + 1 < len(sys.argv):
            profile_arg = sys.argv[i + 1].strip().lstrip('/').split('/')[-1]
            break
        if a.startswith('--profile='):
            profile_arg = a.split('=', 1)[1].strip().lstrip('/').split('/')[-1]
            break

    print("Načítám příspěvky z profilu (až 2 roky zpět)...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/96.0.4664.110'
        )
        await load_cookies(context)
        page = await context.new_page()
        profile_slug = profile_arg or os.getenv('LINKEDIN_PROFILE', '').strip()
        if not profile_slug and os.getenv('LINKEDIN_USERNAME'):
            email = os.getenv('LINKEDIN_USERNAME', '').lower()
            if 'tobolik' in email:
                profile_slug = 'jantobolik'
        if profile_slug:
            activity_url = f'https://www.linkedin.com/in/{profile_slug}/recent-activity/all/'
            print(f"  Profil: linkedin.com/in/{profile_slug}", flush=True)
            await page.goto(activity_url, wait_until='domcontentloaded', timeout=30000)
        else:
            await page.goto('https://www.linkedin.com/in/me/', wait_until='domcontentloaded', timeout=30000)

        if 'login' in page.url or 'authwall' in page.url:
            print(json.dumps({"status": "error", "message": "Not logged in."}, indent=2, ensure_ascii=True))
            await browser.close()
            return

        profile_url = page.url
        if not profile_slug and '/in/' in profile_url and '/recent-activity/' not in profile_url:
            parts = profile_url.rstrip('/').split('/in/')
            if len(parts) > 1:
                slug = parts[1].split('/')[0]
                activity_url = f'https://www.linkedin.com/in/{slug}/recent-activity/all/'
                await page.goto(activity_url, wait_until='domcontentloaded', timeout=30000)

        await page.wait_for_timeout(5000)

        # Kliknout na "Zobrazit celou aktivitu" / "Show all activity" pokud existuje
        try:
            show_all = page.locator('button:has-text("Zobrazit celou aktivitu"), button:has-text("Show all activity"), [aria-label*="Show all"], [aria-label*="Zobrazit celou"]')
            if await show_all.count() > 0:
                await show_all.first.click()
                await page.wait_for_timeout(3000)
                print("  Kliknuto na Zobrazit celou aktivitu", flush=True)
        except Exception:
            pass

        # Rozbalit "Více" / "See more"
        await page.evaluate('''() => {
            document.querySelectorAll('.feed-shared-inline-show-more-text').forEach(el => {
                el.style.setProperty('max-height', 'none', 'important');
                el.style.setProperty('overflow', 'visible', 'important');
            });
        }''')
        await page.wait_for_timeout(500)

        for _ in range(3):
            await page.evaluate('''() => {
                const spans = document.querySelectorAll('span');
                spans.forEach(s => {
                    const t = (s.textContent || '').trim();
                    if ((t === '…více' || t === 'více' || t === '…more' || t === 'more' || t === 'See more') && s.offsetParent) {
                        s.click();
                    }
                });
            }''')
            await page.wait_for_timeout(1200)

        # Načíst příspěvky s mnoha scrolly
        seen_contents = set()
        posts = []
        reached_2y = False

        for scroll in range(max_scrolls):
            try:
                result = await page.evaluate('''() => {
                    let nodes = document.querySelectorAll('[data-urn^="urn:li:activity:"]');
                    if (!nodes.length) nodes = document.querySelectorAll('.feed-shared-update-v2');
                    const getText = (el, sel) => {
                        const e = el.querySelector(sel);
                        return e ? e.innerText.trim() : '';
                    };
                    const getTimestamp = (post) => {
                        const sel = post.querySelector('[class*="sub-description"]');
                        if (!sel) return '';
                        const spans = sel.querySelectorAll('span');
                        for (const s of spans) {
                            const t = (s.textContent || '').trim();
                            if (/^(\\d+\\s*(hod|h|min|m|den|d|týden|w|měsíc|mo|rok|y)|Edited|Upraveno)/.test(t) || /^(\\d+\\s*(hodin|dní|týdnů|měsíců|roků))/.test(t)) return t;
                        }
                        return sel.innerText.trim().split('\\n')[0] || '';
                    };
                    const detectType = (post) => {
                        const types = [];
                        if (post.querySelector('[data-poll], .poll, [class*="poll"]')) types.push('anketa');
                        if (post.querySelector('video, [data-video], [class*="video"]')) types.push('video');
                        if (post.querySelector('.feed-shared-image__container, img[data-ghost-url]')) types.push('obrázek');
                        const imgs = post.querySelectorAll('.feed-shared-image__container, [class*="carousel"] img');
                        if (imgs.length > 1) types.push('carousel');
                        if (post.querySelector('[class*="document"], [data-document]')) types.push('dokument');
                        if (post.querySelector('a[href*="/pulse/"], [class*="article"]')) types.push('článek');
                        return types.length ? types.join(', ') : 'text';
                    };
                    const items = Array.from(nodes).map(post => {
                        const container = post.closest('.feed-shared-update-v2') || post;
                        const content = getText(container, '.feed-shared-inline-show-more-text') || getText(container, '.update-components-text') || getText(container, '.feed-shared-text') || getText(container, '[class*="update-components-text"]');
                        const urnEl = (post.hasAttribute && post.hasAttribute('data-urn')) ? post : (post.querySelector('[data-urn^="urn:li:activity:"]') || post.closest('[data-urn^="urn:li:activity:"]'));
                        const urn = urnEl ? (urnEl.getAttribute('data-urn') || '') : '';
                        const activityId = urn.match(/urn:li:activity:(\\d+)/)?.[1] || '';
                        return {
                            content,
                            timestamp: getTimestamp(container),
                            timestamp_raw: getText(container, '[class*="sub-description"]'),
                            likes: getText(container, '[class*="reactions-count"]') || '0',
                            comments: getText(container, '[class*="comments-count"]') || '',
                            urn,
                            activity_id: activityId,
                            type: detectType(container)
                        };
                    }).filter(p => p.content.length > 20);
                    const allTimestamps = items.map(i => i.timestamp + ' ' + i.timestamp_raw).join(' ');
                    return { items, allTimestamps };
                }''')

                new_items = result.get('items', [])
                all_ts = result.get('allTimestamps', '')

                added = 0
                for p in new_items:
                    key = (p['content'][:100], p['timestamp'])
                    if key not in seen_contents:
                        seen_contents.add(key)
                        # Dekódovat datum z activity ID
                        aid = p.get('activity_id')
                        if aid:
                            try:
                                p['published_at'] = decode_linkedin_timestamp(int(aid))
                            except Exception:
                                p['published_at'] = None
                        else:
                            p['published_at'] = None
                        posts.append(p)
                        added += 1

                # Zastavit při "2 roky" / "2y" / "2 yr"
                if stop_on_2y and ('2 roky' in all_ts or '2 roků' in all_ts or '2y' in all_ts or '2 yr' in all_ts or '2 years' in all_ts):
                    reached_2y = True
                    print(f"  Scroll {scroll+1}: dosaženo ~2 roky, zastavuji. Celkem {len(posts)} příspěvků.", flush=True)
                    break

                if (scroll + 1) % 10 == 0:
                    print(f"  Scroll {scroll+1}/{max_scrolls}: {len(posts)} příspěvků", flush=True)

                if added == 0 and scroll > 50:
                    # Žádné nové příspěvky po dlouhé sérii scrollů (LinkedIn limit ~500)
                    print(f"  Scroll {scroll+1}: žádné nové příspěvky, zastavuji.", flush=True)
                    break

                # Scroll na konec stránky pro načtení dalších příspěvků
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(scroll_wait_ms)

            except Exception as e:
                print(f"  Varování scroll {scroll+1}: {e}", flush=True)

        await browser.close()

        # Přidat pořadové číslo (no 1 = nejnovější)
        for i, p in enumerate(posts, 1):
            p['no'] = i

        # Výstup
        meta = {
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(posts),
            "reached_2y": reached_2y,
            "profile": profile_slug or "auto"
        }
        out = {"status": "success", "meta": meta, "posts": posts}

        if save_to_file:
            output_file = get_output_file(profile_slug)
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"Uloženo do {output_file}", flush=True)

        print(json.dumps({"status": "success", "count": len(posts), "meta": meta}, indent=2, ensure_ascii=True))

if __name__ == "__main__":
    asyncio.run(main())
