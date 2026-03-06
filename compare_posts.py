"""Porovnání linkedin-posts-raw.json vs kopie."""
import json

with open('data/linkedin-posts-raw.json', encoding='utf-8') as f:
    curr = json.load(f)
with open('data/linkedin-posts-raw - kopie.json', encoding='utf-8') as f:
    kopie = json.load(f)

curr_contents = {p['content'][:150] for p in curr['posts']}
kopie_contents = {p['content'][:150] for p in kopie['posts']}

jen_v_kopii = [p for p in kopie['posts'] if p['content'][:150] not in curr_contents]
jen_v_aktualnim = [p for p in curr['posts'] if p['content'][:150] not in kopie_contents]

print('=== JEN V KOPII (chybí v aktuálním) - počet:', len(jen_v_kopii))
for i, p in enumerate(jen_v_kopii[:20]):
    preview = p['content'][:90].replace('\n', ' ')
    print(f"  {i+1}. {preview}...")
if len(jen_v_kopii) > 20:
    print(f"  ... a dalších {len(jen_v_kopii)-20}")

print()
print('=== JEN V AKTUÁLNÍM (chybí v kopii) - počet:', len(jen_v_aktualnim))
for i, p in enumerate(jen_v_aktualnim[:5]):
    preview = p['content'][:90].replace('\n', ' ')
    print(f"  {i+1}. {preview}...")
