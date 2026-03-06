"""
lastfm_enrich.py — Fetch community genre/mood tags from Last.fm for each song.

Adds to every song:
  lastfm_tags : ["indie", "90s", "shoegaze", "female vocalist", ...]

Only tags with a weight >= MIN_WEIGHT are kept (filters out obscure/noisy ones).
Songs not found on Last.fm simply get an empty list — no errors.

Run ONCE before embed.py.
Saves progress every 50 songs so it's safe to interrupt and resume.

Rate limit: Last.fm free tier allows ~5 req/sec. We stay well under that.
"""

import json
import os
import time
import urllib.request
import urllib.parse
from dotenv import load_dotenv

load_dotenv('/Users/bartoska/web/yt-music-prototype/.env')

API_KEY    = os.getenv('LASTFM_API_KEY')
BASE_URL   = 'http://ws.audioscrobbler.com/2.0/'
MIN_WEIGHT = 1      # accept all tags — niche artists have very few votes
MAX_TAGS   = 8      # keep top N tags per song
SAVE_EVERY = 50
INPUT_FILE = '/Users/bartoska/web/yt-music-prototype/enriched_songs.json'

if not API_KEY:
    raise SystemExit('Missing LASTFM_API_KEY in .env')

with open(INPUT_FILE) as f:
    songs = json.load(f)

print(f'Loaded {len(songs)} songs')
already_done  = sum(1 for s in songs if s.get('lastfm_tags'))   # non-empty list
already_empty = sum(1 for s in songs if 'lastfm_tags' in s and not s['lastfm_tags'])
print(f'  {already_done} already have tags — keeping')
print(f'  {already_empty} returned empty last time — retrying with lower threshold')
print(f'  {len(songs) - already_done - already_empty} not yet processed\n')


def fetch_tags(params: dict) -> list[str]:
    """Call Last.fm API and return filtered tag list."""
    url = BASE_URL + '?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        tags_data = data.get('toptags', {}).get('tag', [])
        if isinstance(tags_data, dict):
            tags_data = [tags_data]
        return [
            t['name'].lower()
            for t in tags_data
            if int(t.get('count', 0)) >= MIN_WEIGHT
        ]
    except Exception:
        return []


NOISY = {'under 2000 listeners', 'under 5000 listeners', 'seen live',
         'favorites', 'favourite', 'albums i own'}

def get_tags(title: str, artist: str) -> list[str]:
    """Try track tags first, fall back to artist tags if track returns empty."""
    # 1. Track-level tags
    tags = fetch_tags({
        'method':  'track.getTopTags',
        'artist':  artist,
        'track':   title,
        'api_key': API_KEY,
        'format':  'json',
    })

    # 2. Fall back to artist-level tags
    if not tags:
        time.sleep(0.1)
        tags = fetch_tags({
            'method':  'artist.getTopTags',
            'artist':  artist,
            'api_key': API_KEY,
            'format':  'json',
        })

    # Filter noisy tags and return top N
    tags = [t for t in tags if t not in NOISY]
    return tags[:MAX_TAGS]


found    = 0
not_found = 0

for i, song in enumerate(songs):
    # Skip songs that already have tags — only retry empty ones
    if song.get('lastfm_tags'):
        continue

    tags = get_tags(song.get('title', ''), song.get('artist', ''))
    song['lastfm_tags'] = tags

    if tags:
        found += 1
    else:
        not_found += 1

    # Progress every 10 songs
    if (i + 1) % 10 == 0 or (i + 1) == len(songs):
        pct = round((i + 1) / len(songs) * 100)
        print(f'  [{pct:3d}%] {i+1}/{len(songs)} — tagged: {found}, no tags: {not_found}')

    # Checkpoint save every 50
    if (i + 1) % SAVE_EVERY == 0:
        with open(INPUT_FILE, 'w') as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)

    time.sleep(0.25)   # ~4 req/sec — safely under the rate limit

# Final save
with open(INPUT_FILE, 'w') as f:
    json.dump(songs, f, ensure_ascii=False, indent=2)

total = found + not_found
print(f'\n✅ Done. {found}/{total} songs tagged ({round(found/total*100)}%)')
print(f'Saved to {INPUT_FILE}')
print('\nSample tags:')
samples = [s for s in songs if s.get('lastfm_tags')][:5]
for s in samples:
    print(f'  {s["title"]} — {s["artist"]}: {", ".join(s["lastfm_tags"])}')
print('\nNext step: run  python3 embed.py')
