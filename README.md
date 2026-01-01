# SubliminalGen - Design Document

## 🎯 Project Overview
SubliminalGen is a full-stack iOS + FastAPI application that enables users to create personalized subliminal audio and video content by combining their voice recordings with AI-generated background music and videos.

## 🏗️ Architecture

### System Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   iOS App       │    │   FastAPI       │    │   Storage       │
│   (SwiftUI)     │◄──►│   Backend       │◄──►│   S3 + Supabase │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Local Cache     │    │ AI Services     │    │ Semantic Cache  │
│ (Free Tier)     │    │ gemini music API│    │ (Embeddings)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow
1. **Voice Recording**: Local capture using AVAudioRecorder
2. **AI Generation**: Semantic cache check → API call if needed → S3 storage
3. **Combination**: Mix voice + AI assets (local for Free, cloud for VIP)
4. **Storage**: Two-tier policy based on subscription

## 🗄️ Database Schema (Supabase)

### Table: generated_assets
```sql
CREATE TABLE generated_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type asset_type NOT NULL,
    prompt TEXT NOT NULL,
    normalized_prompt TEXT NOT NULL,
    duration INTEGER NOT NULL,
    embedding VECTOR(384),
    file_url TEXT NOT NULL,
    hash_signature TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    tags JSONB DEFAULT '{}'
);

CREATE TYPE asset_type AS ENUM ('music', 'video');
CREATE INDEX idx_embedding ON generated_assets USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_hash ON generated_assets (hash_signature);
CREATE INDEX idx_type_duration ON generated_assets (type, duration);
```

### Table: user_creations (VIP only)
```sql
CREATE TABLE user_creations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    voice_url TEXT,
    combined_url TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_user_creations ON user_creations (user_id, created_at DESC);
```

### Table: psyche_tracks (VIP only)
```sql
CREATE TABLE psyche_tracks (
    id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    duration INTEGER NOT NULL,
    tags JSON NOT NULL,
    file_path VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_psyche_tracks_tags ON psyche_tracks USING GIN (tags);
```

## ☁️ Storage Structure

### S3 (User Content)
```
s3://subliminal-gen/
├── shared/                 # Reusable AI assets (all users)
│   ├── music/
│   │   └── {hash}.mp3
│   └── video/
│       └── {hash}.mp4
├── vip/                    # VIP user content
│   ├── voices/
│   │   └── {user_id}/{id}.wav
│   └── finals/
│       └── {user_id}/{id}.mp4
└── temp/                   # 24h ephemeral (Free tier)
    └── {session_id}/
```

### Google Cloud Storage (Psyche Library)
```
gs://subliminalgen-psyche-tracks/
├── track_001.mp3           # Queen Energy
├── track_002.mp3           # Deep Focus
├── track_003.mp3           # Inner Peace
├── track_004.mp3           # Abundance Flow
└── track_005.mp3           # Self Love
```

## 🔌 API Endpoints

### Core Generation
- `POST /api/music/{user_id}` - **ACTIVE**: Generate AI music with state modifiers (caching temporarily disabled)
- `POST /api/music/generate` - **DEPRECATED**: Direct generation (unused by frontend)
- `POST /api/video/generate` - Generate AI video with semantic caching
- `POST /api/audio/combine` - Combine voice + music
- `POST /api/video/combine` - Combine audio + video
- `GET /api/download/{id}` - Stream files from S3

### Audio Processing (Platinum Features)
- `POST /api/platinum/extend-audio` - **NEW**: Extend pre-mixed audio with fade-loop technique
- `POST /api/platinum/backend-combine` - *DEPRECATED*: Complex FFmpeg mixing (kept for reference)

### User Management
- `GET /api/library` - List user creations (VIP only)
- `DELETE /api/creation/{id}` - Delete user creation
- `GET /api/usage` - Get usage statistics

### Psyche Library (VIP Only)
- `GET /psyche-tracks` - Get all available psyche tracks
- `GET /psyche-track/metadata/{id}` - Get single track metadata
- `GET /psyche-track/download/{id}` - Download track audio file

## 📱 iOS App Structure

### Views
```
SubliminalGenApp/
├── Views/
│   ├── HomeView.swift
│   ├── RecordView.swift
│   ├── PromptView.swift
│   ├── PreviewView.swift
│   ├── LibraryView.swift
│   └── SettingsView.swift
├── Services/
│   ├── APIService.swift
│   ├── AudioService.swift
│   ├── CacheService.swift
│   └── AuthService.swift
├── Models/
│   ├── Creation.swift
│   ├── GeneratedAsset.swift
│   └── User.swift
└── Utils/
    ├── Constants.swift
    └── Extensions.swift
```

### Key Features
- **Voice Recording**: AVAudioRecorder with real-time waveform
- **Semantic Caching**: Local cache for generated assets
- **Two-Tier Storage**: Free (local) vs VIP (cloud)
- **Background Processing**: Combine operations in background

