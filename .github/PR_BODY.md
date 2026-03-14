## Summary

Rozsekaný monolit `linkedin_browser_mcp.py` (1 234 řádků) do modulárního package `mcp_linkedin/` s 8 moduly. Přidány 2 nové MCP tools pro práci s návštěvníky profilu. Zpřísněna bezpečnost, přidány testy, aktualizováno README.

## Changes

- [x] Rozsekat `linkedin_browser_mcp.py` do `mcp_linkedin/` package (config, selectors, session_store, browser, auth, linkedin_client, mcp_tools, helpers)
- [x] Nový MCP tool `get_profile_viewers` — načtení relevantních návštěvníků profilu (AI, CEO, vývojáři, automatizace) kteří nejsou ve spojení
- [x] Nový MCP tool `send_connection_request` — odeslání žádosti o spojení s volitelnou poznámkou
- [x] Zpřísnění oprávnění: sessions dir `0o777` → `0o700`, cookie soubory `0o666` → `0o600`
- [x] Odstranění duplicitní definice `track_post_comments`
- [x] 161 testů (config, selektory, helpers, session store, smoke importy)
- [x] `pyproject.toml` pro moderní packaging
- [x] Standalone skripty přesunuty do `scripts/`
- [x] README přeframeováno jako interní výzkumný nástroj + ToS varování

## Detailní popis

### Modulární package `mcp_linkedin/`

| Modul | Řádků | Odpovědnost |
|-------|-------|-------------|
| `config.py` | 62 | Centralizované konstanty — timeouty, retry counts, browser args, viewport, permissions, klíčová slova pro filtr relevance |
| `selectors.py` | 120 | Všechny CSS selektory jako pojmenované konstanty + regex patterny (CZ/EN). Když LinkedIn změní DOM, opravuje se jen tento soubor |
| `session_store.py` | 88 | Cookie šifrování (Fernet), persistence, expirace (7 dní), setup sessions directory |
| `browser.py` | 124 | `BrowserSession` context manager — Playwright lifecycle, retry logika, launch config |
| `auth.py` | 67 | `login_linkedin()` a `login_linkedin_secure()` |
| `linkedin_client.py` | 827 | Veškerá LinkedIn interakční logika — feed, search, profiles, posts, comments, profile viewers, connection requests |
| `mcp_tools.py` | 168 | Tenké `@mcp.tool()` wrappery volající `linkedin_client` funkce. Žádná business logika |
| `helpers.py` | 68 | Progress reporting, comment tracking persistence |

### Nové MCP tools

**`get_profile_viewers`** — naviguje na `/me/profile-views/`, extrahuje jméno, headline, profil URL, čas zobrazení, degree. Parametry:
- `only_relevant=True` — filtruje podle klíčových slov v headline (AI, machine learning, CEO, founder, developer, automatizace, CTO, data scientist, …)
- `only_not_connected=True` — vyloučí 1st-degree connections

**`send_connection_request`** — naviguje na profil, klikne Connect, volitelně přidá personalizovanou poznámku. Detekuje již existující spojení (`status: "skipped"`). Fallback na "More" dropdown.

### Bezpečnost

| Co | Bylo | Je |
|----|------|----|
| Sessions directory | `0o777` (rwxrwxrwx) | `0o700` (rwx------) |
| Cookie soubory | `0o666` (rw-rw-rw-) | `0o600` (rw-------) |

### Testy (161)

| Test soubor | Pokrývá |
|-------------|---------|
| `test_imports.py` | Smoke testy — všechny moduly se importují bez chyb |
| `test_selectors.py` | Všechny selektory neprázdné, regex matchují CZ/EN vstupy |
| `test_session_store.py` | Encryption key generace, env var override, directory permissions |
| `test_helpers.py` | `post_url_to_key` determinismus, `report_progress`, comment tracking save/load |
| `test_config.py` | Default hodnoty — permissions, cookie expiry, browser args, keywords |

### Breaking changes

- Entry point: `linkedin_browser_mcp.py` → `server.py` (starý soubor ponechán jako deprecated)
- Standalone skripty: root → `scripts/` (cesty v `.mcp.json` je třeba aktualizovat)

### Nová struktura

```
mcp-linkedin/
├── server.py                  # Nový entry point
├── mcp_linkedin/              # Hlavní package (8 modulů)
├── scripts/                   # Standalone skripty (přesunuté z root)
├── tests/                     # 161 testů
├── pyproject.toml             # Moderní packaging
├── linkedin_browser_mcp.py    # Legacy (deprecated)
└── data/
```

## Status transitions

| Soubor | Předchozí status | Nový status |
|--------|-----------------|-------------|
| `linkedin_browser_mcp.py` | aktivní | deprecated |
| `server.py` | N/A | nový entry point |
| `mcp_linkedin/` | N/A | nový package |

## Source of truth

- [x] AI generováno
- [x] Konzultace s týmem (audit kódu jako vstup)

## Checklist

- [x] Obsah je v češtině
- [x] Konzistentní s existujícím obsahem
- [x] Testy prochází (161 passed)

## Test plan

- [x] `pytest` — 161 testů prochází
- [ ] Manuální test: `python server.py` spustí MCP server přes stdio
- [ ] Manuální test: `get_profile_viewers` v Cursoru vrátí relevantní viewers
- [ ] Manuální test: `send_connection_request` odešle žádost
- [ ] Ověřit Cursor `.mcp.json` konfiguraci s novým entry pointem
