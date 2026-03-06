-- yt-music-prototype: migration to add play history + tags columns
-- Run this in the Supabase SQL editor before running embed.py
-- Safe to run multiple times (IF NOT EXISTS / OR REPLACE)

-- 1. Add new columns to songs table
ALTER TABLE songs ADD COLUMN IF NOT EXISTS play_count  INT;
ALTER TABLE songs ADD COLUMN IF NOT EXISTS last_played TIMESTAMPTZ;
ALTER TABLE songs ADD COLUMN IF NOT EXISTS lastfm_tags JSONB;

-- 2. Update match_songs function to return new columns
CREATE OR REPLACE FUNCTION match_songs(
    query_embedding VECTOR(1536),
    match_count     INT DEFAULT 20
)
RETURNS TABLE (
    id          BIGINT,
    video_id    TEXT,
    title       TEXT,
    artist      TEXT,
    album       TEXT,
    description TEXT,
    sources     JSONB,
    play_count  INT,
    last_played TIMESTAMPTZ,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.video_id,
        s.title,
        s.artist,
        s.album,
        s.description,
        s.sources,
        s.play_count,
        s.last_played,
        1 - (s.embedding <=> query_embedding) AS similarity
    FROM songs s
    ORDER BY s.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
