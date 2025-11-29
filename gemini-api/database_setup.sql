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
    cache_key TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Music users tracking table (extended for authentication)
CREATE TABLE IF NOT EXISTS music_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    password_hash TEXT,
    name TEXT,
    is_vip BOOLEAN DEFAULT FALSE,
    google_id TEXT,
    last_received_uuid TEXT,
    last_received_timestamp TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for music tables
CREATE INDEX IF NOT EXISTS idx_music_tag_uuid ON music (tag, uuid);
CREATE INDEX IF NOT EXISTS idx_music_cache_key ON music (cache_key);
CREATE INDEX IF NOT EXISTS idx_music_users_user_id ON music_users (user_id);
CREATE INDEX IF NOT EXISTS idx_music_users_email ON music_users (email);

-- Fix music_users table to ensure user_id has UUID default
ALTER TABLE music_users ALTER COLUMN user_id SET DEFAULT gen_random_uuid();

-- If user_id is currently TEXT, convert to UUID
-- (Run this only if needed - check your current schema first)
-- ALTER TABLE music_users ALTER COLUMN user_id TYPE UUID USING user_id::UUID;

-- Add VIP tracking columns to music_users table
ALTER TABLE music_users
ADD COLUMN IF NOT EXISTS vip_start_date TIMESTAMP,
ADD COLUMN IF NOT EXISTS vip_end_date TIMESTAMP,
ADD COLUMN IF NOT EXISTS transaction_id TEXT;

-- Add VIP level column to music_users table
ALTER TABLE music_users
ADD COLUMN IF NOT EXISTS vip_level TEXT DEFAULT 'free';

-- Add constraint for valid values
ALTER TABLE music_users
ADD CONSTRAINT vip_level_check
CHECK (vip_level IN ('free', 'gold', 'platinum'));

-- Platinum Downloads Table for Extended Mixes
CREATE TABLE IF NOT EXISTS platinum_downloads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    title TEXT NOT NULL,
    duration INTEGER NOT NULL,
    file_size BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    downloaded BOOLEAN DEFAULT FALSE
);

-- Indexes for platinum downloads
CREATE INDEX IF NOT EXISTS idx_platinum_downloads_expires_at ON platinum_downloads (expires_at);
CREATE INDEX IF NOT EXISTS idx_platinum_downloads_token ON platinum_downloads (token);
CREATE INDEX IF NOT EXISTS idx_platinum_downloads_user_id ON platinum_downloads (user_id);