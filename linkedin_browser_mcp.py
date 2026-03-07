from fastmcp import FastMCP, Context
from playwright.async_api import async_playwright
import asyncio
import os
import re
import json
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import time
import logging
import sys
from pathlib import Path

# Set up logging to stderr only
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def setup_sessions_directory():
    """Set up the sessions directory with proper permissions"""
    try:
        sessions_dir = Path(__file__).parent / 'sessions'
        sessions_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
        # Ensure the directory has the correct permissions even if it already existed
        os.chmod(sessions_dir, 0o777)
        logger.debug(f"Sessions directory set up at {sessions_dir} with full permissions")
        return True
    except Exception as e:
        logger.error(f"Failed to set up sessions directory: {str(e)}")
        return False

# Load environment variables
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.debug(f"Loaded environment from {env_path}")
else:
    logger.warning(f"No .env file found at {env_path}")

# Create MCP server
mcp = FastMCP("linkedin")

def report_progress(ctx, current, total, message=None):
    """Helper function to report progress with proper validation"""
    try:
        progress = min(1.0, current / total) if total > 0 else 0
        if message:
            ctx.info(message)
        logger.debug(f"Progress: {progress:.2%} - {message if message else ''}")
    except Exception as e:
        logger.error(f"Error reporting progress: {str(e)}")

def handle_notification(ctx, notification_type, params=None):
    """Helper function to handle notifications with proper validation"""
    try:
        if notification_type == "initialized":
            logger.info("MCP Server initialized")
            if ctx:  # Only call ctx.info if ctx is provided
                ctx.info("Server initialized and ready")
        elif notification_type == "cancelled":
            reason = params.get("reason", "Unknown reason")
            logger.warning(f"Operation cancelled: {reason}")
            if ctx:
                ctx.warning(f"Operation cancelled: {reason}")
        else:
            logger.debug(f"Notification: {notification_type} - {params}")
    except Exception as e:
        logger.error(f"Error handling notification: {str(e)}")

# Helper to save cookies between sessions
async def save_cookies(page, platform):
    """Save cookies with proper directory permissions"""
    try:
        cookies = await page.context.cookies()
        
        # Validate cookies
        if not cookies or not isinstance(cookies, list):
            raise ValueError("Invalid cookie format")
            
        # Add timestamp for expiration check
        cookie_data = {
            "timestamp": int(time.time()),
            "cookies": cookies
        }
        
        # Ensure sessions directory exists with proper permissions
        if not setup_sessions_directory():
            raise Exception("Failed to set up sessions directory")
        
        # Encrypt cookies before saving (key from .env or .cookie_key)
        key = os.getenv('COOKIE_ENCRYPTION_KEY')
        if not key:
            key_file = Path(__file__).parent / 'sessions' / '.cookie_key'
            if key_file.exists():
                key = key_file.read_bytes()
            else:
                key = Fernet.generate_key()
                key_file.write_bytes(key)
        elif isinstance(key, str):
            key = key.encode()
        f = Fernet(key)
        encrypted_data = f.encrypt(json.dumps(cookie_data).encode())
        
        cookie_file = Path(__file__).parent / 'sessions' / f'{platform}_cookies.json'
        with open(cookie_file, 'wb') as f:
            f.write(encrypted_data)
        # Set file permissions to 666 (rw-rw-rw-)
        os.chmod(cookie_file, 0o666)
            
    except Exception as e:
        raise Exception(f"Failed to save cookies: {str(e)}")

# Helper to load cookies
async def load_cookies(context, platform):
    try:
        cookie_file = Path(__file__).parent / 'sessions' / f'{platform}_cookies.json'
        with open(cookie_file, 'rb') as f:
            encrypted_data = f.read()
            
        # Decrypt cookies (key from .env or .cookie_key)
        key = os.getenv('COOKIE_ENCRYPTION_KEY')
        if not key:
            key_file = Path(__file__).parent / 'sessions' / '.cookie_key'
            if not key_file.exists():
                return False
            key = key_file.read_bytes()
        elif isinstance(key, str):
            key = key.encode()
        f = Fernet(key)
        cookie_data = json.loads(f.decrypt(encrypted_data))
        
        # Check cookie expiration (7 days)
        if int(time.time()) - cookie_data["timestamp"] > 604800:
            os.remove(cookie_file)
            return False
            
        await context.add_cookies(cookie_data["cookies"])
        return True
        
    except FileNotFoundError:
        return False
    except Exception as e:
        # If there's any error loading cookies, delete the file and start fresh
        try:
            os.remove(Path(__file__).parent / 'sessions' / f'{platform}_cookies.json')
        except:
            pass
        return False
    
