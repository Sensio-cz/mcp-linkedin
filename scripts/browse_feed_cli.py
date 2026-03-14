"""CLI pro načtení LinkedIn feedu - volá browse_linkedin_feed přímo."""
import asyncio
import sys
from pathlib import Path

# Přidat parent do path
sys.path.insert(0, str(Path(__file__).parent))

# Mock Context pro CLI
class MockContext:
    def info(self, msg): print(f"[INFO] {msg}", file=sys.stderr)
    def warning(self, msg): print(f"[WARN] {msg}", file=sys.stderr)
    def error(self, msg): print(f"[ERR] {msg}", file=sys.stderr)
    def report_progress(self, a, b, msg=None): pass

async def main():
    from linkedin_browser_mcp import browse_linkedin_feed
    ctx = MockContext()
    result = await browse_linkedin_feed(ctx, count=5)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
