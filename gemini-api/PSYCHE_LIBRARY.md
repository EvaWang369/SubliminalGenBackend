# Psyche Library API Implementation

## Overview
The Psyche Library provides VIP users access to curated subliminal audio tracks using **Option 2 Architecture**: clean separation of metadata browsing and on-demand downloads.

## 🎭 Psyche Library Architecture (Option 2)

### Caching Strategy (iOS-Controlled)
- **iOS owns caching**: Sole authority over what to download and store locally
- **Backend provides**: Metadata and download URLs only (no cache management)
- **Offline-first**: Downloaded tracks available without internet
- **Download-on-demand**: Signed URLs generated only when user taps download

### Storage Flow
```
iOS → /psyche-tracks (metadata only)
iOS → /psyche-track/download/{id} → signed URL → download & cache
```

### Access Control
- **VIP Verification**: All endpoints check VIP status via AuthService
- **Short-lived signed URLs**: 1-hour expiration for security
- **Private GCS bucket**: No public access, signed URLs only
- **RLS Policies**: Optional defense-in-depth (AuthService is primary)

## API Endpoints

### 1. GET /psyche-tracks
**Purpose**: Get all available psyche tracks (metadata only)  
**Auth**: VIP users only  
**Parameters**: `user_id` (query parameter)

**Response** (Clean metadata - no downloadURL):
```json
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

### 2. GET /psyche-track/metadata/{track_id}
**Purpose**: Get single track metadata  
**Auth**: VIP users only  
**Parameters**: `user_id` (query parameter)

**Response**: Single track object (metadata only)

### 3. GET /psyche-track/download/{track_id}
**Purpose**: Generate signed URL and download audio file  
**Auth**: VIP users only  
**Parameters**: `user_id` (query parameter)  
**Response**: 302 redirect to 1-hour signed GCS URL

## Database Schema

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

-- RLS Policy (VIP users only)
ALTER TABLE psyche_tracks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "VIP users can read psyche tracks" ON psyche_tracks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM auth.users 
            WHERE auth.users.id = auth.uid() 
            AND (auth.users.raw_user_meta_data->>'isVIP')::boolean = true
        )
    );
```

## Storage Structure
```
gs://subliminalgen-temp-files/psyche-tracks/
├── track_001.m4a           # Queen Energy (iOS-optimized AAC)
├── track_002.m4a           # Deep Focus
├── track_003.m4a           # Inner Peace
├── track_004.m4a           # Abundance Flow
└── track_005.m4a           # Self Love
```

**Format**: M4A (AAC codec, 128kbps) - optimized for iOS caching

## Security Features

### VIP Verification
- All endpoints verify VIP status via `auth_service.get_user_profile()`
- Non-VIP users receive 403 Forbidden with specific error message
- Uses existing JWT/auth system

### Signed URLs (On-Demand Only)
- Generated only when user taps download (not during browse)
- 1-hour expiration for security
- Service account credentials with GCS fallback
- No wasted URLs for tracks never downloaded

### Row Level Security (RLS)
- Supabase RLS policies restrict database access to VIP users only
- Additional server-side verification for defense in depth

## Error Responses

### VIP Required (403)
```json
{
  "error": "VIP_REQUIRED",
  "message": "Psyche Library requires VIP subscription"
}
```

### Track Not Found (404)
```json
{
  "detail": "Track not found"
}
```

## Setup Instructions

### 1. Database Setup
```bash
# Run the SQL schema
psql -h your-supabase-host -d postgres -f database_psyche_setup.sql

# Or use Supabase dashboard SQL editor
```

### 2. Populate Sample Data
```bash
python setup_psyche_data.py
```

### 3. GCS Bucket Setup
```bash
# Using existing bucket with psyche-tracks folder
gsutil cp track_*.m4a gs://subliminalgen-temp-files/psyche-tracks/

# Verify upload
gsutil ls gs://subliminalgen-temp-files/psyche-tracks/
```

### 4. Environment Variables
```bash
# Already configured in existing .env
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

## Testing

### Run Test Suite
```bash
python test_psyche_endpoints.py
```

### Manual Testing
```bash
# VIP user - get metadata only
curl "https://subliminalgen-backend-311287456014.us-central1.run.app/psyche-tracks?user_id=037b15a2-4c47-4473-9e6a-0e710c3c39a5"

# Non-VIP user - should return 403
curl "https://subliminalgen-backend-311287456014.us-central1.run.app/psyche-tracks?user_id=free-user-456"

# Get single track metadata
curl "https://subliminalgen-backend-311287456014.us-central1.run.app/psyche-track/metadata/track_001?user_id=037b15a2-4c47-4473-9e6a-0e710c3c39a5"

# Download track (generates signed URL + redirect)
curl -L "https://subliminalgen-backend-311287456014.us-central1.run.app/psyche-track/download/track_001?user_id=037b15a2-4c47-4473-9e6a-0e710c3c39a5" -o track_001.m4a
```

## Sample API Usage

### Request/Response Examples

**GET /psyche-tracks?user_id=vip-user-123**
```json
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

**GET /psyche-track/download/track_001?user_id=vip-user-123**
```
HTTP 302 Redirect
Location: https://storage.googleapis.com/subliminalgen-temp-files/psyche-tracks/track_001.m4a?X-Goog-Algorithm=...
```

**Non-VIP Response (403)**
```json
{
  "detail": {
    "error": "VIP_REQUIRED",
    "message": "Psyche Library requires VIP subscription"
  }
}
```

## Integration Points

### Existing Services Used
- `AuthService`: VIP status verification
- `PsycheService`: New service for track management
- Supabase: Database and RLS policies
- Google Cloud Storage: Audio file storage

### Response Format
- Follows existing API patterns from main.py
- Uses Pydantic models for type safety
- Consistent error handling with HTTPException

## Performance Considerations

### Caching
- **No backend caching**: iOS owns all cache decisions
- **Metadata queries**: Fast database lookups with GIN index on tags
- **Signed URLs**: Generated on-demand, 1-hour expiration
- **Analytics ready**: Separate view/download tracking (Phase 2)

### Scalability
- GCS handles unlimited storage and bandwidth
- Supabase scales automatically
- Signed URLs distribute load away from API server

## Future Enhancements

### Phase 2 Features
- **Analytics tables**: Track exposure vs download intent
- **Personalization**: User-specific track recommendations
- **Rate limiting**: Download quotas per user
- **A/B testing**: Track availability experiments

### Analytics (Planned)
- **library_view**: User browsed psyche library
- **track_exposure**: User saw specific track
- **download_intent**: User tapped download
- **actual_download**: File successfully downloaded