"""
enrich.py — Generate mood/vibe descriptions for every song.

For songs that have Spotify audio features (from spotify_enrich.py):
  → GPT is given the REAL BPM, energy, danceability, valence, etc.
  → GPT only needs to fill in texture, mood language, and context
  → No more guessing tempo or energy from the song title!

For songs without Spotify data (niche/world music not on Spotify):
  → Falls back to the original prompt (GPT infers everything)

Run order:
  1. python3.12 spotify_enrich.py   (fetch Spotify features — one-time)
  2. python3.12 enrich.py           (this script)
  3. python3.12 embed.py            (re-upload embeddings)
"""

import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv('/Users/bartoska/web/yt-music-prototype/.env')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

SONGS_PATH     = '/Users/bartoska/web/yt-music-prototype/enriched_songs.json'
ENRICHED_PATH  = '/Users/bartoska/web/yt-music-prototype/enriched_songs.json'
BATCH_SIZE     = 20


# ── Load songs ────────────────────────────────────────────────────────────────
with open(SONGS_PATH) as f:
    all_songs = json.load(f)

print(f"Loaded {len(all_songs)} songs")

spotify_count = sum(1 for s in all_songs if s.get("spotify_features"))
print(f"  {spotify_count} have Spotify audio features")
print(f"  {len(all_songs) - spotify_count} will use GPT inference only\n")


# ── Resume support ────────────────────────────────────────────────────────────
# We re-enrich ALL songs (overwrite existing descriptions) to use new prompt.
# Remove 'description' from all songs so we start fresh.
for s in all_songs:
    s.pop('description', None)

to_enrich = all_songs
total_batches = (len(to_enrich) + BATCH_SIZE - 1) // BATCH_SIZE
print(f"Songs to enrich: {len(to_enrich)}")
print(f"Batches: {total_batches} × up to {BATCH_SIZE} songs each\n")


# ── Helpers ───────────────────────────────────────────────────────────────────
def tempo_label(bpm: float) -> str:
    if bpm < 70:   return f"{bpm} BPM (slow)"
    if bpm < 100:  return f"{bpm} BPM (mid-tempo)"
    if bpm < 130:  return f"{bpm} BPM (uptempo)"
    return f"{bpm} BPM (fast-paced)"

def energy_label(e: float) -> str:
    if e < 0.25:  return f"{e:.2f} (quiet and intimate)"
    if e < 0.45:  return f"{e:.2f} (gentle)"
    if e < 0.65:  return f"{e:.2f} (moderate)"
    if e < 0.82:  return f"{e:.2f} (high-energy)"
    return f"{e:.2f} (intense and driving)"

def valence_label(v: float) -> str:
    if v < 0.25:  return f"{v:.2f} (melancholic / dark)"
    if v < 0.45:  return f"{v:.2f} (bittersweet)"
    if v < 0.65:  return f"{v:.2f} (neutral)"
    if v < 0.80:  return f"{v:.2f} (upbeat)"
    return f"{v:.2f} (euphoric / joyful)"

def dance_label(d: float) -> str:
    if d < 0.35:  return f"{d:.2f} (not for dancing)"
    if d < 0.55:  return f"{d:.2f} (mildly rhythmic)"
    if d < 0.72:  return f"{d:.2f} (groovy)"
    return f"{d:.2f} (very danceable)"


def make_song_entry(i: int, song: dict) -> str:
    """Format a single song entry for the prompt, including Spotify data if available."""
    line = f'{i+1}. "{song["title"]}" by {song["artist"]}'
    if song.get('album'):
        line += f' (album: {song["album"]})'

    sf = song.get("spotify_features")
    if sf:
        facts = [
            f"Tempo: {tempo_label(sf['bpm'])}",
            f"Energy: {energy_label(sf['energy'])}",
            f"Danceability: {dance_label(sf['danceability'])}",
            f"Valence (mood positivity): {valence_label(sf['valence'])}",
            f"Acousticness: {sf['acousticness']:.2f} ({'mostly acoustic' if sf['acousticness'] > 0.6 else 'produced/electronic'})",
            f"Instrumentalness: {sf['instrumentalness']:.2f} ({'no vocals' if sf['instrumentalness'] > 0.5 else 'has vocals'})",
        ]
        line += "\n   [MEASURED DATA — use exactly as given, do not contradict these values]\n   " + "\n   ".join(facts)

    return line


