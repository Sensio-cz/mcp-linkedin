#!/usr/bin/env python3
"""Standalone script to load comments from a LinkedIn post. Usage: python get_post_comments_standalone.py <post_url> [--save]"""
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from linkedin_browser_mcp import get_post_comments


class SimpleContext:
    def info(self, msg): print(f"[INFO] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")
    def warning(self, msg): print(f"[WARNING] {msg}")


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    save = "--save" in sys.argv or "-s" in sys.argv
    if not url:
        print("Usage: python get_post_comments_standalone.py <post_url> [--save]")
        sys.exit(1)
    ctx = SimpleContext()
    result = await get_post_comments(url, ctx, save_to_file=save)
    if result.get("status") == "success":
        for i, c in enumerate(result.get("comments", []), 1):
            print(f"\n--- Komentář {i}: {c.get('author', '?')} ({c.get('timestamp', '')}) ---")
            print(f"Reakce: {c.get('reactions', 0)}, Podkomentáře: {c.get('replies', 0)}")
            print(c.get("content", "")[:200] + ("..." if len(c.get("content", "")) > 200 else ""))
        print(f"\nCelkem: {result.get('count', 0)} komentářů")
        if result.get("saved_to"):
            print(f"Uloženo do: {result['saved_to']}")
    else:
        print(f"Chyba: {result.get('message', 'Unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
