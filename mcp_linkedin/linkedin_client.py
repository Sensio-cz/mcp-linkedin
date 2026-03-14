"""LinkedIn interaction logic — feed, profiles, posts, comments, profile viewers.

All functions accept a BrowserSession and return plain dicts.
MCP tool decorators live in mcp_tools.py (thin wrappers).
"""

import asyncio
import json
import logging
import re
import shutil
import time

from pathlib import Path

from .browser import BrowserSession
from .config import (
    COMMENT_TRACKING_DIR,
    MAX_COMMENT_LOAD_ITERATIONS,
    MAX_REPLY_BUTTONS_PER_PASS,
    MAX_REPLY_EXPAND_PASSES,
    MAX_SCROLL_FEED,
    MAX_SCROLL_POSTS,
    RELEVANT_KEYWORDS,
    SCROLL_DELAY,
    SCROLL_DELAY_COMMENTS,
    SELECTOR_TIMEOUT,
    SELECTOR_TIMEOUT_LONG,
    TRACK_MAX_CHECKS,
    TRACK_MIN_INTERVAL,
)
from .helpers import (
    load_tracked_comments,
    report_progress,
    save_tracked_comments,
)
from .selectors import (
    COMMENT_ALL,
    COMMENT_LOAD_MORE,
    COMMENT_REPLY_SELECTOR,
    COMMENT_TRIGGER,
    CONNECT_ADD_NOTE,
    CONNECT_BUTTON,
    CONNECT_NOTE_FIELD,
    CONNECT_SEND_BTN,
    CONNECT_SEND_NOW,
    FEED_POST,
    FEED_POST_ALT,
    LIKE_BUTTON,
    COMMENT_BOX_TRIGGER,
    COMMENT_EDITOR,
    COMMENT_SUBMIT,
    SEARCH_RESULT,
    PROFILE_CARD,
    VIEW_REPLIES_RE,
    VIEWERS_CONNECT_BTN,
    VIEWERS_HEADLINE,
    VIEWERS_LIST_ITEM,
    VIEWERS_NAME,
    VIEWERS_TIME,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Feed
# ═══════════════════════════════════════════════════════════════════════════

async def browse_feed(session: BrowserSession, ctx, count: int = 5) -> dict:
    """Browse LinkedIn feed and return recent posts."""
    posts = []
    errors = []

    try:
        page = await session.new_page("https://www.linkedin.com/feed/")
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        ctx.info(f"Browsing feed for {count} posts...")

        for i in range(min(count, MAX_SCROLL_FEED)):
            report_progress(ctx, i, count, f"Loading post {i+1}/{count}")
            try:
                await page.wait_for_selector(FEED_POST, timeout=5000)
                new_posts = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('.feed-shared-update-v2'))
                        .map(post => {
                            try {
                                return {
                                    author: post.querySelector('.feed-shared-actor__name')?.innerText?.trim() || 'Unknown',
                                    headline: post.querySelector('.feed-shared-actor__description')?.innerText?.trim() || '',
                                    content: post.querySelector('.feed-shared-text')?.innerText?.trim() || '',
                                    timestamp: post.querySelector('.feed-shared-actor__sub-description')?.innerText?.trim() || '',
                                    likes: post.querySelector('.social-details-social-counts__reactions-count')?.innerText?.trim() || '0'
                                };
                            } catch (e) { return null; }
                        })
                        .filter(p => p !== null);
                }''')
                for post in new_posts:
                    if post not in posts:
                        posts.append(post)
                if len(posts) >= count:
                    break
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(SCROLL_DELAY)
            except Exception as e:
                errors.append(f"Error during scroll {i}: {e}")

        await session.save_session(page)
        return {"status": "success", "posts": posts[:count], "count": len(posts[:count]), "errors": errors or None}
    except Exception as e:
        return {"status": "error", "message": f"Failed to browse feed: {e}", "posts": posts, "errors": errors}


# ═══════════════════════════════════════════════════════════════════════════
# Search
# ═══════════════════════════════════════════════════════════════════════════

async def search_profiles(session: BrowserSession, ctx, query: str, count: int = 5) -> dict:
    """Search for LinkedIn profiles matching a query."""
    try:
        page = await session.new_page(f"https://www.linkedin.com/search/results/people/?keywords={query}")
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        ctx.info(f"Searching for profiles matching: {query}")
        report_progress(ctx, 20, 100, "Loading search results...")
        await page.wait_for_selector(SEARCH_RESULT, timeout=SELECTOR_TIMEOUT)
        report_progress(ctx, 50, 100, "Extracting profile data...")

        profiles = await page.evaluate('''(count) => {
            const results = [];
            const cards = document.querySelectorAll('.reusable-search__result-container');
            for (let i = 0; i < Math.min(cards.length, count); i++) {
                const card = cards[i];
                try {
                    results.push({
                        name: card.querySelector('.entity-result__title-text a')?.innerText?.trim() || 'Unknown',
                        headline: card.querySelector('.entity-result__primary-subtitle')?.innerText?.trim() || '',
                        location: card.querySelector('.entity-result__secondary-subtitle')?.innerText?.trim() || '',
                        profileUrl: card.querySelector('.app-aware-link')?.href || '',
                        connectionDegree: card.querySelector('.dist-value')?.innerText?.trim() || '',
                        snippet: card.querySelector('.entity-result__summary')?.innerText?.trim() || ''
                    });
                } catch (e) {}
            }
            return results;
        }''', count)

        await session.save_session(page)
        return {"status": "success", "profiles": profiles, "count": len(profiles), "query": query}
    except Exception as e:
        return {"status": "error", "message": f"Failed to search profiles: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
# Profile viewing
# ═══════════════════════════════════════════════════════════════════════════

async def view_profile(session: BrowserSession, ctx, profile_url: str) -> dict:
    """Visit and extract data from a specific LinkedIn profile."""
    if "linkedin.com/in/" not in profile_url:
        return {"status": "error", "message": "Invalid LinkedIn profile URL. Should contain 'linkedin.com/in/'"}

    try:
        page = await session.new_page(profile_url)
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        ctx.info(f"Viewing profile: {profile_url}")
        await page.wait_for_selector(PROFILE_CARD, timeout=SELECTOR_TIMEOUT)
        await ctx.report_progress(0.5, 1.0)

        profile_data = await page.evaluate('''() => {
            const getData = (sel, prop = 'innerText') => {
                const el = document.querySelector(sel);
                return el ? el[prop].trim() : null;
            };
            return {
                name: getData('.pv-top-card--list .text-heading-xlarge'),
                headline: getData('.pv-top-card--list .text-body-medium'),
                location: getData('.pv-top-card--list .text-body-small:not(.inline)'),
                connectionDegree: getData('.pv-top-card__connections-count .t-black--light'),
                about: getData('.pv-shared-text-with-see-more .inline-show-more-text'),
                experience: Array.from(document.querySelectorAll('#experience-section .pv-entity__summary-info'))
                    .map(exp => ({
                        title: exp.querySelector('h3')?.innerText?.trim() || '',
                        company: exp.querySelector('.pv-entity__secondary-title')?.innerText?.trim() || '',
                        duration: exp.querySelector('.pv-entity__date-range span:not(.visually-hidden)')?.innerText?.trim() || ''
                    })),
                education: Array.from(document.querySelectorAll('#education-section .pv-education-entity'))
                    .map(edu => ({
                        school: edu.querySelector('.pv-entity__school-name')?.innerText?.trim() || '',
                        degree: edu.querySelector('.pv-entity__degree-name .pv-entity__comma-item')?.innerText?.trim() || '',
                        field: edu.querySelector('.pv-entity__fos .pv-entity__comma-item')?.innerText?.trim() || '',
                        dates: edu.querySelector('.pv-entity__dates span:not(.visually-hidden)')?.innerText?.trim() || ''
                    }))
            };
        }''')

        await ctx.report_progress(1.0, 1.0)
        await session.save_session(page)
        return {"status": "success", "profile": profile_data, "url": profile_url}
    except Exception as e:
        return {"status": "error", "message": f"Failed to extract profile data: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
# Profile posts
# ═══════════════════════════════════════════════════════════════════════════

async def get_profile_posts(session: BrowserSession, ctx, profile_url: str, count: int = 10) -> dict:
    """Fetch recent posts/activity from a specific LinkedIn profile."""
    if "linkedin.com/in/" not in profile_url:
        return {"status": "error", "message": "Invalid LinkedIn profile URL. Should contain 'linkedin.com/in/'"}

    profile_url = profile_url.rstrip("/")
    activity_url = f"{profile_url}/recent-activity/all/"
    posts = []
    errors = []
    count = min(count, 50)

    try:
        page = await session.new_page(activity_url)
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        ctx.info(f"Fetching posts from profile: {profile_url}")
        report_progress(ctx, 10, 100, "Loading activity page...")

        try:
            await page.wait_for_selector(FEED_POST, timeout=15000)
        except Exception:
            try:
                await page.wait_for_selector(FEED_POST_ALT, timeout=5000)
            except Exception:
                await session.save_session(page)
                return {"status": "success", "posts": [], "count": 0, "profile_url": profile_url,
                        "message": "No posts found or profile activity is not publicly visible"}

        max_scrolls = min(count, MAX_SCROLL_POSTS)
        for i in range(max_scrolls):
            report_progress(ctx, 10 + int(60 * i / max_scrolls), 100, f"Loading posts ({len(posts)}/{count})...")
            try:
                new_posts = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('.feed-shared-update-v2'))
                        .map(post => {
                            try {
                                const urn = post.getAttribute('data-urn') || '';
                                const permalinkEl = post.querySelector('a[href*="/feed/update/"]');
                                const postUrl = permalinkEl ? permalinkEl.href : '';
                                return {
                                    content: post.querySelector('.feed-shared-text')?.innerText?.trim() ||
                                             post.querySelector('.break-words')?.innerText?.trim() || '',
                                    timestamp: post.querySelector('.feed-shared-actor__sub-description')?.innerText?.trim() ||
                                               post.querySelector('time')?.innerText?.trim() || '',
                                    likes: post.querySelector('.social-details-social-counts__reactions-count')?.innerText?.trim() || '0',
                                    comments: post.querySelector('.social-details-social-counts__comments')?.innerText?.trim() || '0',
                                    reposts: post.querySelector('.social-details-social-counts__item--with-social-proof')?.innerText?.trim() || '0',
                                    postUrl, urn,
                                    hasImage: !!post.querySelector('.feed-shared-image') || !!post.querySelector('img.ivm-view-attr__img--centered'),
                                    hasVideo: !!post.querySelector('.feed-shared-linkedin-video') || !!post.querySelector('video'),
                                    hasDocument: !!post.querySelector('.feed-shared-document')
                                };
                            } catch (e) { return null; }
                        })
                        .filter(p => p !== null && (p.content || p.hasImage || p.hasVideo || p.hasDocument));
                }''')

                seen_keys = {p.get("urn") or p.get("content", "")[:80] for p in posts}
                for post in new_posts:
                    key = post.get("urn") or post.get("content", "")[:80]
                    if key and key not in seen_keys:
                        posts.append(post)
                        seen_keys.add(key)
                if len(posts) >= count:
                    break
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(1500)
            except Exception as e:
                errors.append(f"Error during scroll {i}: {e}")

        await session.save_session(page)
        return {"status": "success", "posts": posts[:count], "count": len(posts[:count]),
                "profile_url": profile_url, "errors": errors or None}
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch profile posts: {e}",
                "posts": posts, "errors": errors}


