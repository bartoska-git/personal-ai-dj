"""
web_enrich.py — Re-enrich low-confidence songs using Tavily web search + GPT.

TWO passes depending on target:

  Pass 1 (original, complete):
    gpt_confidence == 1 AND lastfm_tags == []
    → 271 songs, all done via OpenAI web_search_preview

  Pass 2 (current, Tavily):
    gpt_confidence == 1 AND lastfm_tags not empty AND play_count > 0
    → ~228 songs in your actual listening history
    → Tavily fetches real page content, GPT-4o-mini synthesises description

Architecture:
  Tavily Search  →  extracted page content (rich, LLM-ready)
  GPT-4o-mini    →  synthesises description from that content
  (two cheap calls instead of one expensive bundled OpenAI web search call)

Saves progress after every song — safe to interrupt and resume.
"""

import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

load_dotenv()

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

INPUT_FILE = 'enriched_songs.json'

with open(INPUT_FILE) as f:
    songs = json.load(f)

# Pass 2: low confidence + has tags + in listening history
flagged = [
    s for s in songs
    if s.get('gpt_confidence') == 1
    and s.get('lastfm_tags')          # has community tags
    and s.get('play_count')           # in your actual listening history
    and not s.get('web_enriched')     # not already done
]

print(f'Songs flagged for Tavily enrichment: {len(flagged)}')
print(f'  (low confidence + has tags + in your listening history)\n')


def web_enrich_song(song: dict) -> str:
    """
    Step 1: Tavily searches the web and returns extracted page content.
    Step 2: GPT-4o-mini reads that content and writes a grounded description.
    """

    query = f'"{song["title"]}" {song["artist"]} song music'

    # Step 1 — Tavily: real page content, not just snippets
    try:
        results = tavily_client.search(
            query=query,
            max_results=3,
            search_depth='advanced',   # extracts full page content, not just snippets
        )
    except Exception as e:
        raise RuntimeError(f'Tavily search failed: {e}')

    # Build context from extracted content
    context_parts = []
    for r in results.get('results', []):
        title   = r.get('title', '')
        content = r.get('content', '')
        if content:
            context_parts.append(f'Source: {title}\n{content}')

    if not context_parts:
        raise RuntimeError('Tavily returned no usable content')

    context = '\n\n---\n\n'.join(context_parts)

    # Step 2 — GPT: synthesise a description from the real content
    tags_str = ', '.join(song.get('lastfm_tags', []))

    prompt = f"""You are writing a description for a music search system.

Song: "{song['title']}" by {song['artist']}
{f'Album: {song["album"]}' if song.get('album') else ''}
Last.fm community tags: {tags_str}

Here is information found on the web about this song and artist:

{context}

Using the web information above (and the tags as additional context), write a
2-3 sentence description that includes:
1. TEMPO — slow / mid-tempo / uptempo / fast-paced
2. ENERGY — quiet and intimate / gentle / moderate / high-energy / intense
3. INSTRUMENTATION — specific instruments or sonic texture
4. MOOD / EMOTION — the feeling it creates
5. BEST MOMENT — what context suits it (late-night, morning run, etc.)
6. GENRE and cultural/regional context if relevant

Base your description strictly on what the web content says.
If this is a regional or non-Western artist, mention their origin and tradition.
Return only the description text, no extra commentary."""

    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.7,
        max_tokens=200,
    )

    return response.choices[0].message.content.strip()


updated = 0

for i, song in enumerate(flagged):
    label = f'[{i+1}/{len(flagged)}] {song["title"]} — {song["artist"]}'
    print(f'{label} ({song["play_count"]}x) ...', end=' ', flush=True)

    try:
        new_description = web_enrich_song(song)

        if new_description:
            song['description']    = new_description
            song['web_enriched']   = True
            song['gpt_confidence'] = 2   # now grounded in real content
            updated += 1
            print('✓')
        else:
            print('no result')

        # Save after every song — safe to interrupt
        with open(INPUT_FILE, 'w') as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f'FAILED: {e}')

    time.sleep(1)   # Tavily + OpenAI: 1s is enough, no daily quota

print(f'\n✅ Done! {updated}/{len(flagged)} songs re-enriched via Tavily + GPT.')
print('\nNext step: run embed.py')
