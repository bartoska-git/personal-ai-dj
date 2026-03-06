import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

# Load secrets — works both locally (.env) and on Streamlit Cloud (st.secrets)
load_dotenv()

def _secret(key: str) -> str:
    """Read from st.secrets if available (Streamlit Cloud), else from env."""
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.getenv(key)

openai_client = OpenAI(api_key=_secret('OPENAI_API_KEY'))
supabase      = create_client(_secret('SUPABASE_URL'), _secret('SUPABASE_KEY'))

# ── Step 1: Embed the user's query ────────────────────────────────────────────
def search_songs(query: str, match_count: int = 20) -> list:
    """Convert the query to a vector and find the most similar songs."""
    resp = openai_client.embeddings.create(
        model='text-embedding-3-small',
        input=query
    )
    query_vector = resp.data[0].embedding

    result = supabase.rpc('match_songs', {
        'query_embedding': query_vector,
        'match_count':     match_count
    }).execute()

    return result.data


# ── Step 2: Curate a playlist from the candidates ────────────────────────────
SYSTEM_PROMPT = """You are a personal music curator with deep knowledge of Anna's taste.

Anna's library spans jazz, indie folk, world music, film scores, 80s pop, hip-hop, classical, and more.
When she's sad or melancholy, she reaches for slow jazz, Nicholas Britell film scores, quiet acoustic music, and introspective indie — NOT songs with "sad", "sorrow", or "cry" in their titles.
She values emotional depth and musicality over obvious literal matches.

You have retrieved 20 candidate songs based on semantic similarity of their musical descriptions.
Each song may include a play_count (how many times Anna has played it) and last_played (when she last played it).

CRITICAL RULES:
- NEVER select a song just because its title contains a word from the request (e.g. "Bad Day" for a sad mood, "Song of Sorrow" for sadness). That is lazy and wrong.
- Judge each song purely on how it actually SOUNDS and FEELS — tempo, instrumentation, emotional texture, atmosphere
- Be selective and ruthless — 6 perfect songs beats 12 mediocre ones
- A sad mood should surface: slow jazz, melancholy instrumentals, quiet introspective vocals, minor key pieces — not songs titled "sad" or "sorrow"
- Reasons must reference the song's actual musical qualities (tempo, instrumentation, vocal tone, atmosphere) — never generic phrases like "this song captures the mood"

USING PLAY HISTORY:
- play_count signals how much Anna loves a song — all else equal, favour songs she plays often
- If the request implies discovery ("something new", "haven't heard in a while"), favour low/no play_count or old last_played dates
- If the request implies comfort ("something familiar", "my favourites"), strongly favour high play_count songs
- Never mention play counts in your reasons — it should feel like natural curation, not data reporting

Your job:
1. Select the 6–12 songs that BEST match based on how they actually sound — ignore title keywords
2. Order them thoughtfully — consider energy arc and flow
3. Write a specific one-sentence reason per song referencing its actual musical qualities
4. Give the playlist a short evocative title (not "Your Playlist" or "Sad Songs")
5. Write a warm 1–2 sentence intro speaking directly to Anna

Return JSON in this exact shape:
{
  "title": "playlist title",
  "intro": "warm 1-2 sentence intro",
  "songs": [
    {
      "title": "song title",
      "artist": "artist name",
      "video_id": "the video_id value or null",
      "reason": "one sentence reason referencing actual musical qualities"
    }
  ]
}"""

def generate_playlist(query: str, candidates: list) -> dict:
    """Ask GPT-4o-mini to curate the best playlist from the candidates."""

    candidates_text = '\n'.join(
        f'{i+1}. "{s["title"]}" by {s["artist"]}'
        + (f' — album: {s["album"]}' if s.get('album') else '')
        + f'\n   Vibe: {s["description"]}'
        + f'\n   video_id: {s.get("video_id") or "null"}'
        + (f'\n   play_count: {s["play_count"]}' if s.get('play_count') else '')
        + (f'\n   last_played: {s["last_played"]}' if s.get('last_played') else '')
        for i, s in enumerate(candidates)
    )

    user_prompt = f"""Anna's request: "{query}"

Candidate songs from her library (ranked by how closely they matched):
{candidates_text}

Please curate the best playlist from these candidates."""

    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': user_prompt}
        ],
        response_format={'type': 'json_object'},
        temperature=0.7
    )

    return json.loads(response.choices[0].message.content)


# ── Full pipeline ─────────────────────────────────────────────────────────────
def get_playlist(query: str) -> dict:
    """query → embed → search → generate → return playlist dict."""
    print(f'\nSearching your library for: "{query}"...')
    candidates = search_songs(query, match_count=20)
    print(f'Found {len(candidates)} candidates — curating your playlist...\n')
    return generate_playlist(query, candidates)


# ── Run directly for testing ──────────────────────────────────────────────────
if __name__ == '__main__':
    query = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else input('What do you want to listen to? ')

    playlist = get_playlist(query)

    print(f'🎵  {playlist["title"]}')
    print(f'    {playlist["intro"]}')
    print()

    for i, song in enumerate(playlist['songs'], 1):
        vid = song.get('video_id')
        if vid:
            link = f'https://music.youtube.com/watch?v={vid}'
        else:
            q = f'{song["title"]} {song["artist"]}'.replace(' ', '+')
            link = f'https://music.youtube.com/search?q={q}'

        print(f'{i:2}. {song["title"]} — {song["artist"]}')
        print(f'    {song["reason"]}')
        print(f'    🔗 {link}')
        print()
