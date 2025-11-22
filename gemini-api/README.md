# SubliminalGen Music API

**Complete music generation and VIP user management API**

## Files:
- `music_server.py` - Main API server with all features
- `services/music_service.py` - Music service with Supabase integration
- `services/lyria_music.py` - Lyria AI music generator
- `models/requests.py` - Request models
- `models/responses.py` - Response models
- `database_setup.sql` - Database schema setup
- `.env` - Environment configuration
- `requirements.txt` - Dependencies

## Setup:
1. **Install dependencies:** `pip install -r requirements.txt`
2. **Configure environment:** Update `.env` with your credentials
3. **Setup database:** Run `database_setup.sql` in Supabase
4. **Run server:** `python music_server.py`
5. **API available at:** `http://localhost:8001`

## API Endpoints

**Base URL:** `http://0.0.0.0:8001`

### Core Music Features

#### GET /
Health check
```bash
curl http://localhost:8001/
```

#### GET /api/music/{user_id}
Get personalized music for user (with Supabase caching)
```bash
curl "http://localhost:8001/api/music/user123?tag=meditation"
```
**Supported tags:** `meditation`, `focus`, `sleep`, `energy`

#### POST /api/music/generate
Direct music generation using Lyria AI
```bash
curl -X POST "http://localhost:8001/api/music/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "peaceful meditation music", "duration": 30}'
```

### VIP User Features

#### POST /api/audio/combine
Combine voice recording with AI music
```bash
curl -X POST "http://localhost:8001/api/audio/combine" \
  -F "voice_file=@voice.wav" \
  -F "music_id=1234567890-abc123" \
  -F "user_id=user123" \
  -F "is_vip=true" \
  -F "title=My Meditation"
```

**Response:**
- **VIP users:** Permanent storage + creation ID
- **Free users:** 24-hour temporary file

#### GET /api/library
Get user's saved creations (VIP only)
```bash
curl "http://localhost:8001/api/library?user_id=user123"
```

#### DELETE /api/creation/{creation_id}
Delete a saved creation (VIP only)
```bash
curl -X DELETE "http://localhost:8001/api/creation/uuid-here?user_id=user123"
```

### File Management

#### GET /api/download/{file_id}
Download/stream any file
```bash
curl "http://localhost:8001/api/download/audio123.wav" -o music.wav
```

#### GET /files/{filename}
Serve static files from uploads directory
```bash
curl "http://localhost:8001/files/audio123.wav" -o music.wav
```

## Database Schema

### Supabase Tables:
- **`music`** - Generated music tracks with metadata
- **`music_users`** - User music delivery tracking
- **`user_creations`** - VIP user saved creations

### Storage Buckets:
- **`music`** - Generated music files
- **Local uploads/** - Combined audio files

## Environment Variables
```env
# Gemini/Lyria AI
GEMINI_API_KEY=your_gemini_api_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_service_key

# Optional
ENVIRONMENT=development
DEBUG=true
```

## Features

✅ **AI Music Generation** - Lyria/Gemini integration  
✅ **Smart Caching** - Supabase-based user tracking  
✅ **Voice Combining** - Upload + mix with AI music  
✅ **VIP Library** - Permanent storage for premium users  
✅ **File Management** - Download, stream, delete  
✅ **Tag-based Music** - Meditation, focus, sleep, energy  

## Deployment

**Render.com:**
- Root Directory: `gemini-api`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn music_server:app --host 0.0.0.0 --port $PORT`

**Local Development:**
```bash
cd gemini-api
python music_server.py
```

API will be available at `http://localhost:8001` 🎵