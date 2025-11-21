-- Create music table to store generated tracks
CREATE TABLE music (
  uuid TEXT PRIMARY KEY,
  title TEXT,
  tag TEXT,
  supabase_url TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Create music_users table to track what each user has received
CREATE TABLE music_users (
  user_id TEXT PRIMARY KEY,
  last_received_uuid TEXT,
  last_received_timestamp TIMESTAMP
);

-- Create storage bucket for music files (skip if already exists)
INSERT INTO storage.buckets (id, name, public) 
VALUES ('music', 'music', true)
ON CONFLICT (id) DO NOTHING;

-- Disable RLS for music tables (allow service key access)
ALTER TABLE music DISABLE ROW LEVEL SECURITY;
ALTER TABLE music_users DISABLE ROW LEVEL SECURITY;