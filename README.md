# MCP LinkedIn Server

MCP server pro automatizaci LinkedIn — vyhledávání profilů, čtení feedu, lajkování a komentování příspěvků. Vhodné pro obchodní a marketingové účely (lead generation, social selling).

## Technologie

- Python, FastMCP, Playwright (browser automation)
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
pip install -r requirements.txt
playwright install chromium
```

## Konfigurace

1. Zkopíruj `.env.example` na `.env`
2. Doplň `LINKEDIN_USERNAME` a `LINKEDIN_PASSWORD`
3. Pro první přihlášení spusť `python login_standalone.py`

## Spuštění MCP serveru

Pro Cursor: konfigurace v `.mcp.json` (viz [Sensio OS mcp-linkedin-setup](https://github.com/Sensio-cz/Sensio-os/blob/main/blueprints/infrastructure/mcp-linkedin-setup.md)).

## Skripty

| Skript | Popis |
|--------|-------|
| `linkedin_browser_mcp.py` | MCP server (spouští Cursor) |
| `login_standalone.py` | První přihlášení |
| `browse_feed_standalone.py` | Načtení feedu |
| `create_post_standalone.py` | Zveřejnění příspěvku |
| `browse_my_posts.py` | Načtení vlastních příspěvků |