class BrowserSession:
    """Context manager for browser sessions with cookie persistence"""
    
    def __init__(self, platform='linkedin', headless=True, launch_timeout=30000, max_retries=3):
        logger.info(f"Initializing {platform} browser session (headless: {headless})")
        self.platform = platform
        self.headless = headless
        self.launch_timeout = launch_timeout
        self.max_retries = max_retries
        self.playwright = None
        self.browser = None
        self.context = None
        self._closed = False
        
    async def __aenter__(self):
        retry_count = 0
        last_error = None
        
        # Ensure sessions directory exists with proper permissions
        if not setup_sessions_directory():
            raise Exception("Failed to set up sessions directory with proper permissions")
        
        while retry_count < self.max_retries and not self._closed:
            try:
                logger.info(f"Starting Playwright (attempt {retry_count + 1}/{self.max_retries})")
                
                # Ensure clean state
                await self._cleanup()
                
                # Initialize Playwright with timeout
                self.playwright = await asyncio.wait_for(
                    async_playwright().start(),
                    timeout=self.launch_timeout/1000
                )
                
                # Launch browser with more generous timeout and retry logic
                launch_success = False
                for attempt in range(3):
                    try:
                        logger.info(f"Launching browser (sub-attempt {attempt + 1}/3)")
                        self.browser = await self.playwright.chromium.launch(
                            headless=self.headless,
                            timeout=self.launch_timeout,
                            args=[
                                '--disable-dev-shm-usage',
                                '--no-sandbox',
                                '--disable-blink-features=AutomationControlled',  # Try to avoid detection
                                '--start-maximized'  # Start with maximized window
                            ]
                        )
                        launch_success = True
                        break
                    except Exception as e:
                        logger.error(f"Browser launch sub-attempt {attempt + 1} failed: {str(e)}")
                        await asyncio.sleep(2)  # Increased delay between attempts
                
                if not launch_success:
                    raise Exception("Failed to launch browser after 3 attempts")
                
                logger.info("Creating browser context")
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
                )
                
                # Try to load existing session
                logger.info("Attempting to load existing session")
                try:
                    session_loaded = await load_cookies(self.context, self.platform)
                    if session_loaded:
                        logger.info("Existing session loaded successfully")
                    else:
                        logger.info("No existing session found or session expired")
                except Exception as cookie_error:
                    logger.warning(f"Error loading cookies: {str(cookie_error)}")
                    # Continue even if cookie loading fails
                
                return self
                
            except Exception as e:
                last_error = e
                retry_count += 1
                logger.error(f"Browser session initialization attempt {retry_count} failed: {str(e)}")
                
                # Cleanup on failure
                await self._cleanup()
                
                if retry_count < self.max_retries and not self._closed:
                    await asyncio.sleep(2 * retry_count)  # Exponential backoff
                else:
                    logger.error("All browser session initialization attempts failed")
                    raise Exception(f"Failed to initialize browser after {self.max_retries} attempts. Last error: {str(last_error)}")

    async def _cleanup(self):
        """Clean up browser resources"""
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                logger.error(f"Error stopping playwright: {str(e)}")
        self.browser = None
        self.playwright = None
        self.context = None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.info("Closing browser session")
        self._closed = True
        await self._cleanup()
        
    async def new_page(self, url=None):
        if self._closed:
            raise Exception("Browser session has been closed")
        
        page = await self.context.new_page()
        if url:
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                logger.error(f"Error navigating to {url}: {str(e)}")
                raise
        return page
        
    async def save_session(self, page):
        if self._closed:
            raise Exception("Browser session has been closed")
            
        try:
            await save_cookies(page, self.platform)
        except Exception as e:
            logger.error(f"Error saving session: {str(e)}")
            raise

