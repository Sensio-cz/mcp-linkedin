"""CLI pro prihlaseni na LinkedIn - otevře prohlížeč."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

class MockContext:
    def info(self, msg): print(f"[INFO] {msg}", flush=True)
    def warning(self, msg): print(f"[WARN] {msg}", flush=True)
    def error(self, msg): print(f"[ERR] {msg}", flush=True)

async def main():
    print("Spouštím přihlášení - měl by se otevřít prohlížeč...", flush=True)
    try:
        from linkedin_browser_mcp import login_linkedin_secure
        ctx = MockContext()
        result = await login_linkedin_secure(ctx)
        print(f"Výsledek: {result}", flush=True)
    except Exception as e:
        print(f"CHYBA: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
