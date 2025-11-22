-- User Creations Table for VIP Features
CREATE TABLE IF NOT EXISTS user_creations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    voice_url TEXT,
    combined_url TEXT NOT NULL,
    music_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Index for faster user queries
CREATE INDEX IF NOT EXISTS idx_user_creations_user_id ON user_creations (user_id, created_at DESC);

-- Music table (if not exists)
CREATE TABLE IF NOT EXISTS music (
    uuid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    tag TEXT NOT NULL DEFAULT 'meditation',
    supabase_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Music users tracking table (if not exists)
CREATE TABLE IF NOT EXISTS music_users (
    user_id TEXT PRIMARY KEY,
    last_received_uuid TEXT,
    last_received_timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes for music tables
CREATE INDEX IF NOT EXISTS idx_music_tag_uuid ON music (tag, uuid);
CREATE INDEX IF NOT EXISTS idx_music_users_user_id ON music_users (user_id);