# ═══════════════════════════════════════════════════════════════════════════
# Comments
# ═══════════════════════════════════════════════════════════════════════════

async def get_post_comments(
    session: BrowserSession, ctx, post_url: str,
    save_to_file: bool = False, load_all: bool = True,
) -> dict:
    """Load all comments from a LinkedIn post with thread expansion."""
    if not ("linkedin.com/posts/" in post_url or "linkedin.com/feed/update/" in post_url):
        return {"status": "error", "message": "Invalid LinkedIn post URL"}

    base_url = post_url.split("?")[0].rstrip("/")

    try:
        page = await session.new_page(base_url)
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        await page.wait_for_selector(FEED_POST, timeout=SELECTOR_TIMEOUT_LONG)
        ctx.info("Post loaded, expanding comments...")

        # Click comments trigger
        try:
            trigger = page.locator(COMMENT_TRIGGER).first
            await trigger.click(timeout=5000)
            await page.wait_for_timeout(2000)
        except Exception:
            pass

        # Iteratively load more comments
        comments = []
        prev_count = 0
        for _ in range(MAX_COMMENT_LOAD_ITERATIONS):
            batch = await _extract_comments_batch(page)
            for c in batch:
                if not any(x.get("content") == c.get("content") and x.get("author") == c.get("author") for x in comments):
                    comments.append(c)
            try:
                load_more = page.locator(COMMENT_LOAD_MORE).first
                await load_more.click(timeout=2000)
                await page.wait_for_timeout(SCROLL_DELAY_COMMENTS)
            except Exception:
                break
            if len(comments) == prev_count:
                break
            prev_count = len(comments)

        # Expand reply threads
        for _ in range(MAX_REPLY_EXPAND_PASSES):
            view_replies = page.locator("button").filter(has_text=VIEW_REPLIES_RE)
            cnt = await view_replies.count()
            for i in range(min(cnt, MAX_REPLY_BUTTONS_PER_PASS)):
                try:
                    btn = view_replies.nth(i)
                    if await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(1200)
                except Exception:
                    pass

        # Final extraction with replies
        comments = await _extract_comments_final(page)
        await session.save_session(page)

        result = {"status": "success", "post_url": base_url, "comments": comments, "count": len(comments)}

        if save_to_file:
            COMMENT_TRACKING_DIR.mkdir(parents=True, exist_ok=True)
            activity_id = base_url.split("activity:")[-1].rstrip("/")
            filename = COMMENT_TRACKING_DIR / f"comments_{activity_id}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({
                    "post_url": base_url,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "comments": comments,
                    "count": len(comments),
                }, f, ensure_ascii=False, indent=2)
            result["saved_to"] = str(filename)

        return result
    except Exception as e:
        return {"status": "error", "message": f"Failed to get comments: {e}"}