def enrich_batch(batch: list) -> list[str]:
    """Returns a list of description strings, one per song in batch."""
    song_list = '\n'.join(make_song_entry(i, s) for i, s in enumerate(batch))

    # Count how many in batch have Spotify data
    has_spotify = sum(1 for s in batch if s.get("spotify_features"))

    if has_spotify > 0:
        spotify_note = (
            f"\n{has_spotify} of these songs include MEASURED audio data from Spotify "
            "(tempo, energy, danceability, valence, acousticness). "
            "For those songs, your description MUST match the measured values exactly — "
            "if the data says 'fast-paced and high-energy', write it that way even if the title sounds sad. "
            "Only describe instrumentation, texture, mood language, and listening context — "
            "the tempo/energy/danceability values are facts, not suggestions."
        )
    else:
        spotify_note = ""

    prompt = f"""For each song below, write 2-3 sentences describing it for a music search system.{spotify_note}

Each description MUST include:
1. TEMPO — slow / mid-tempo / uptempo / fast-paced (use measured BPM if provided)
2. ENERGY — quiet and intimate / gentle / moderate / high-energy / intense (use measured energy if provided)
3. INSTRUMENTATION — name specific instruments or sonic texture (e.g. "sparse piano and cello", "swinging brass and upright bass", "driving congas and electric guitar")
4. MOOD / EMOTION — the feeling it creates (melancholy, joyful, tense, romantic, nostalgic, euphoric, playful...)
5. BEST MOMENT — what context suits it (late-night drive, rainy afternoon, dinner party, morning run, dancing, focused work...)
6. VOCALIST — if the artist is a band or group, mention the lead vocalist by name

Return JSON: {{"descriptions": ["...", "...", ...]}}
Exactly {len(batch)} strings in the same order as the songs.

Songs:
{song_list}"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {
                'role': 'system',
                'content': (
                    'You are a music expert writing precise descriptions for a semantic search system. '
                    'When measured audio data is provided, it is ground truth — never contradict it. '
                    'Always return valid JSON.'
                )
            },
            {'role': 'user', 'content': prompt}
        ],
        response_format={'type': 'json_object'},
        temperature=0.5   # lower temperature for more faithful adherence to measured data
    )

    result = json.loads(response.choices[0].message.content)
    descriptions = result.get('descriptions') or next(iter(result.values()))
    return descriptions


# ── Main loop ─────────────────────────────────────────────────────────────────
enriched_map = {}

for i in range(0, len(to_enrich), BATCH_SIZE):
    batch     = to_enrich[i:i + BATCH_SIZE]
    batch_num = i // BATCH_SIZE + 1

    print(f'Batch {batch_num}/{total_batches} ...', end=' ', flush=True)

    try:
        descriptions = enrich_batch(batch)

        for j, song in enumerate(batch):
            key = song.get('videoId') or f'__noid__{song["title"]}__{song["artist"]}'
            enriched_map[key] = {**song, 'description': descriptions[j] if j < len(descriptions) else ''}

        print('✓')

        # Save after every batch — safe to interrupt
        with open(ENRICHED_PATH, 'w', encoding='utf-8') as f:
            json.dump(list(enriched_map.values()), f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f'FAILED: {e}')
        time.sleep(2)

    if i + BATCH_SIZE < len(to_enrich):
        time.sleep(0.3)

print(f'\n✅ Done! {len(enriched_map)} songs enriched → enriched_songs.json')

# ── Quick preview ─────────────────────────────────────────────────────────────
print('\nSample descriptions:')
samples = [s for s in enriched_map.values() if s.get('description')][:3]
for s in samples:
    has_sp = '📊' if s.get('spotify_features') else '🤖'
    print(f'\n  {has_sp} {s["title"]} — {s["artist"]}')
    print(f'     {s["description"]}')