@mcp.tool()
async def login_linkedin(username: str | None = None, password: str | None = None, ctx: Context | None = None) -> dict:
    """Open LinkedIn login page in browser for manual login.
    Username and password are optional - if not provided, user will need to enter them manually."""
    
    logger.info("Starting LinkedIn login with browser for manual login")
    
    # Create browser session with explicit window size and position
    async with BrowserSession(platform='linkedin', headless=False) as session:
        try:
            # Configure browser window
            page = await session.new_page()
            await page.set_viewport_size({'width': 1280, 'height': 800})
            
            # Navigate to LinkedIn login
            await page.goto('https://www.linkedin.com/login', wait_until='networkidle')
            
            # Check if already logged in
            if 'feed' in page.url:
                await session.save_session(page)
                return {"status": "success", "message": "Already logged in"}
            
            if ctx:
                ctx.info("Please log in manually through the browser window...")
                ctx.info("The browser will wait for up to 5 minutes for you to complete the login.")
            logger.info("Waiting for manual login...")
            
            # Pre-fill credentials if provided
            try:
                if username:
                    await page.fill('#username', username)
                if password:
                    await page.fill('#password', password)
            except Exception as e:
                logger.warning(f"Failed to pre-fill credentials: {str(e)}")
                # Continue anyway - user can enter manually
            
            # Wait for successful login (feed page)
            try:
                await page.wait_for_url('**/feed/**', timeout=300000)  # 5 minutes timeout
                if ctx:
                    ctx.info("Login successful!")
                logger.info("Manual login successful")
                await session.save_session(page)
                # Keep browser open for a moment to show success
                await asyncio.sleep(3)
                return {"status": "success", "message": "Manual login successful"}
            except Exception as e:
                logger.error(f"Login timeout: {str(e)}")
                return {
                    "status": "error",
                    "message": "Login timeout. Please try again and complete login within 5 minutes."
                }
                
        except Exception as e:
            logger.error(f"Login process error: {str(e)}")
            return {"status": "error", "message": f"Login process error: {str(e)}"}

@mcp.tool()
async def login_linkedin_secure(ctx: Context | None = None) -> dict:
    """Open LinkedIn login page in browser for manual login using environment credentials as default values.
    
    Optional environment variables:
    - LINKEDIN_USERNAME: Your LinkedIn email/username (will be pre-filled if provided)
    - LINKEDIN_PASSWORD: Your LinkedIn password (will be pre-filled if provided)
    
    Returns:
        dict: Login status and message
    """
    logger.info("Starting secure LinkedIn login")
    username = os.getenv('LINKEDIN_USERNAME', '').strip()
    password = os.getenv('LINKEDIN_PASSWORD', '').strip()
    
    # We'll pass the credentials to pre-fill them, but user can still modify them
    return await login_linkedin(username if username else None, password if password else None, ctx)

@mcp.tool()
async def get_linkedin_profile(username: str, ctx: Context) -> dict:
    """Get LinkedIn profile information"""
    async with BrowserSession(platform='linkedin', headless=False) as session:
        page = await session.new_page(f'https://www.linkedin.com/in/{username}')
        
        # Check if profile page loaded
        if 'profile' not in page.url:
            return {"status": "error", "message": "Profile page not found"}
            
