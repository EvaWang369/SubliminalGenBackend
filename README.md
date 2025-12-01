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

## ☁️ S3 Storage Structure
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

## 🔌 API Endpoints

### Core Generation
- `POST /api/music/generate` - Generate AI music with semantic caching
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
- **Storage**: AWS S3 with CloudFront
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
