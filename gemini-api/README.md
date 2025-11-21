# SubliminalGen API

## Files:
- `music_server.py` - Music API server (Port 8001)
- `services/music_service.py` - Music service with Supabase integration
- `services/lyria_music.py` - Lyria AI music generator
- `models/requests.py` - Request models
- `models/responses.py` - Response models
- `.env` - Environment configuration
- `requirements.txt` - Dependencies

## Setup:
1. Install dependencies: `pip install -r requirements.txt`
2. Update `.env` with Supabase and Lyria credentials
3. Run music server: `python music_server.py`
4. Run main server: `python ../main.py`

## API Endpoints

### Main API (Port 8000)
**Base URL:** `http://0.0.0.0:8000`

#### GET /
Health check
```bash
curl http://localhost:8000/
```

#### POST /api/music/generate
Generate AI music with semantic caching
```bash
curl -X POST "http://localhost:8000/api/music/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "relaxing ambient music", "duration": 30, "style": "ambient", "mood": "calm"}'
```

#### POST /api/video/generate
Generate AI video with semantic caching
```bash
curl -X POST "http://localhost:8000/api/video/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "abstract visuals", "duration": 30, "style": "abstract", "resolution": "1080p"}'
```

#### POST /api/audio/combine
Combine voice recording with AI music
```bash
curl -X POST "http://localhost:8000/api/audio/combine" \
  -F "voice_file=@voice.wav" \
  -F "music_id=123" \
  -F "user_id=user123" \
  -F "is_vip=true"
```

#### GET /api/library
Get user's creation library (VIP only)
```bash
curl "http://localhost:8000/api/library?user_id=user123"
```

#### GET /api/download/{file_id}
Download/stream files
```bash
curl "http://localhost:8000/api/download/file123" -o downloaded_file
```

### Music API (Port 8001)
**Base URL:** `http://0.0.0.0:8001`

#### GET /
Health check
```bash
curl http://localhost:8001/
```

#### GET /api/music/{user_id}
Get cached music for user (from Supabase)
```bash
curl "http://localhost:8001/api/music/user123?tag=meditation"
```
Supported tags: `meditation`, `focus`, `sleep`, `energy`

#### POST /api/music/generate
Direct music generation
```bash
curl -X POST "http://localhost:8001/api/music/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "peaceful meditation music", "duration": 30}'
```

#### GET /files/{filename}
Serve static audio files
```bash
curl "http://localhost:8001/files/audio123.wav" -o music.wav
```

## Data Sources

### Supabase Integration
The Music API uses Supabase for:
- **`music` table** - Track metadata (uuid, title, tag, supabase_url)
- **`music_users` table** - User tracking (user_id, last_received_uuid, timestamp)
- **`music` storage bucket** - Audio file storage

### Environment Variables
```env
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
```

### Sample Videos Resources:
1. Generate videos with sounds: https://firefly.adobe.com/generate/sound-effects 