## 🎵 Music Generation with State Modifiers

### State Prompt Enhancement
**NEW FEATURE**: Identity states are converted to descriptive presence text for richer music generation.

#### Available State Modifiers
```python
STATE_PROMPT_MODIFIERS = {
    "powerful": "confident, expansive, grounded presence",
    "determined": "focused, steady, forward-moving energy", 
    "freedom": "open, spacious, unrestricted flow",
    "dreamy": "ethereal, floating, slow-evolving textures"
}
```

#### Sample Request
```bash
POST /api/music/user123
{
  "prompt": "peaceful meditation music",
  "music_type": ["powerful", "dreamy"],
  "mood": ["calm"],
  "tag": "meditation",
  "duration": 30
}
```

#### Enhanced Prompt to Lyria
```
"peaceful meditation music, presence: confident, expansive, grounded presence, ethereal, floating, slow-evolving textures, style: powerful, dreamy, mood: calm"
```

### Current Status: Caching Disabled
**TEMPORARY**: All requests generate fresh music via Lyria API
- **Reason**: Improving deduplication logic to prevent old track returns
- **Impact**: Higher API costs, always unique music
- **Timeline**: Cache will be re-enabled with time-based filtering

#### TODO: Smart Caching Implementation
- [ ] Time-based filtering (24-48h cooldown)
- [ ] Track multiple recent UUIDs per user
- [ ] Consider user listening history  
- [ ] Implement cache hit rate optimization
- [ ] Add user preference-based deduplication

## 🧠 Semantic Caching Logic

### Similarity Matching
1. **Text Preprocessing**: Normalize prompt (lowercase, trim, remove special chars)
2. **Embedding Generation**: OpenAI text-embedding-3-small (384 dimensions)
3. **Similarity Search**: Cosine similarity ≥ 0.9 threshold
4. **Fallback**: SHA256 hash exact match

### Cache Strategy
```python
def find_similar_asset(prompt: str, duration: int, asset_type: str):
    # 1. Hash-based exact match
    hash_key = sha256(f"{prompt.lower().strip()}:{duration}:{asset_type}")
    exact_match = db.query_by_hash(hash_key)
    if exact_match:
        return exact_match
    
    # 2. Semantic similarity search
    embedding = generate_embedding(prompt)
    similar = db.similarity_search(embedding, threshold=0.9, type=asset_type)
    if similar and abs(similar.duration - duration) <= 5:  # 5s tolerance
        return similar
    
    # 3. Generate new asset
    return None
```

## 🔒 Privacy & Security

### Data Protection
- **Voice Recordings**: Never uploaded for Free users
- **Encryption**: All S3 objects encrypted at rest
- **Access Control**: Supabase RLS policies
- **API Keys**: Environment variables only

### Retention Policy
- **Free Tier**: 24h local cache, auto-cleanup
- **VIP Tier**: Persistent cloud storage
- **Shared Assets**: Permanent (music/video)

## 💰 Cost Optimization

### API Usage Reduction
- **Semantic Caching**: ~80% cache hit rate expected
- **Shared Assets**: One generation serves multiple users
- **Duration Tolerance**: ±5 seconds reuse window

### Storage Efficiency
- **Compression**: MP3 for audio, H.264 for video
- **Lifecycle Policies**: Auto-delete temp files after 24h
- **CDN**: CloudFront for fast global delivery

## 🎭 Psyche Library Architecture

### Caching Strategy (iOS-Controlled)
- **iOS owns caching**: Decides what to download and store locally
- **Backend supports**: Provides metadata and signed URLs only
- **Offline-first**: Downloaded tracks available without internet
- **User-driven**: Explicit downloads, not automatic caching

### Storage Flow
```
iOS → Backend (VIP check) → GCS (signed URL) → iOS (download & cache)
```

### Access Control
- **VIP Verification**: All endpoints check VIP status via existing auth
- **Signed URLs**: 1-hour temporary access to GCS files
- **Private Bucket**: No public access, signed URLs only
- **RLS Policies**: Database-level access control

### Sample API Usage
```bash
# Get all tracks (VIP only)
GET /psyche-tracks?user_id=vip-user-123

# Response
{
  "tracks": [
    {
      "id": "track_001",
      "title": "Queen Energy",
      "duration": 180,
      "tags": ["queen", "power", "confidence"]
    }
  ]
}
```

### 🔧 Adding New Psyche Tracks

#### Method 1: Automated Script (Recommended)
```bash
# Use the admin script
python add_psyche_track.py track_007.m4a "Confidence Boost" 240 "confidence,power,success"
```

#### Method 2: Manual Process
**Step 1: Upload to Google Cloud Storage**
```bash
gsutil cp new_track.m4a gs://subliminalgen-temp-files/psyche-tracks/track_006.m4a
```

