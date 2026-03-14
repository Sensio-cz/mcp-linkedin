"""All LinkedIn CSS selectors and regex patterns as named constants.

When LinkedIn changes their DOM, update *only this file*.
"""

import re

# ── Feed ───────────────────────────────────────────────────────────────────
FEED_POST = ".feed-shared-update-v2"
FEED_POST_ALT = "[data-urn]"
FEED_AUTHOR = ".feed-shared-actor__name"
FEED_HEADLINE = ".feed-shared-actor__description"
FEED_CONTENT = ".feed-shared-text"
FEED_CONTENT_ALT = ".break-words"
FEED_TIMESTAMP = ".feed-shared-actor__sub-description"
FEED_TIMESTAMP_ALT = "time"
FEED_LIKES = ".social-details-social-counts__reactions-count"
FEED_COMMENTS_COUNT = ".social-details-social-counts__comments"
FEED_REPOSTS_COUNT = ".social-details-social-counts__item--with-social-proof"

# ── Feed media detection ──────────────────────────────────────────────────
FEED_IMAGE = ".feed-shared-image"
FEED_IMAGE_ALT = "img.ivm-view-attr__img--centered"
FEED_VIDEO = ".feed-shared-linkedin-video"
FEED_VIDEO_ALT = "video"
FEED_DOCUMENT = ".feed-shared-document"

# ── Post permalink ────────────────────────────────────────────────────────
FEED_PERMALINK = 'a[href*="/feed/update/"]'

# ── Search results ────────────────────────────────────────────────────────
SEARCH_RESULT = ".reusable-search__result-container"
SEARCH_NAME = ".entity-result__title-text a"
SEARCH_HEADLINE = ".entity-result__primary-subtitle"
SEARCH_LOCATION = ".entity-result__secondary-subtitle"
SEARCH_LINK = ".app-aware-link"
SEARCH_DEGREE = ".dist-value"
SEARCH_SNIPPET = ".entity-result__summary"

# ── Profile ───────────────────────────────────────────────────────────────
PROFILE_CARD = ".pv-top-card"
PROFILE_NAME = ".pv-top-card--list .text-heading-xlarge"
PROFILE_HEADLINE = ".pv-top-card--list .text-body-medium"
PROFILE_LOCATION = ".pv-top-card--list .text-body-small:not(.inline)"
PROFILE_CONNECTIONS = ".pv-top-card__connections-count .t-black--light"
PROFILE_ABOUT = ".pv-shared-text-with-see-more .inline-show-more-text"
PROFILE_EXPERIENCE = "#experience-section .pv-entity__summary-info"
PROFILE_EDUCATION = "#education-section .pv-education-entity"

# ── Comments ──────────────────────────────────────────────────────────────
COMMENT_ENTITY = ".comments-comment-entity"
COMMENT_ITEM = ".comments-comment-item"
COMMENT_ARTICLE = "article[data-id]"
COMMENT_ALL = f"{COMMENT_ENTITY}, {COMMENT_ITEM}, {COMMENT_ARTICLE}"
COMMENT_REPLY_CLASS = "comments-comment-entity--reply"
COMMENT_REPLY_ITEM_CLASS = "comments-comment-item--reply"
COMMENT_REPLY_SELECTOR = f".{COMMENT_REPLY_CLASS}, .{COMMENT_REPLY_ITEM_CLASS}"

COMMENT_AUTHOR_TITLE = ".comments-comment-meta__description-title"
COMMENT_AUTHOR_NAME = ".comments-comment-actor__name"
COMMENT_AUTHOR_META = ".comments-post-meta__name-text"
COMMENT_AUTHOR_SELECTORS = [
    COMMENT_AUTHOR_TITLE,
    COMMENT_AUTHOR_NAME,
    COMMENT_AUTHOR_META,
    '[class*="actor__name"]',
]

COMMENT_CONTENT = ".comments-comment-item__main-content"
COMMENT_CONTENT_ALT = '[class*="comment-item__content"]'
COMMENT_CONTENT_ENTITY = '.comments-comment-entity__content [class*="main-content"]'

COMMENT_TIMESTAMP = "time.comments-comment-meta__data"
COMMENT_TIMESTAMP_ALT = ".comments-comment-item__timestamp"
COMMENT_TIMESTAMP_GENERIC = '[class*="timestamp"]'

COMMENT_SOCIAL_BAR = ".comment-social-activity"
COMMENT_SOCIAL_ALT = '[class*="comment-social"], [class*="social-activity"]'

COMMENT_TRIGGER = 'button.social-details-social-counts__comments, [class*="comments-count"]'
COMMENT_LOAD_MORE = 'button:has-text("See more"), button:has-text("Load more"), span:has-text("See more comments")'

COMMENT_META_ACTOR = ".comments-comment-meta__actor"
COMMENT_META_IMAGE_LINK = 'a.comments-comment-meta__image-link[href*="/in/"]'

# ── Comment reactions regex (CZ + EN) ─────────────────────────────────────
REACTION_RE = re.compile(
    r'(?:Líbí se|Like)\s*(\d+)|(\d+)\s*(?:Reaction|Reakce)s?', re.I
)

# ── Reply expansion regex (CZ + EN) ──────────────────────────────────────
VIEW_REPLIES_RE = re.compile(
    r'View\s+\d+\s+repl|Zobrazit\s+\d+\s+odpověd', re.I
)
REPLY_COUNT_PATTERNS = [
    re.compile(r'View\s+(\d+)\s+repl', re.I),
    re.compile(r'(\d+)\s+repl', re.I),
    re.compile(r'Zobrazit\s+(\d+)\s+odpov', re.I),
    re.compile(r'(\d+)\s+odpov', re.I),
]

# ── Post interaction ──────────────────────────────────────────────────────
LIKE_BUTTON = "button.react-button__trigger"
COMMENT_BOX_TRIGGER = "button.comments-comment-box__trigger"
COMMENT_EDITOR = ".ql-editor"
COMMENT_SUBMIT = "button.comments-comment-box__submit-button"

# ── Profile viewers ───────────────────────────────────────────────────────
VIEWERS_LIST_ITEM = ".profile-views__list-item, .entity-result__item, [data-view-name='profile-view-entity']"
VIEWERS_NAME = "a[href*='/in/']"
VIEWERS_HEADLINE = ".profile-views__subtitle, .entity-result__primary-subtitle, [class*='subtitle']"
VIEWERS_TIME = ".profile-views__date, time, [class*='timestamp']"
VIEWERS_CONNECT_BTN = "button:has-text('Connect'), button:has-text('Spojit'), button[aria-label*='Connect'], button[aria-label*='Spojit']"

# ── Connection request ────────────────────────────────────────────────────
CONNECT_BUTTON = "button:has-text('Connect'), button:has-text('Spojit se'), button[aria-label*='Connect']"
CONNECT_SEND_NOW = "button:has-text('Send now'), button:has-text('Odeslat'), button[aria-label*='Send now']"
CONNECT_ADD_NOTE = "button:has-text('Add a note'), button:has-text('Přidat poznámku')"
CONNECT_NOTE_FIELD = "textarea[name='message'], textarea#custom-message, .send-invite__custom-message"
CONNECT_SEND_BTN = "button[aria-label*='Send'], button:has-text('Send'), button:has-text('Odeslat')"
