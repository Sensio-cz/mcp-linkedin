# Refaktoring MCP LinkedIn — Implementační plán

## Souhrn
Rozsekat monolit `linkedin_browser_mcp.py` (1234 řádků) do modulární struktury, zpřísnit bezpečnost, přidat testy, aktualizovat README.

## Nová struktura

```
mcp-linkedin/
├── linkedin_mcp/              # Python package
│   ├── __init__.py            # Package init, verze
│   ├── config.py              # Konstanty, timeouty, retry counts
│   ├── selectors.py           # Všechny CSS selektory jako pojmenované konstanty
│   ├── session_store.py       # Cookie šifrování/dešifrování, persistence, expirace
│   ├── browser.py             # BrowserSession context manager, launch config
│   ├── auth.py                # Login flows (login_linkedin, login_linkedin_secure)
│   ├── linkedin_client.py     # Veškerá LinkedIn logika (feed, profily, posty, komentáře)
│   ├── mcp_tools.py           # FastMCP tool definice (tenké wrappery volající linkedin_client)
│   └── helpers.py             # report_progress, handle_notification, _post_url_to_key, etc.
├── scripts/                   # Standalone skripty (přesunuté, aktualizované importy)
│   ├── login_standalone.py
│   ├── browse_feed_standalone.py
│   ├── create_post_standalone.py
│   ├── browse_my_posts.py
│   ├── get_post_comments_standalone.py
│   ├── merge_all_posts.py
│   ├── compare_posts.py
│   └── dump_comment_structure.py
├── tests/
│   ├── __init__.py
│   ├── test_selectors.py      # Testy konzistence selektorů
│   ├── test_session_store.py  # Testy cookie šifrování/expirace
│   ├── test_config.py         # Testy konfigurací
│   ├── test_helpers.py        # Testy helper funkcí
│   └── test_imports.py        # Smoke testy importů všech modulů
├── server.py                  # Entry point (nahrazuje linkedin_browser_mcp.py)
├── pyproject.toml             # Moderní packaging
├── requirements.txt           # Zachováno pro zpětnou kompatibilitu
├── README.md                  # Aktualizované README
├── .env.example
├── .gitignore
└── data/
    └── .gitkeep
```

## Kroky implementace

### Krok 1: Vytvořit package strukturu
- Vytvořit `linkedin_mcp/` adresář s `__init__.py`
- Vytvořit `tests/` adresář s `__init__.py`
- Vytvořit `scripts/` adresář

### Krok 2: Extrahovat `config.py`
- Timeouty (login 5min, selektory 5-60s, scroll delays)
- Retry konstanty (max_attempts=3, delays)
- Browser launch argumenty
- User-Agent string
- Viewport rozměry
- Max scroll counts
- **Zpřísnit file permissions**: 0o700 pro sessions dir, 0o600 pro cookie soubory

### Krok 3: Extrahovat `selectors.py`
- Všechny CSS selektory z page.evaluate() a wait_for_selector()
- Pojmenované konstanty (FEED_POST, FEED_AUTHOR, FEED_CONTENT, COMMENT_ENTITY, etc.)
- Regex patterny pro reply detection (CZ + EN)

### Krok 4: Extrahovat `session_store.py`
- `setup_sessions_directory()` — s oprávněními 0o700
- `get_or_create_encryption_key()`
- `save_cookies(page, platform)` — s oprávněními 0o600
- `load_cookies()` — včetně 7-day expirace
- Cookie encryption/decryption přes Fernet

### Krok 5: Extrahovat `browser.py`
- `BrowserSession` context manager (celá třída)
- Browser launch konfigurace
- Retry logika pro browser launch

### Krok 6: Extrahovat `helpers.py`
- `report_progress()`
- `handle_notification()`
- `_get_comment_tracking_path()`
- `_post_url_to_key()`
- `_load_tracked_comments()`
- `_save_tracked_comments()`

### Krok 7: Extrahovat `auth.py`
- `login_linkedin()` — kompletní login flow
- `login_linkedin_secure()` — wrapper s env credentials

### Krok 8: Extrahovat `linkedin_client.py`
- `browse_feed(session, count)` — čistá logika bez MCP dekorátorů
- `search_profiles(session, query, count)`
- `view_profile(session, profile_url)`
- `get_profile_posts(session, profile_url, count)`
- `get_post_comments(session, post_url, save_to_file, load_all)`
- `track_post_comments(session, post_url, auto_refresh, interval, max_checks)`
- `interact_with_post(session, post_url, action, comment)`
- **Odstranit duplicitní track_post_comments** (řádek 937 vs 1102) — zachovat pokročilou verzi

### Krok 9: Vytvořit `mcp_tools.py`
- FastMCP instance
- Tenké @mcp.tool() wrappery volající linkedin_client funkce
- Zachovat přesně stejné MCP API (názvy, parametry, return typy)

### Krok 10: Vytvořit `server.py` (entry point)
- Import FastMCP instance z mcp_tools
- Inicializace (sessions dir, dotenv)
- `mcp.run(transport='stdio')`
- Zachovat linkedin_browser_mcp.py jako symlink/redirect pro zpětnou kompatibilitu

### Krok 11: Přesunout standalone skripty do `scripts/`
- Přesunout všechny *_standalone.py, browse_my_posts.py, merge_all_posts.py, compare_posts.py, dump_comment_structure.py, login_cli.py, browse_feed_cli.py
- Aktualizovat importy na nový package

### Krok 12: Napsat testy
- `test_imports.py` — smoke test importů všech modulů
- `test_selectors.py` — test že selektory jsou neprázdné stringy, žádné duplikáty
- `test_session_store.py` — mock testy encrypt/decrypt cookies, expirace
- `test_helpers.py` — test _post_url_to_key, report_progress
- `test_config.py` — test defaultních hodnot

### Krok 13: Vytvořit `pyproject.toml`
- Metadata, dependencies (z requirements.txt)
- Test dependencies (pytest)
- Entry point pro server

### Krok 14: Aktualizovat README
- Přeframovat jako "interní výzkumný/prototypový nástroj"
- Přidat explicitní ToS varování a disclaimer o riziku účtu
- Aktualizovat instalaci a strukturu pro nový package
- Aktualizovat tabulku skriptů

### Krok 15: Aktualizovat .gitignore
- Přidat `*.egg-info/`, `dist/`, `build/`

### Krok 16: Commit a push
