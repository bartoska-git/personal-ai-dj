"""
embed.py — Embed all enriched songs and upload to Supabase pgvector.

Changes from v1:
  - Last.fm tags now included in embedded text (after noise filtering)
  - play_count and last_played stored in Supabase (ranking signals)
  - lastfm_tags stored in Supabase (for future filtering)
  - Model stays text-embedding-3-small (1536 dimensions — no schema migration needed)

Before running: ensure the Supabase songs table has play_count, last_played,
and lastfm_tags columns (run the two ALTER TABLE lines in supabase_migration.sql).
"""

import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
# Uses service role key — needed for INSERT operations (bypasses RLS)
supabase      = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

ENRICHED_PATH = 'enriched_songs.json'
EMBED_MODEL   = 'text-embedding-3-small'   # 1536 dimensions
EMBED_BATCH   = 100
INSERT_BATCH  = 50

# Tags that add no musical meaning — excluded from embedded text
NOISY_TAGS = {
    'all', 'soty', 'seen live', 'favorites', 'favourite', 'albums i own',
    'under 2000 listeners', 'under 5000 listeners', 'under 1000 listeners',
    'best of 2025', 'best of 2024', 'best of 2023', 'best of 2022',
    'love it', 'awesome', 'cool', 'great', 'beautiful',
}
def clean_tags(tags: list) -> list:
    result = []
    for t in (tags or []):
        tl = t.lower()
        if tl in NOISY_TAGS:
            continue
        if any(x in tl for x in ['fm ', ' fm', 'radio', 'the bookshelf', 'listeners']):
            continue
        result.append(t)
    return result

# ── Load enriched songs ───────────────────────────────────────────────────────
with open(ENRICHED_PATH) as f:
    songs = json.load(f)

songs = [s for s in songs if s.get('description')]
print(f'Enriched songs available: {len(songs)}')
print(f'Songs with play history:  {sum(1 for s in songs if s.get("play_count"))}')

# ── Check what's already in Supabase ─────────────────────────────────────────
count_resp = supabase.table('songs').select('id', count='exact').execute()
already_in = count_resp.count or 0
print(f'Already in Supabase:      {already_in}')

if already_in > 0:
    print(f'\nClearing {already_in} existing rows and re-uploading cleanly...')
    supabase.table('songs').delete().neq('id', 0).execute()

print(f'\nUploading {len(songs)} songs...\n')

# ── Build the text we embed for each song ────────────────────────────────────
# Title intentionally excluded — avoids literal keyword matching
# (searching "sad" shouldn't surface songs just because "sad" is in the title)
# Tags appended after description for genre/mood signal boost.
def embed_text(song: dict) -> str:
    parts = [f"Artist: {song['artist']}"]
    if song.get('album'):
        parts.append(f"Album: {song['album']}")
    parts.append(song['description'])
    tags = clean_tags(song.get('lastfm_tags', []))
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    return ' — '.join(parts)

# ── Main loop ─────────────────────────────────────────────────────────────────
total         = len(songs)
total_batches = (total + EMBED_BATCH - 1) // EMBED_BATCH
uploaded      = 0

for i in range(0, total, EMBED_BATCH):
    batch     = songs[i:i + EMBED_BATCH]
    batch_num = i // EMBED_BATCH + 1

    print(f'Batch {batch_num}/{total_batches}: embedding + uploading {len(batch)} songs...', end=' ', flush=True)

    try:
        # 1. Embed
        texts      = [embed_text(s) for s in batch]
        emb_resp   = openai_client.embeddings.create(model=EMBED_MODEL, input=texts)
        embeddings = [r.embedding for r in emb_resp.data]

        # 2. Build rows
        rows = []
        for j, song in enumerate(batch):
            row = {
                'video_id':    song.get('videoId'),
                'title':       song['title'],
                'artist':      song['artist'],
                'album':       song.get('album') or '',
                'description': song['description'],
                'sources':     song.get('sources', []),
                'embedding':   embeddings[j],
                'lastfm_tags': clean_tags(song.get('lastfm_tags', [])),
            }
            if song.get('play_count'):
                row['play_count'] = song['play_count']
            if song.get('last_played'):
                row['last_played'] = song['last_played']
            rows.append(row)

        # 3. Insert in sub-batches
        for k in range(0, len(rows), INSERT_BATCH):
            supabase.table('songs').insert(rows[k:k + INSERT_BATCH]).execute()

        uploaded += len(batch)
        print(f'✓  ({uploaded}/{total})')

    except Exception as e:
        print(f'FAILED: {e}')

    if i + EMBED_BATCH < total:
        time.sleep(0.2)

print(f'\n✅ Done! {uploaded} songs embedded and uploaded to Supabase 🎵')
