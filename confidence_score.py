"""
confidence_score.py — Ask GPT to rate its own knowledge of each song.

Adds to every song:
  gpt_confidence : 1 | 2 | 3
    3 = knows this song/artist well, description is grounded in real knowledge
    2 = some knowledge, description is partially inferred
    1 = doesn't recognise this, description is a guess

Songs with confidence == 1 AND no lastfm_tags are flagged for web search
re-enrichment in the next step (web_enrich.py).

Processes in batches of 50 for efficiency. Safe to interrupt and resume.
"""

import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

INPUT_FILE = 'enriched_songs.json'
BATCH_SIZE = 50

with open(INPUT_FILE) as f:
    songs = json.load(f)

already_done = sum(1 for s in songs if 'gpt_confidence' in s)
to_score     = [s for s in songs if 'gpt_confidence' not in s]

print(f'Loaded {len(songs)} songs')
print(f'  {already_done} already scored — resuming')
print(f'  {len(to_score)} to score\n')

total_batches = (len(to_score) + BATCH_SIZE - 1) // BATCH_SIZE


def score_batch(batch: list) -> list[int]:
    """Returns a list of confidence scores (1/2/3), one per song."""
    song_list = '\n'.join(
        f'{i+1}. "{s["title"]}" by {s["artist"]}'
        for i, s in enumerate(batch)
    )

    prompt = f"""For each song below, rate your knowledge of it from 1 to 3.

1 = I don't recognise this song or artist — my knowledge is a guess
2 = I have some knowledge of this artist but am not certain about this specific song
3 = I know this song and artist well — I can describe it accurately

Be honest. It is better to give a low score than to overstate your knowledge.
Niche, regional, or non-Western music you haven't encountered should be rated 1.

Return JSON: {{"scores": [1, 3, 2, ...]}}
Exactly {len(batch)} integers in the same order as the songs.

Songs:
{song_list}"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': 'You are honest about the limits of your knowledge. Always return valid JSON.'},
            {'role': 'user',   'content': prompt}
        ],
        response_format={'type': 'json_object'},
        temperature=0,
    )

    result = json.loads(response.choices[0].message.content)
    scores = result.get('scores') or next(iter(result.values()))
    return [max(1, min(3, int(s))) for s in scores]   # clamp to 1-3


# Index songs by videoId for fast lookup
song_index = {
    s.get('videoId') or f'__noid__{s["title"]}__{s["artist"]}': s
    for s in songs
}

for i in range(0, len(to_score), BATCH_SIZE):
    batch     = to_score[i:i + BATCH_SIZE]
    batch_num = i // BATCH_SIZE + 1

    print(f'Batch {batch_num}/{total_batches} ...', end=' ', flush=True)

    try:
        scores = score_batch(batch)

        for j, song in enumerate(batch):
            song['gpt_confidence'] = scores[j] if j < len(scores) else 1

        print(f'✓  (scores: {scores[:10]}{"..." if len(scores) > 10 else ""})')

        # Save after every batch
        with open(INPUT_FILE, 'w') as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f'FAILED: {e}')

    time.sleep(0.3)

# Final save
with open(INPUT_FILE, 'w') as f:
    json.dump(songs, f, ensure_ascii=False, indent=2)

# Summary
low  = sum(1 for s in songs if s.get('gpt_confidence') == 1)
mid  = sum(1 for s in songs if s.get('gpt_confidence') == 2)
high = sum(1 for s in songs if s.get('gpt_confidence') == 3)
flagged = sum(1 for s in songs if s.get('gpt_confidence') == 1 and not s.get('lastfm_tags'))

print(f'\n✅ Done!')
print(f'  Confidence 3 (knows well): {high}')
print(f'  Confidence 2 (partial):    {mid}')
print(f'  Confidence 1 (guessing):   {low}')
print(f'\n  → {flagged} songs flagged for web search re-enrichment')
print(f'     (confidence == 1 AND no Last.fm tags)')
print('\nNext step: run  python3 web_enrich.py')
