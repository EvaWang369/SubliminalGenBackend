# SubliminalGen Music API

**Complete music generation and VIP user management API**

## Files:
- `main.py` - Main API server with all features
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
4. **Run server:** `python main.py`
5. **API available at:** `http://localhost:8001`

## API Endpoints

**Base URL:** `http://0.0.0.0:8001`

### Core Music Features

#### GET /
Health check
```bash
curl http://localhost:8001/
```

#### POST /api/music/{user_id} (Unified Endpoint)
Handles both simple and enhanced music generation

**Enhanced Mode (with iOS parameters):**
```bash
curl -X POST "http://localhost:8001/api/music/user123" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A calm, meditative forest melody",
    "tag": "meditation",
    "music_type": ["Ambient"],
    "instruments": ["Piano", "Nature Sounds"],
    "mood": ["Peaceful"],
    "frequencies": ["432 Hz"]
  }'
```

**Simple Mode (tag-based):**
```bash
curl -X POST "http://localhost:8001/api/music/user123" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "calm meditation music",
    "tag": "meditation"
  }'
```

#### POST /api/music/generate (Local Storage)
Direct generation with local file storage
```bash
curl -X POST "http://localhost:8001/api/music/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "peaceful meditation music", "tag": "meditation"}'
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

✅ **Advanced AI Music Generation** - Lyria/Gemini with rich parameters  
✅ **Hybrid Caching System** - Hash-based + Tag-based sequential caching  
✅ **Smart Lyria Configuration** - Tag-optimized BPM, density, brightness  
✅ **Unified API Endpoint** - Single POST endpoint handles simple + enhanced requests  
✅ **Voice Combining** - Upload + mix with AI music  
✅ **VIP Library** - Permanent storage for premium users  
✅ **File Management** - Download, stream, delete  
✅ **Cost Optimization** - Intelligent caching reduces API calls by 80%+

## Caching System

### **Hybrid Caching Architecture**

**Enhanced Mode (Hash-based + Sequential):**
1. **Hash Lookup**: Check if enhanced prompt exists in cache
2. **User History**: Verify user hasn't received this track
3. **Smart Selection**: Return cached track or find next in sequence
4. **Fallback**: Generate new track if needed

**Simple Mode (Tag-based Sequential):**
1. **User Tracking**: Track last received track per tag
2. **Sequential Delivery**: Get next track in tag sequence
3. **Auto-generation**: Create new track when sequence ends

### **Smart Lyria Configuration**

**Tag-Based Optimization:**
```python
# Meditation: 70 BPM, low density, warm tones
# Focus: 90 BPM, medium density, balanced brightness  
# Sleep: 60 BPM, minimal density, soft tones
# Energy: 120 BPM, high density, bright tones
```

## iOS Client Integration

**Production Endpoint:**
```
POST https://subliminalgenbackend.onrender.com/api/music/{user_id}
```

**iOS Request Examples:**
```swift
// Enhanced Mode
let enhancedRequest = [
    "prompt": "Calm meditation music",
    "tag": "meditation",
    "instruments": ["Piano", "Nature Sounds"],
    "mood": ["Peaceful"]
]

// Simple Mode  
let simpleRequest = [
    "prompt": "focus music",
    "tag": "focus"
]
```

**Response Format:**
```json
{
  "uuid": "1763844598-lsw9ja",
  "title": "Enhanced Meditation Track",
  "url": "https://supabase-storage-url.wav",
  "cached": true,
  "generation_time": "0.3s"
}
```  

## Deployment

**Render.com:**
- Root Directory: `gemini-api`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`
- Environment Variables: `BASE_URL=https://subliminalgenbackend.onrender.com`

**Local Development:**
```bash
cd gemini-api
python main.py
```

API will be available at `http://localhost:8001` 🎵

sample curl request:
```
curl -X POST http://localhost:8001/api/music/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "relaxing piano music",
    "tag": "meditation",
    "duration": 60,
    "is_vip": true,
    "music_type": ["ambient"],
    "instruments": ["piano"],
    "mood": ["calm"]
  }'

```
https://ai.google.dev/gemini-api/docs/music-generation?utm_source=deepmind.google&utm_medium=referral&utm_campaign=gdm&utm_content

VIP User Test (60s duration):
```
curl -X POST https://subliminalgenbackend.onrender.com/api/music/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "relaxing piano music",
    "tag": "meditation",
    "duration": 60,
    "is_vip": true,
    "music_type": ["ambient"],
    "instruments": ["piano"],
    "mood": ["calm"]
  }'
```

Free User Test (30s duration cap):
```
curl -X POST https://subliminalgenbackend.onrender.com/api/music/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "energetic workout music",
    "tag": "energy",
    "duration": 90,
    "is_vip": false
  }'
```

Health Check:
```
curl https://subliminalgenbackend.onrender.com/

```

If VIP & duration > 3 minutes → call backend combine API

This becomes an extra VIP feature, not blocking playback.

Flow:
Frontend → combine locally (1–3 min)
            ↓
If VIP & selectedDuration > 3 min:
    Call backend “long_combine” API
            ↓
Backend turns raw files into long version
            ↓
Uploads long version to Supabase
            ↓
Sends back cloud URL
            ↓
Frontend updates track metadata