async def track_post_comments(
    session: BrowserSession, ctx, post_url: str,
    auto_refresh: bool = False, interval_seconds: int = 60, max_checks: int = 10,
) -> dict:
    """Track comments — detect new comments since last check.

    First call saves all comments. Subsequent calls return only NEW ones.
    With auto_refresh=True, polls repeatedly at the given interval.
    """
    if not ("linkedin.com/posts/" in post_url or "linkedin.com/feed/update/" in post_url):
        return {"status": "error", "message": "Invalid LinkedIn post URL"}

    interval_seconds = max(TRACK_MIN_INTERVAL, interval_seconds)
    max_checks = min(max_checks, TRACK_MAX_CHECKS)

    tracking_data = load_tracked_comments(post_url)
    known_comments = tracking_data.get("comments", [])
    known_keys = {(c.get("author", "") + ":" + c.get("content", "")[:100]) for c in known_comments}

    all_new = []
    check_count = 0
    checks_performed = []

    while True:
        check_count += 1
        ctx.info(f"Check #{check_count}: Fetching comments from post...")

        result = await get_post_comments(session, ctx, post_url, save_to_file=False)
        if result.get("status") != "success":
            return {
                "status": "error",
                "message": f"Failed on check #{check_count}: {result.get('message', 'Unknown error')}",
                "new_comments_so_far": all_new,
                "checks_performed": check_count,
            }

        new_in_check = []
        for c in result.get("comments", []):
            key = c.get("author", "") + ":" + c.get("content", "")[:100]
            if key not in known_keys:
                new_in_check.append(c)
                known_keys.add(key)
                all_new.append(c)

        checks_performed.append({
            "check_number": check_count,
            "timestamp": int(time.time()),
            "total_comments": len(result.get("comments", [])),
            "new_comments": len(new_in_check),
        })

        ctx.info(f"Check #{check_count}: {'Found ' + str(len(new_in_check)) + ' new comment(s)!' if new_in_check else 'No new comments'}")

        all_known = known_comments + all_new
        tracking_data = {
            "post_url": post_url,
            "comments": all_known,
            "last_checked": int(time.time()),
            "total_checks": tracking_data.get("total_checks", 0) + 1,
        }
        save_tracked_comments(post_url, tracking_data)

        if not auto_refresh or check_count >= max_checks:
            break
        ctx.info(f"Waiting {interval_seconds}s before next check...")
        await asyncio.sleep(interval_seconds)

    is_first = len(known_comments) == 0 and check_count == 1
    return {
        "status": "success",
        "post_url": post_url,
        "is_first_load": is_first,
        "new_comments": all_new,
        "new_count": len(all_new),
        "total_tracked": len(tracking_data["comments"]),
        "checks_performed": checks_performed,
        "message": (
            f"Initial load: {len(all_new)} comments saved for tracking."
            if is_first
            else f"Found {len(all_new)} new comment(s) across {check_count} check(s)."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Post interaction
# ═══════════════════════════════════════════════════════════════════════════

async def interact_with_post(
    session: BrowserSession, ctx, post_url: str,
    action: str = "like", comment: str | None = None,
) -> dict:
    """Interact with a LinkedIn post (like, comment, read)."""
    if not ("linkedin.com/posts/" in post_url or "linkedin.com/feed/update/" in post_url):
        return {"status": "error", "message": "Invalid LinkedIn post URL"}

    valid_actions = ["like", "comment", "read"]
    if action not in valid_actions:
        return {"status": "error", "message": f"Invalid action. Choose from: {', '.join(valid_actions)}"}

    try:
        page = await session.new_page(post_url)
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        await page.wait_for_selector(FEED_POST, timeout=SELECTOR_TIMEOUT)
        ctx.info(f"Post loaded, performing action: {action}")

        post_content = await page.evaluate('''() => {
            const post = document.querySelector('.feed-shared-update-v2');
            return {
                author: post.querySelector('.feed-shared-actor__name')?.innerText?.trim() || 'Unknown',
                content: post.querySelector('.feed-shared-text')?.innerText?.trim() || '',
                engagementCount: post.querySelector('.social-details-social-counts__reactions-count')?.innerText?.trim() || '0'
            };
        }''')

        if action == "like":
            liked = await page.evaluate('''() => {
                const btn = document.querySelector('button.react-button__trigger');
                const isLiked = btn.getAttribute('aria-pressed') === 'true';
                if (!isLiked) { btn.click(); return true; }
                return false;
            }''')
            result = {"status": "success", "action": "like", "performed": liked,
                      "message": "Successfully liked the post" if liked else "Post was already liked"}
        elif action == "comment" and comment:
            await page.click(COMMENT_BOX_TRIGGER)
            await page.fill(COMMENT_EDITOR, comment)
            await page.click(COMMENT_SUBMIT)
            await page.wait_for_timeout(2000)
            result = {"status": "success", "action": "comment", "message": "Comment posted successfully"}
        else:
            result = {"status": "success", "action": "read", "post": post_content}

        await session.save_session(page)
        return result
    except Exception as e:
        return {"status": "error", "message": f"Failed to interact with post: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
# Profile viewers  (NEW)
# ═══════════════════════════════════════════════════════════════════════════

def _is_relevant(headline: str) -> bool:
    """Check if a viewer's headline matches relevant keywords."""
    lower = headline.lower()
    return any(kw in lower for kw in RELEVANT_KEYWORDS)


async def get_profile_viewers(
    session: BrowserSession, ctx,
    only_relevant: bool = True,
    only_not_connected: bool = True,
) -> dict:
    """Load people who viewed my profile, optionally filtered by relevance.

    Navigates to linkedin.com/me/profile-views/ and extracts viewer data.
    Relevance is determined by headline keywords (AI, founders, devs, automation).

    Args:
        session: Active browser session.
        ctx: MCP context.
        only_relevant: If True, return only viewers whose headline matches RELEVANT_KEYWORDS.
        only_not_connected: If True, exclude 1st-degree connections.

    Returns:
        dict with status, viewers list, counts.
    """
    try:
        page = await session.new_page("https://www.linkedin.com/me/profile-views/")
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        ctx.info("Loading profile viewers...")
        await page.wait_for_timeout(3000)

        # Scroll to load all viewers
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(1000)

        # Extract viewer data
        viewers = await page.evaluate('''(selectors) => {
            const items = document.querySelectorAll(selectors.listItem);
            const results = [];
            items.forEach(item => {
                const nameEl = item.querySelector(selectors.name);
                const headlineEl = item.querySelector(selectors.headline);
                const timeEl = item.querySelector(selectors.time);
                const profileUrl = nameEl?.href || '';
                const name = nameEl?.innerText?.trim() || '';
                const headline = headlineEl?.innerText?.trim() || '';
                const viewedAt = timeEl?.innerText?.trim() || '';

                // Check connection degree
                const degreeEl = item.querySelector('.dist-value, [class*="degree"]');
                const degree = degreeEl?.innerText?.trim() || '';
                const isConnected = degree.includes('1') || item.innerText.includes('1st');

                // Check if connect button exists
                const connectBtn = item.querySelector('button[aria-label*="Connect"], button[aria-label*="Spojit"]');
                const hasConnectBtn = !!connectBtn;

                if (name) {
                    results.push({
                        name, headline, profileUrl, viewedAt,
                        degree, isConnected, hasConnectBtn
                    });
                }
            });
            return results;
        }''', {
            "listItem": VIEWERS_LIST_ITEM,
            "name": VIEWERS_NAME,
            "headline": VIEWERS_HEADLINE,
            "time": VIEWERS_TIME,
        })

        await session.save_session(page)

        total_count = len(viewers)

        # Apply filters
        if only_not_connected:
            viewers = [v for v in viewers if not v.get("isConnected")]
        if only_relevant:
            viewers = [v for v in viewers if _is_relevant(v.get("headline", ""))]

        for v in viewers:
            v["isRelevant"] = _is_relevant(v.get("headline", ""))

        return {
            "status": "success",
            "viewers": viewers,
            "filtered_count": len(viewers),
            "total_count": total_count,
            "filters_applied": {
                "only_relevant": only_relevant,
                "only_not_connected": only_not_connected,
            },
        }
    except Exception as e:
        logger.error("Failed to get profile viewers: %s", e)
        return {"status": "error", "message": f"Failed to get profile viewers: {e}"}


async def send_connection_request(
    session: BrowserSession, ctx,
    profile_url: str,
    note: str | None = None,
) -> dict:
    """Send a connection request to a LinkedIn profile.

    Args:
        session: Active browser session.
        ctx: MCP context.
        profile_url: Full LinkedIn profile URL (must contain linkedin.com/in/).
        note: Optional personalised message to include with the request.

    Returns:
        dict with status and message.
    """
    if "linkedin.com/in/" not in profile_url:
        return {"status": "error", "message": "Invalid LinkedIn profile URL. Should contain 'linkedin.com/in/'"}

    try:
        page = await session.new_page(profile_url)
        if "login" in page.url:
            return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}

        ctx.info(f"Opening profile: {profile_url}")
        await page.wait_for_timeout(2000)

        # Look for Connect button on profile page
        connect_btn = page.locator(CONNECT_BUTTON).first
        try:
            await connect_btn.wait_for(timeout=5000)
        except Exception:
            # Maybe already connected, or button is in "More" dropdown
            more_btn = page.locator('button:has-text("More"), button:has-text("Více"), button[aria-label*="More"]').first
            try:
                await more_btn.click(timeout=3000)
                await page.wait_for_timeout(1000)
                connect_btn = page.locator(CONNECT_BUTTON).first
                await connect_btn.wait_for(timeout=3000)
            except Exception:
                await session.save_session(page)
                return {
                    "status": "skipped",
                    "message": "Connect button not found. Already connected or unable to connect.",
                    "profile_url": profile_url,
                }

        await connect_btn.click()
        await page.wait_for_timeout(1500)

        if note:
            # Click "Add a note" if available
            try:
                add_note_btn = page.locator(CONNECT_ADD_NOTE).first
                await add_note_btn.click(timeout=3000)
                await page.wait_for_timeout(1000)

                note_field = page.locator(CONNECT_NOTE_FIELD).first
                await note_field.fill(note)
                await page.wait_for_timeout(500)

                send_btn = page.locator(CONNECT_SEND_BTN).first
                await send_btn.click(timeout=3000)
            except Exception as e:
                logger.warning("Failed to add note, trying send without note: %s", e)
                # Try send without note
                try:
                    send_now = page.locator(CONNECT_SEND_NOW).first
                    await send_now.click(timeout=3000)
                except Exception:
                    pass
        else:
            # Send without note
            try:
                send_now = page.locator(CONNECT_SEND_NOW).first
                await send_now.click(timeout=3000)
            except Exception:
                pass  # Some modals auto-send

        await page.wait_for_timeout(2000)
        await session.save_session(page)

        return {
            "status": "success",
            "message": f"Connection request sent to {profile_url}" + (" with note" if note else ""),
            "profile_url": profile_url,
        }
    except Exception as e:
        logger.error("Failed to send connection request: %s", e)
        return {"status": "error", "message": f"Failed to send connection request: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers for comment extraction
# ═══════════════════════════════════════════════════════════════════════════

async def _extract_comments_batch(page) -> list[dict]:
    """Quick comment extraction (used during iterative loading)."""
    return await page.evaluate('''() => {
        const items = [];
        const commentEls = document.querySelectorAll('.comments-comment-entity, .comments-comment-item, article[data-id]');
        const filtered = Array.from(commentEls).filter(el => {
            if ((el.className || '').includes('__')) return false;
            return !el.classList.contains('comments-comment-entity--reply') && !el.closest('.comments-comment-entity--reply');
        });
        filtered.forEach(el => {
            const authorEl = el.querySelector('.comments-comment-meta__description-title, .comments-comment-actor__name, a[href*="/in/"]');
            const contentEl = el.querySelector('.comments-comment-item__main-content, [class*="comment-item__content"], .feed-shared-text');
            const timeEl = el.querySelector('time.comments-comment-meta__data, [class*="timestamp"]');
            let reactions = 0;
            const socialBar = el.querySelector('.comment-social-activity');
            if (socialBar) {
                const m = socialBar.innerText?.match(/(?:Líbí se|Like)\\s*(\\d+)|(\\d+)\\s*(?:Reaction|Reakce)/i);
                if (m) reactions = parseInt(m[1] || m[2], 10);
            }
            let replies = 0;
            const replyMatch = el.innerText.match(/View\\s+(\\d+)\\s+repl/i) || el.innerText.match(/(\\d+)\\s+repl/i) || el.innerText.match(/Zobrazit\\s+(\\d+)\\s+odpov/i) || el.innerText.match(/(\\d+)\\s+odpov/i);
            if (replyMatch) replies = parseInt(replyMatch[1], 10);
            const author = authorEl?.innerText?.trim() || 'Unknown';
            const content = contentEl?.innerText?.trim() || '';
            if (content) items.push({ author, content, timestamp: timeEl?.innerText?.trim() || '', reactions, replies });
        });
        return items;
    }''')


async def _extract_comments_final(page) -> list[dict]:
    """Full comment extraction with nested replies (final pass)."""
    return await page.evaluate('''() => {
        const items = [];
        const seen = new Set();
        const allCommentEls = document.querySelectorAll('.comments-comment-entity, .comments-comment-item, article[data-id]');
        const topLevel = Array.from(allCommentEls).filter(el => {
            if ((el.className || '').includes('__')) return false;
            const isReply = el.classList.contains('comments-comment-entity--reply') ||
                el.classList.contains('comments-comment-item--reply') ||
                el.closest('.comments-comment-entity--reply, .comments-comment-item--reply');
            return !isReply;
        });

        function getAuthor(el) {
            const title = el.querySelector('.comments-comment-meta__description-title');
            if (title && title.innerText?.trim()) return title.innerText.trim();
            const selectors = ['.comments-comment-actor__name', '.comments-post-meta__name-text', '[class*="actor__name"]'];
            for (const sel of selectors) {
                const a = el.querySelector(sel);
                if (a && a.innerText?.trim()) return a.innerText.trim();
            }
            const firstLink = el.querySelector('.comments-comment-meta__actor a[href*="/in/"], a.comments-comment-meta__image-link[href*="/in/"]');
            if (firstLink) {
                const desc = firstLink.closest('.comments-comment-meta__actor')?.querySelector('.comments-comment-meta__description-title');
                if (desc) return desc.innerText?.trim() || '';
            }
            const profileLinks = el.querySelectorAll('a[href*="/in/"]');
            for (const a of profileLinks) {
                const t = a.innerText?.trim();
                if (t && t.length > 2 && t.length < 80 && !t.includes('\\n') && !/^https?:\\/\\//.test(t))
                    return t;
            }
            return '';
        }

        function getReactions(el) {
            const socialBar = el.querySelector('.comment-social-activity, [class*="comment-social"], [class*="social-activity"]');
            if (socialBar) {
                const txt = socialBar.innerText || '';
                const m = txt.match(/(?:Líbí se|Like)\\s*(\\d+)|(\\d+)\\s*(?:Reaction|Reakce)s?/i);
                if (m) return parseInt(m[1] || m[2], 10);
            }
            const m = el.innerText?.match(/(\\d+)\\s*(?:Reaction|Reakce)s?/i);
            if (m) return parseInt(m[1], 10);
            return 0;
        }

        topLevel.forEach(el => {
            const author = getAuthor(el) || 'Unknown';
            const contentEl = el.querySelector('.comments-comment-item__main-content, .comments-comment-entity__content [class*="main-content"], [class*="comment-item__content"], .feed-shared-text');
            const content = contentEl?.innerText?.trim() || '';
            const timeEl = el.querySelector('time.comments-comment-meta__data, .comments-comment-item__timestamp, [class*="timestamp"]');
            const timestamp = timeEl?.innerText?.trim() || '';
            const reactions = getReactions(el);

            const replyEls = el.querySelectorAll('.comments-comment-entity--reply, .comments-comment-item--reply');
            const repliesData = [];
            replyEls.forEach(replyEl => {
                const rAuthor = getAuthor(replyEl) || 'Unknown';
                const rContentEl = replyEl.querySelector('.comments-comment-item__main-content, .comments-comment-entity__content [class*="main-content"], [class*="comment-item__content"], .feed-shared-text');
                const rContent = rContentEl?.innerText?.trim() || '';
                const rTimeEl = replyEl.querySelector('time.comments-comment-meta__data, [class*="timestamp"]');
                const rTimestamp = rTimeEl?.innerText?.trim() || '';
                const rReactions = getReactions(replyEl);
                if (rContent) repliesData.push({ author: rAuthor, content: rContent, timestamp: rTimestamp, reactions: rReactions });
            });

            const key = author + '|' + content.substring(0, 50);
            if (content && !seen.has(key)) {
                seen.add(key);
                items.push({ author, content, timestamp, reactions, replies: repliesData.length, replies_data: repliesData });
            }
        });
        return items;
    }''')
