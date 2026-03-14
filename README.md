# MCP LinkedIn Server

> **Interní výzkumný / prototypový nástroj.** Nejedná se o oficiálně podporovaný produkt.

MCP server pro automatizaci LinkedIn — vyhledávání profilů, čtení feedu, lajkování, komentování příspěvků, sledování komentářů a zobrazení návštěvníků profilu. Určeno pro interní experimenty v oblasti lead generation a social selling.

## ⚠️ Upozornění na podmínky LinkedIn (ToS)

**Používání tohoto nástroje může porušovat podmínky používání LinkedIn**, včetně:

- Automatizovaný přístup a scraping obsahu bez výslovného souhlasu LinkedIn
- Automatické odesílání požadavků o spojení
- Crawling a indexování dat z LinkedIn

**Rizika:**
- Dočasné nebo trvalé omezení/zrušení LinkedIn účtu
- Právní následky v případě komerčního nasazení

Tento nástroj je určen **výhradně pro interní výzkum a experimenty**. Použití je na vlastní riziko. Autoři nenesou odpovědnost za případné důsledky.

---

## Technologie

- Python 3.11+, FastMCP, Playwright (browser automation)
- Licence: MIT

## Instalace

```bash
git clone https://github.com/Sensio-cz/mcp-linkedin.git
cd mcp-linkedin
python -m venv env
# Windows:
env\Scripts\activate
# Linux/macOS:
source env/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

## Konfigurace

1. Zkopíruj `.env.example` na `.env`
2. Doplň `LINKEDIN_USERNAME` a `LINKEDIN_PASSWORD`
3. Pro první přihlášení spusť `python scripts/login_standalone.py`

## Spuštění MCP serveru

```bash
python server.py
```

Pro Cursor: konfigurace v `.mcp.json` (viz [Sensio OS mcp-linkedin-setup](https://github.com/Sensio-cz/Sensio-os/blob/main/blueprints/infrastructure/mcp-linkedin-setup.md)).

## Struktura projektu

```
mcp-linkedin/
├── server.py                  # Entry point
├── mcp_linkedin/              # Hlavní Python package
│   ├── config.py              # Konstanty, timeouty, oprávnění
│   ├── selectors.py           # CSS selektory jako pojmenované konstanty
│   ├── session_store.py       # Cookie šifrování/persistence
│   ├── browser.py             # BrowserSession context manager
│   ├── auth.py                # Login flows
│   ├── linkedin_client.py     # LinkedIn logika (feed, profily, komentáře, viewers)
│   ├── mcp_tools.py           # FastMCP @tool definice
│   └── helpers.py             # Utility funkce
├── scripts/                   # Standalone skripty
├── tests/                     # Testy (pytest)
├── pyproject.toml             # Packaging
└── linkedin_browser_mcp.py    # Legacy entry point (deprecated)
```

## MCP nástroje (tools)

| Tool | Popis |
|------|-------|
| `login_linkedin` | Manuální přihlášení přes browser |
| `login_linkedin_secure` | Přihlášení s credentials z `.env` |
| `browse_linkedin_feed` | Načtení feedu |
| `search_linkedin_profiles` | Vyhledávání profilů |
| `view_linkedin_profile` | Detail profilu |
| `get_profile_posts` | Příspěvky profilu |
| `get_post_comments` | Komentáře k příspěvku (rozbalí vlákna) |
| `track_post_comments` | Sledování nových komentářů |
| `interact_with_linkedin_post` | Like / komentář / čtení příspěvku |
| `get_profile_viewers` | **Nové:** Kdo si zobrazil můj profil (filtr: relevantní + nepřipojení) |
| `send_connection_request` | **Nové:** Odeslání žádosti o spojení (volitelně s poznámkou) |

## Standalone skripty

| Skript | Popis |
|--------|-------|
| `scripts/login_standalone.py` | První přihlášení |
| `scripts/browse_feed_standalone.py` | Načtení feedu |
| `scripts/create_post_standalone.py` | Zveřejnění příspěvku |
| `scripts/browse_my_posts.py` | Načtení vlastních příspěvků |
| `scripts/get_post_comments_standalone.py` | Načtení komentářů |

## Testy

```bash
pytest
```

## Bezpečnost

- Cookies jsou šifrovány pomocí Fernet (AES-128-CBC)
- Sessions adresář má oprávnění `0700` (pouze vlastník)
- Cookie soubory mají oprávnění `0600` (pouze vlastník)
- Credentials v `.env` — nikdy necommitovat do gitu