@mcp.tool()
async def browse_linkedin_feed(ctx: Context, count: int = 5) -> dict:
    """Browse LinkedIn feed and return recent posts
    
    Args:
        ctx: MCP context for logging and progress reporting
        count: Number of posts to retrieve (default: 5)
        
    Returns:
        dict: Contains status, posts array, and any errors
    """
    posts = []
    errors = []
    
    async with BrowserSession(platform='linkedin') as session:
        try:
            page = await session.new_page('https://www.linkedin.com/feed/')
            
            # Check if we're logged in
            if 'login' in page.url:
                return {
                    "status": "error", 
                    "message": "Not logged in. Please run login_linkedin tool first"
                }
                
            ctx.info(f"Browsing feed for {count} posts...")
            
            # Scroll to load content
            for i in range(min(count, 20)):  # Limit to reasonable number
                report_progress(ctx, i, count, f"Loading post {i+1}/{count}")
                
                try:
                    # Wait for posts to be visible
                    await page.wait_for_selector('.feed-shared-update-v2', timeout=5000)
                    
                    # Extract visible posts
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
                                } catch (e) {
                                    return null;
                                }
                            })
                            .filter(p => p !== null);
                    }''')
                    
                    # Add new posts to our collection, avoiding duplicates
                    for post in new_posts:
                        if post not in posts:
                            posts.append(post)
                            
                    if len(posts) >= count:
                        break
                        
                    # Scroll down to load more content
                    await page.evaluate('window.scrollBy(0, 800)')
                    await page.wait_for_timeout(1000)  # Wait for content to load
                    
                except Exception as scroll_error:
                    errors.append(f"Error during scroll {i}: {str(scroll_error)}")
                    continue
            
            # Save session cookies
            await session.save_session(page)
            
            return {
                "status": "success",
                "posts": posts[:count],
                "count": len(posts),
                "errors": errors if errors else None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to browse feed: {str(e)}",
                "posts": posts,
                "errors": errors
            }
        

@mcp.tool()
async def search_linkedin_profiles(query: str, ctx: Context, count: int = 5) -> dict:
    """Search for LinkedIn profiles matching a query"""
    async with BrowserSession(platform='linkedin') as session:
        try:
            search_url = f'https://www.linkedin.com/search/results/people/?keywords={query}'
            page = await session.new_page(search_url)
            
            # Check if we're logged in
            if 'login' in page.url:
                return {
                    "status": "error", 
                    "message": "Not logged in. Please run login_linkedin tool first"
                }
            
            ctx.info(f"Searching for profiles matching: {query}")
            report_progress(ctx, 20, 100, "Loading search results...")
            
            # Wait for search results
            await page.wait_for_selector('.reusable-search__result-container', timeout=10000)
            ctx.info("Search results loaded")
            report_progress(ctx, 50, 100, "Extracting profile data...")
            
            # Extract profile data
            profiles = await page.evaluate('''(count) => {
                const results = [];
                const profileCards = document.querySelectorAll('.reusable-search__result-container');
                
                for (let i = 0; i < Math.min(profileCards.length, count); i++) {
                    const card = profileCards[i];
                    try {
                        const profile = {
                            name: card.querySelector('.entity-result__title-text a')?.innerText?.trim() || 'Unknown',
                            headline: card.querySelector('.entity-result__primary-subtitle')?.innerText?.trim() || '',
                            location: card.querySelector('.entity-result__secondary-subtitle')?.innerText?.trim() || '',
                            profileUrl: card.querySelector('.app-aware-link')?.href || '',
                            connectionDegree: card.querySelector('.dist-value')?.innerText?.trim() || '',
                            snippet: card.querySelector('.entity-result__summary')?.innerText?.trim() || ''
                        };
                        results.push(profile);
                    } catch (e) {
                        console.error("Error extracting profile", e);
                    }
                }
                return results;
            }''', count)
            
            report_progress(ctx, 90, 100, "Saving session...")
            await session.save_session(page)
            report_progress(ctx, 100, 100, "Search complete")
            
            return {
                "status": "success",
                "profiles": profiles,
                "count": len(profiles),
                "query": query
            }
            
        except Exception as e:
            ctx.error(f"Profile search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search profiles: {str(e)}"
            }
        
@mcp.tool() 
async def view_linkedin_profile(profile_url: str, ctx: Context) -> dict:
    """Visit and extract data from a specific LinkedIn profile"""
    if not ('linkedin.com/in/' in profile_url):
        return {
            "status": "error",
            "message": "Invalid LinkedIn profile URL. Should contain 'linkedin.com/in/'"
        }
        
    async with BrowserSession(platform='linkedin') as session:
        try:
            page = await session.new_page(profile_url)
            
            # Check if we're logged in
            if 'login' in page.url:
                return {
                    "status": "error", 
                    "message": "Not logged in. Please run login_linkedin tool first"
                }
                
            ctx.info(f"Viewing profile: {profile_url}")
            
            # Wait for profile to load
            await page.wait_for_selector('.pv-top-card', timeout=10000)
            await ctx.report_progress(0.5, 1.0)
            
            # Extract profile information
            profile_data = await page.evaluate('''() => {
                const getData = (selector, property = 'innerText') => {
                    const element = document.querySelector(selector);
                    return element ? element[property].trim() : null;
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
            
            return {
                "status": "success",
                "profile": profile_data,
                "url": profile_url
            }
            
        except Exception as e:
            ctx.error(f"Profile viewing failed: {str(e)}")
            return {
                "status": "error", 
                "message": f"Failed to extract profile data: {str(e)}"
            }
        

@mcp.tool()
async def get_profile_posts(profile_url: str, ctx: Context, count: int = 10) -> dict:
    """Fetch recent posts/activity from a specific LinkedIn profile

    Args:
        profile_url: LinkedIn profile URL (e.g. https://www.linkedin.com/in/jantobolik)
        ctx: MCP context for logging and progress reporting
        count: Number of posts to retrieve (default: 10, max: 50)

    Returns:
        dict: Contains status, posts array with content/date/engagement, and any errors
    """
    if not ('linkedin.com/in/' in profile_url):
        return {
            "status": "error",
            "message": "Invalid LinkedIn profile URL. Should contain 'linkedin.com/in/'"
        }

    # Normalize URL — strip trailing slash and build activity URL
    profile_url = profile_url.rstrip('/')
    activity_url = f"{profile_url}/recent-activity/all/"

    posts = []
    errors = []
    count = min(count, 50)

    async with BrowserSession(platform='linkedin') as session:
        try:
            page = await session.new_page(activity_url)

            # Check if we're logged in
            if 'login' in page.url:
                return {
                    "status": "error",
                    "message": "Not logged in. Please run login_linkedin tool first"
                }

            ctx.info(f"Fetching posts from profile: {profile_url}")
            report_progress(ctx, 10, 100, "Loading activity page...")

            # Wait for activity content to load
            try:
                await page.wait_for_selector('.feed-shared-update-v2', timeout=15000)
            except Exception:
                # Try alternative selector for newer LinkedIn layouts
                try:
                    await page.wait_for_selector('[data-urn]', timeout=5000)
                except Exception:
                    await session.save_session(page)
                    return {
                        "status": "success",
                        "posts": [],
                        "count": 0,
                        "profile_url": profile_url,
                        "message": "No posts found or profile activity is not publicly visible"
                    }

            # Scroll to load more posts
            max_scrolls = min(count, 50)
            for i in range(max_scrolls):
                report_progress(ctx, 10 + int(60 * i / max_scrolls), 100, f"Loading posts ({len(posts)}/{count})...")

                try:
                    # Extract all currently visible posts
                    new_posts = await page.evaluate('''() => {
                        return Array.from(document.querySelectorAll('.feed-shared-update-v2'))
                            .map(post => {
                                try {
                                    // Extract post URL from data-urn or permalink
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
                                        postUrl: postUrl,
                                        urn: urn,
                                        hasImage: !!post.querySelector('.feed-shared-image') || !!post.querySelector('img.ivm-view-attr__img--centered'),
                                        hasVideo: !!post.querySelector('.feed-shared-linkedin-video') || !!post.querySelector('video'),
                                        hasDocument: !!post.querySelector('.feed-shared-document')
                                    };
                                } catch (e) {
                                    return null;
                                }
                            })
                            .filter(p => p !== null && (p.content || p.hasImage || p.hasVideo || p.hasDocument));
                    }''')

                    # Add new posts avoiding duplicates (by urn or content)
                    seen_keys = {p.get('urn') or p.get('content', '')[:80] for p in posts}
                    for post in new_posts:
                        key = post.get('urn') or post.get('content', '')[:80]
                        if key and key not in seen_keys:
                            posts.append(post)
                            seen_keys.add(key)

                    if len(posts) >= count:
                        break

                    # Scroll down to load more
                    await page.evaluate('window.scrollBy(0, 1000)')
                    await page.wait_for_timeout(1500)

                except Exception as scroll_error:
                    errors.append(f"Error during scroll {i}: {str(scroll_error)}")
                    continue

            report_progress(ctx, 90, 100, "Saving session...")
            await session.save_session(page)
            report_progress(ctx, 100, 100, "Done")

            return {
                "status": "success",
                "posts": posts[:count],
                "count": len(posts[:count]),
                "profile_url": profile_url,
                "errors": errors if errors else None
            }

        except Exception as e:
            ctx.error(f"Failed to fetch profile posts: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to fetch profile posts: {str(e)}",
                "posts": posts,
                "errors": errors
            }


@mcp.tool()
async def get_post_comments(post_url: str, ctx: Context, save_to_file: bool = False, load_all: bool = True) -> dict:
    """Load all comments from a LinkedIn post. Expands threads, clicks 'load more', extracts author, content, timestamp, likes/reactions count, and reply count for each comment.
    Optionally saves to data/comment_tracking/ as JSON."""
    if not ('linkedin.com/posts/' in post_url or 'linkedin.com/feed/update/' in post_url):
        return {"status": "error", "message": "Invalid LinkedIn post URL"}
    
    # Normalize URL (strip comment/reply query params for consistent loading)
    base_url = post_url.split('?')[0].rstrip('/')
    
    async with BrowserSession(platform='linkedin', headless=False) as session:
        try:
            page = await session.new_page(base_url)
            
            if 'login' in page.url:
                return {"status": "error", "message": "Not logged in. Please run login_linkedin tool first"}
            
            await page.wait_for_selector('.feed-shared-update-v2', timeout=60000)
            ctx.info("Post loaded, expanding comments...")
            
            # Click comments to expand section
            try:
                comments_trigger = page.locator('button.social-details-social-counts__comments, [class*="comments-count"]').first
                await comments_trigger.click(timeout=5000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass
            
            comments = []
            prev_count = 0
            max_iterations = 20
            
            for iteration in range(max_iterations):
                # Extract comments (same logic as final extraction, simplified)
                batch = await page.evaluate('''() => {
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
                
                for c in batch:
                    if not any(x.get('content') == c.get('content') and x.get('author') == c.get('author') for x in comments):
                        comments.append(c)
                
                # Click "See more comments" or "Load more"
                load_more = page.locator('button:has-text("See more"), button:has-text("Load more"), span:has-text("See more comments")').first
                try:
                    await load_more.click(timeout=2000)
                    await page.wait_for_timeout(1500)
                except Exception:
                    break
                
                if len(comments) == prev_count:
                    break
                prev_count = len(comments)
            
            # Expand reply threads - ONLY "View X replies" / "Zobrazit X odpovědí", NOT "Reply"/"Odpovědět" (opens reply form!)
            view_replies_re = re.compile(r'View\s+\d+\s+repl|Zobrazit\s+\d+\s+odpověd', re.I)
            for _ in range(3):  # Multiple passes - new buttons may appear after expand
                view_replies = page.locator('button').filter(has_text=view_replies_re)
                cnt = await view_replies.count()
                for i in range(min(cnt, 50)):
                    try:
                        btn = view_replies.nth(i)
                        if await btn.is_visible():
                            await btn.click()
                            await page.wait_for_timeout(1200)
                    except Exception:
                        pass
            
            # Final extraction: only TOP-LEVEL comments, with reply count from "View X replies" or nested elements
            comments = await page.evaluate('''() => {
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
            
            await session.save_session(page)
            
            result = {
                "status": "success",
                "post_url": base_url,
                "comments": comments,
                "count": len(comments)
            }
            
            if save_to_file:
                tracking_dir = Path(__file__).parent / 'data' / 'comment_tracking'
                tracking_dir.mkdir(parents=True, exist_ok=True)
                activity_id = base_url.split('activity:')[-1].rstrip('/')
                filename = tracking_dir / f"comments_{activity_id}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        "post_url": base_url,
                        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "comments": comments,
                        "count": len(comments)
                    }, f, ensure_ascii=False, indent=2)
                result["saved_to"] = str(filename)
            
            return result
            
        except Exception as e:
            ctx.error(f"Failed to get comments: {str(e)}")
            return {"status": "error", "message": f"Failed to get comments: {str(e)}"}


@mcp.tool()
async def track_post_comments(post_url: str, ctx: Context, poll_interval_seconds: int = 300, save_to_file: bool = True) -> dict:
    """Track comments on a LinkedIn post. Fetches comments, saves to data/comment_tracking/, detects new comments since last run.
    For continuous polling, run repeatedly (e.g. via cron) or call with desired poll_interval_seconds.
    Returns current comments plus new_comments list if previous state existed."""
    result = await get_post_comments(post_url, ctx, save_to_file=save_to_file)
    if result.get("status") != "success":
        return result
    
    tracking_dir = Path(__file__).parent / 'data' / 'comment_tracking'
    base_url = post_url.split('?')[0].rstrip('/')
    activity_id = base_url.split('activity:')[-1].rstrip('/')
    filename = tracking_dir / f"comments_{activity_id}.json"
    
    prev_path = tracking_dir / f"comments_{activity_id}_prev.json"
    new_comments = []
    if prev_path.exists():
        try:
            with open(prev_path, 'r', encoding='utf-8') as f:
                prev = json.load(f)
            prev_keys = {f"{c.get('author','')}|{c.get('content','')[:80]}" for c in prev.get("comments", [])}
            for c in result.get("comments", []):
                key = f"{c.get('author','')}|{c.get('content','')[:80]}"
                if key not in prev_keys:
                    new_comments.append(c)
        except Exception:
            pass
    
    if save_to_file and filename.exists():
        import shutil
        shutil.copy(filename, prev_path)
    
    result["new_comments_count"] = len(new_comments)
    result["new_comments"] = new_comments
    return result


@mcp.tool()
async def interact_with_linkedin_post(post_url: str, ctx: Context, action: str = "like", comment: str = None) -> dict:
    """Interact with a LinkedIn post (like, comment)"""
    if not ('linkedin.com/posts/' in post_url or 'linkedin.com/feed/update/' in post_url):
        return {
            "status": "error",
            "message": "Invalid LinkedIn post URL"
        }
        
    valid_actions = ["like", "comment", "read"]
    if action not in valid_actions:
        return {
            "status": "error",
            "message": f"Invalid action. Choose from: {', '.join(valid_actions)}"
        }
        
    async with BrowserSession(platform='linkedin', headless=False) as session:
        try:
            page = await session.new_page(post_url)
            
            # Check if we're logged in
            if 'login' in page.url:
                return {
                    "status": "error", 
                    "message": "Not logged in. Please run login_linkedin tool first"
                }
                
            # Wait for post to load
            await page.wait_for_selector('.feed-shared-update-v2', timeout=10000)
            ctx.info(f"Post loaded, performing action: {action}")
            
            # Read post content
            post_content = await page.evaluate('''() => {
                const post = document.querySelector('.feed-shared-update-v2');
                return {
                    author: post.querySelector('.feed-shared-actor__name')?.innerText?.trim() || 'Unknown',
                    content: post.querySelector('.feed-shared-text')?.innerText?.trim() || '',
                    engagementCount: post.querySelector('.social-details-social-counts__reactions-count')?.innerText?.trim() || '0'
                };
            }''')
            
            # Perform the requested action
            if action == "like":
                # Find and click like button if not already liked
                liked = await page.evaluate('''() => {
                    const likeButton = document.querySelector('button.react-button__trigger');
                    const isLiked = likeButton.getAttribute('aria-pressed') === 'true';
                    if (!isLiked) {
                        likeButton.click();
                        return true;
                    }
                    return false;
                }''')
                
                result = {
                    "status": "success",
                    "action": "like",
                    "performed": liked,
                    "message": "Successfully liked the post" if liked else "Post was already liked"
                }
                
            elif action == "comment" and comment:
                # Add comment to the post
                await page.click('button.comments-comment-box__trigger')  # Open comment box
                await page.fill('.ql-editor', comment)
                await page.click('button.comments-comment-box__submit-button')  # Submit comment
                
                # Wait for comment to appear
                await page.wait_for_timeout(2000)
                
                result = {
                    "status": "success",
                    "action": "comment",
                    "message": "Comment posted successfully"
                }
                
            else:  # action == "read"
                result = {
                    "status": "success",
                    "action": "read",
                    "post": post_content
                }
                
            await session.save_session(page)
            return result
            
        except Exception as e:
            ctx.error(f"Post interaction failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to interact with post: {str(e)}"
            }
        
        

def _get_comment_tracking_path():
    """Get path to the comment tracking data directory"""
    tracking_dir = Path(__file__).parent / 'data' / 'comment_tracking'
    tracking_dir.mkdir(parents=True, exist_ok=True)
    return tracking_dir


def _post_url_to_key(post_url: str) -> str:
    """Convert a post URL to a safe filename key"""
    import hashlib
    return hashlib.md5(post_url.encode()).hexdigest()


def _load_tracked_comments(post_url: str) -> dict:
    """Load previously tracked comments for a post"""
    tracking_dir = _get_comment_tracking_path()
    key = _post_url_to_key(post_url)
    tracking_file = tracking_dir / f'{key}.json'
    if tracking_file.exists():
        with open(tracking_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"post_url": post_url, "comments": [], "last_checked": None}


def _save_tracked_comments(post_url: str, data: dict):
    """Save tracked comments for a post"""
    tracking_dir = _get_comment_tracking_path()
    key = _post_url_to_key(post_url)
    tracking_file = tracking_dir / f'{key}.json'
    with open(tracking_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@mcp.tool()
async def track_post_comments(
    post_url: str,
    ctx: Context,
    auto_refresh: bool = False,
    interval_seconds: int = 60,
    max_checks: int = 10
) -> dict:
    """Track comments on a LinkedIn post — detect new comments since last check.

    First call loads all comments and saves them. Subsequent calls return only NEW comments.
    With auto_refresh=True, polls repeatedly at the given interval.

    Args:
        post_url: LinkedIn post URL
        ctx: MCP context for logging and progress reporting
        auto_refresh: If True, automatically re-check for new comments (default: False)
        interval_seconds: Seconds between checks when auto_refresh=True (default: 60, min: 30)
        max_checks: Maximum number of auto-refresh checks (default: 10, max: 50)

    Returns:
        dict: Contains status, new_comments, all_comments, and tracking metadata
    """
    if not ('linkedin.com/posts/' in post_url or 'linkedin.com/feed/update/' in post_url):
        return {
            "status": "error",
            "message": "Invalid LinkedIn post URL"
        }

    interval_seconds = max(30, interval_seconds)
    max_checks = min(max_checks, 50)

    # Load previous tracking data
    tracking_data = _load_tracked_comments(post_url)
    known_comments = tracking_data.get("comments", [])
    known_keys = {(c.get("author", "") + ":" + c.get("content", "")[:100]) for c in known_comments}

    all_new_comments = []
    check_count = 0
    checks_performed = []

    while True:
        check_count += 1
        ctx.info(f"Check #{check_count}: Fetching comments from post...")

        # Fetch current comments
        result = await get_post_comments(post_url, ctx, save_to_file=False)

        if result.get("status") != "success":
            return {
                "status": "error",
                "message": f"Failed to fetch comments on check #{check_count}: {result.get('message', 'Unknown error')}",
                "new_comments_so_far": all_new_comments,
                "checks_performed": check_count
            }

        current_comments = result.get("comments", [])

        # Find new comments
        new_in_this_check = []
        for comment in current_comments:
            key = comment.get("author", "") + ":" + comment.get("content", "")[:100]
            if key not in known_keys:
                new_in_this_check.append(comment)
                known_keys.add(key)
                all_new_comments.append(comment)

        checks_performed.append({
            "check_number": check_count,
            "timestamp": int(time.time()),
            "total_comments": len(current_comments),
            "new_comments": len(new_in_this_check)
        })

        if new_in_this_check:
            ctx.info(f"Check #{check_count}: Found {len(new_in_this_check)} new comment(s)!")
        else:
            ctx.info(f"Check #{check_count}: No new comments")

        # Update tracking data with all known comments
        all_known = known_comments + all_new_comments
        tracking_data = {
            "post_url": post_url,
            "comments": all_known,
            "last_checked": int(time.time()),
            "total_checks": tracking_data.get("total_checks", 0) + 1
        }
        _save_tracked_comments(post_url, tracking_data)

        # If not auto-refreshing, or we've reached max checks, stop
        if not auto_refresh or check_count >= max_checks:
            break

        ctx.info(f"Waiting {interval_seconds}s before next check...")
        await asyncio.sleep(interval_seconds)

    is_first_check = len(known_comments) == 0 and check_count == 1

    return {
        "status": "success",
        "post_url": post_url,
        "is_first_load": is_first_check,
        "new_comments": all_new_comments,
        "new_count": len(all_new_comments),
        "total_tracked": len(tracking_data["comments"]),
        "checks_performed": checks_performed,
        "message": (
            f"Initial load: {len(all_new_comments)} comments saved for tracking."
            if is_first_check
            else f"Found {len(all_new_comments)} new comment(s) across {check_count} check(s)."
        )
    }


if __name__ == "__main__":
    try:
        logger.debug("Starting LinkedIn MCP Server with debug logging")
        
        # Initialize MCP server with simple configuration
        try:
            handle_notification(None, "initialized")  # Pass None for ctx during initialization
            mcp.run(transport='stdio')
        except KeyboardInterrupt:
            handle_notification(None, "cancelled", {"reason": "Server stopped by user"})
            logger.info("Server stopped by user")
        except Exception as e:
            handle_notification(None, "cancelled", {"reason": str(e)})
            logger.error(f"Server error: {str(e)}", exc_info=True)
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Startup error: {str(e)}", exc_info=True)
        sys.exit(1)
        
