-- Initial database schema for story processing system
-- Migrated from SQLite to PostgreSQL for Supabase

-- Stories table
CREATE TABLE IF NOT EXISTS stories (
    id SERIAL PRIMARY KEY,
    email_id TEXT UNIQUE NOT NULL,
    title TEXT,
    author TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    word_count INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    processed_at TIMESTAMPTZ,
    source TEXT DEFAULT 'email',
    extraction_method TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Story chunks table
CREATE TABLE IF NOT EXISTS story_chunks (
    id SERIAL PRIMARY KEY,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    chunk_number INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    word_count INTEGER,
    chunk_text TEXT NOT NULL DEFAULT '',
    storage_path TEXT,
    sent_to_kindle_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(story_id, chunk_number)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status);
CREATE INDEX IF NOT EXISTS idx_stories_email_id ON stories(email_id);
CREATE INDEX IF NOT EXISTS idx_stories_received_at ON stories(received_at);
CREATE INDEX IF NOT EXISTS idx_story_chunks_story_id ON story_chunks(story_id);
CREATE INDEX IF NOT EXISTS idx_story_chunks_sent_at ON story_chunks(sent_to_kindle_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
CREATE TRIGGER update_stories_updated_at BEFORE UPDATE ON stories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

