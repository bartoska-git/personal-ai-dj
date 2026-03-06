import json
import time
from ytmusicapi import YTMusic

yt = YTMusic('/Users/bartoska/web/yt-music-prototype/browser.json')

# Playlists to skip (user's choice)
SKIP_PLAYLISTS = {
    'New Episodes',
    'filmmaking',
    'Skvela hudba',
    'Yellowstone Soundtrack: The Best Songs Playlist',
    'Video Case Studies',
    'COVID-19',
    'soundtracks',
    'Israeli vibe',
    'Episodes for Later'
}

songs = {}  # videoId -> song dict, for deduplication

# Load existing songs.json so we don't lose data from previous runs
output_path = '/Users/bartoska/web/yt-music-prototype/songs.json'
try:
    with open(output_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)
    for s in existing:
        vid = s.get('videoId')
        key = vid if vid else f'__noid__{s["title"]}__{s["artist"]}'
        songs[key] = s
    print(f'Loaded {len(songs)} songs from previous run — will merge new ones in.\n')
except FileNotFoundError:
    print('No existing songs.json — starting fresh.\n')

def add_song(track, source):
    artists = track.get('artists', [])
    artist_name = artists[0].get('name', 'Unknown') if artists else 'Unknown'
    title = track.get('title', 'Unknown')
    vid = track.get('videoId')

    # Some playlists return tracks with null videoId (ATV audio-only type).
    # Fall back to a title+artist composite key so we don't lose them.
    key = vid if vid else f'__noid__{title}__{artist_name}'

    if not title or title == 'Unknown':
        return  # skip truly empty rows

    album = track.get('album') or {}
    album_name = album.get('name', '') if isinstance(album, dict) else ''

    if key not in songs:
        songs[key] = {
            'videoId': vid,   # may be None for ATV tracks
            'title': title,
            'artist': artist_name,
            'album': album_name,
            'sources': [source]
        }
    else:
        if source not in songs[key]['sources']:
            songs[key]['sources'].append(source)

# 1. Listening history
print('Fetching listening history...')
try:
    history = yt.get_history()
    for track in history:
        add_song(track, 'history')
    print(f'  → {len(history)} songs')
except Exception as e:
    print(f'  FAILED: {e}')

# 2. Individually saved library songs
print('Fetching library songs...')
try:
    library = yt.get_library_songs(limit=500)
    for track in library:
        add_song(track, 'library')
    print(f'  → {len(library)} songs')
except Exception as e:
    print(f'  FAILED: {e}')

# 3. All kept playlists
print('Fetching playlists...')
playlists = yt.get_library_playlists(limit=50)

for p in playlists:
    title = p.get('title', '')

    if title in SKIP_PLAYLISTS:
        print(f'  SKIP: {title}')
        continue

    playlist_id = p.get('playlistId')
    if not playlist_id:
        continue

    try:
        print(f'  Fetching: {title}...', end=' ', flush=True)
        details = yt.get_playlist(playlist_id, limit=2000)
        tracks = details.get('tracks', [])
        for track in tracks:
            add_song(track, title)
        print(f'→ {len(tracks)} songs')
        time.sleep(0.5)  # be polite to the API
    except Exception as e:
        print(f'FAILED: {e}')

# Save to JSON
song_list = list(songs.values())
output_path = '/Users/bartoska/web/yt-music-prototype/songs.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(song_list, f, indent=2, ensure_ascii=False)

print(f'\n✅ Done! {len(song_list)} unique songs saved to songs.json')
