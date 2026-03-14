"""
Sloučí linkedin-posts-raw.json s kopií do jednoho kompletního souboru.
Zachová všechny unikátní příspěvky (podle content[:150]) a doplní metadata z novější verze.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent / 'data'
CURRENT = DATA_DIR / 'linkedin-posts-raw.json'
KOPIE = DATA_DIR / 'linkedin-posts-raw - kopie.json'
OUTPUT = DATA_DIR / 'linkedin-posts-complete.json'


def decode_linkedin_timestamp(activity_id: str) -> str | None:
    """Z activity ID dekódovat datum."""
    try:
        aid = int(activity_id)
        ts_ms = aid >> 22
        if ts_ms < 1e12:
            ts_ms = ts_ms * 1000
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def main():
    if not KOPIE.exists():
        print(f"Kopie neexistuje: {KOPIE}")
        return

    with open(KOPIE, encoding='utf-8') as f:
        kopie_data = json.load(f)

    # Aktuální soubor (může mít novější metadata)
    curr_by_content = {}
    if CURRENT.exists():
        with open(CURRENT, encoding='utf-8') as f:
            curr_data = json.load(f)
        for p in curr_data.get('posts', []):
            key = p['content'][:150]
            curr_by_content[key] = p

    # Sloučit: kopie jako základ, doplnit metadata z aktuálního
    seen = set()
    merged = []
    for p in kopie_data.get('posts', []):
        key = p['content'][:150]
        if key in seen:
            continue
        seen.add(key)

        # Má aktuální verze lepší metadata?
        curr = curr_by_content.get(key)
        if curr:
            # Použít aktuální (má urn, activity_id, published_at, type, no)
            merged.append(curr)
        else:
            # Pouze z kopie - doplnit základní metadata
            post = dict(p)
            if 'urn' not in post:
                post['urn'] = ''
            if 'activity_id' not in post:
                post['activity_id'] = ''
            if 'published_at' not in post and post.get('activity_id'):
                post['published_at'] = decode_linkedin_timestamp(post['activity_id'])
            else:
                post['published_at'] = None
            if 'type' not in post:
                post['type'] = 'text'
            if 'comments' not in post:
                post['comments'] = ''
            merged.append(post)

    # Seřadit podle published_at (nejnovější první), pak podle pořadí v kopii
    def sort_key(p):
        pa = p.get('published_at')
        if pa:
            return (0, pa)
        return (1, '')

    merged.sort(key=sort_key, reverse=True)

    # Přidat pořadové číslo
    for i, p in enumerate(merged, 1):
        p['no'] = i

    meta = {
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(merged),
        "source": "merge (kopie + aktuální)",
        "profile": kopie_data.get('meta', {}).get('profile', 'jantobolik')
    }

    out = {"status": "success", "meta": meta, "posts": merged}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Sloučeno: {len(merged)} příspěvků → {OUTPUT}")


if __name__ == "__main__":
    main()