**Step 2: Add to Database**
```sql
INSERT INTO psyche_tracks (id, title, duration, tags, file_path) VALUES
('track_006', 'New Track Title', 240, '["tag1", "tag2", "tag3"]', 'track_006.m4a');
```

#### File Requirements
- **Format**: M4A (AAC codec, 128kbps) - optimized for iOS
- **Naming**: `track_XXX.m4a` (sequential numbering)
- **Duration**: Accurate duration in seconds
- **Tags**: JSON array of relevant keywords

#### Verification
```bash
# Test the new track
curl "https://your-api.com/psyche-tracks?user_id=vip-user-id"
curl "https://your-api.com/psyche-track/download/track_006?user_id=vip-user-id"
```

## 🎵 Audio Processing Technology

### Platinum Extend-Audio Pipeline
**New optimized approach for audio extension:**

#### **Technology Stack**
- **FFmpeg**: Professional audio processing engine
- **Python subprocess**: Secure FFmpeg command execution
- **Fade-Loop Algorithm**: Pre-fade input → Simple loop duplication

#### **Processing Flow**
1. **iOS Pre-mixing**: Voice + music combined locally (30s-5min)
2. **Backend Extension**: Apply fades → Loop to target duration
3. **Natural Endings**: No abrupt cuts, smooth meditation experience

#### **Performance Benefits**
- **10-20x faster** than complex mixing (2-10s vs 30-60s)
- **Memory efficient**: Streaming processing, no RAM spikes
- **Predictable**: Linear scaling with loop count
- **Professional quality**: 2-second fade in/out transitions (optimal for meditation)

#### **Supported Durations**
- **Input**: 30 seconds to 5 minutes (pre-mixed)
- **Output**: ~10min, ~15min, ~30min (approximate, natural endings)
- **Algorithm**: `loops = target_duration ÷ input_duration`

#### **FFmpeg Commands**
```bash
# Step 1: Apply fade in/out
ffmpeg -i input.wav -filter_complex \
  "[0:a]afade=t=in:ss=0:d=2,afade=t=out:st=END-2:d=2[faded]" \
  faded.wav

# Step 2: Loop the faded version
ffmpeg -stream_loop LOOPS-1 -i faded.wav -c copy output.wav
```

## 🚀 Deployment Strategy

### Backend (FastAPI)
- **Platform**: Render.com or Railway
- **Environment**: Python 3.11+
- **Dependencies**: FastAPI, Supabase, FFmpeg, subprocess
- **Audio Processing**: FFmpeg 8.0+ with fade/loop filters

### iOS App
- **Target**: iOS 15.0+
- **Architecture**: MVVM with Combine
- **Dependencies**: Supabase Swift SDK, AVAudioRecorder
- **Audio Mixing**: Local voice+music combination

### Infrastructure
- **Database**: Supabase (PostgreSQL + Auth)
- **Storage**: AWS S3 with CloudFront + Google Cloud Storage (Psyche)
- **Audio Processing**: FFmpeg streaming pipeline
- **Monitoring**: Supabase Analytics + Sentry

## 📊 Performance Targets

### Response Times
- **Cache Hit**: < 500ms
- **New Generation**: < 30s (music), < 60s (video)
- **Audio Extension**: 2-10s (vs 30-60s previous approach)
- **File Upload**: < 10s for 1MB file

### Audio Processing Performance
- **3-loop extension**: ~3 seconds processing
- **9-loop extension**: ~8 seconds processing
- **Memory usage**: <100MB (streaming approach)
- **File size**: 15-50MB output (vs 100MB+ previous)

### Scalability
- **Concurrent Users**: 1000+
- **Storage**: Unlimited (S3)
- **Cache Size**: 10GB+ semantic index
- **Audio Pipeline**: Handles 30min+ extensions efficiently

## 🧪 Testing Strategy

### Backend Testing
- Unit tests for semantic caching
- Integration tests for AI APIs
- Load testing for concurrent requests

### iOS Testing
- UI tests for recording flow
- Unit tests for audio processing
- Performance tests for large files

## 📈 Future Enhancements

### Phase 2 Features
- **Batch Processing**: Multiple creations at once
- **Advanced Mixing**: EQ, reverb, compression
- **Social Sharing**: Export to social platforms
- **Analytics**: Usage insights and recommendations

### Technical Improvements
- **Edge Caching**: Redis for faster lookups
- **Streaming**: Real-time audio/video processing
- **ML Models**: On-device voice enhancement

## 🛠️ Admin Tools

### Psyche Library Management
- **add_psyche_track.py**: Automated script for adding new tracks
- **database_psyche_setup.sql**: Initial database schema and sample data
- **test_psyche_endpoints.py**: Comprehensive API testing suite

### Usage Examples
```bash
# Add new track
python add_psyche_track.py track_008.m4a "Deep Sleep" 300 "sleep,relaxation,peace"

# Test all endpoints
python test_psyche_endpoints.py

# Setup database (first time)
psql -h supabase-host -d postgres -f database_psyche_setup.sql
```
