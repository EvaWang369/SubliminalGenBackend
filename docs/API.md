# SubliminalGen API Documentation

## Base URL
```
http://localhost:8000/api
```

## Authentication
Currently using simple user_id parameter. In production, implement proper JWT authentication.

## Endpoints

### POST /music/generate
Generate AI music with semantic caching.

**Request Body:**
```json
{
  "prompt": "Calm ocean waves with soft piano",
  "duration": 60,
  "style": "ambient",
  "mood": "calm"
}
```

**Response:**
```json
{
  "id": "uuid",
  "file_url": "https://s3.../music.mp3",
  "cached": true,
  "duration": 60,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### POST /video/generate
Generate AI video with semantic caching.

**Request Body:**
```json
{
  "prompt": "Flowing abstract patterns in blue and gold",
  "duration": 60,
  "style": "abstract",
  "resolution": "1080p"
}
```

**Response:**
```json
{
  "id": "uuid",
  "file_url": "https://s3.../video.mp4",
  "cached": false,
  "duration": 60,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### POST /audio/combine
Combine voice recording with AI music.

**Request (multipart/form-data):**
- `voice_file`: Audio file (WAV/MP3)
- `music_id`: Generated music asset ID
- `user_id`: User ID (optional, VIP only)
- `is_vip`: Boolean flag

**Response (Free User):**
```json
{
  "temp_url": "https://s3.../temp/audio.mp3",
  "expires_in": 86400
}
```

**Response (VIP User):**
```json
{
  "creation_id": "uuid",
  "file_url": "https://s3.../vip/final.mp3"
}
```

### POST /video/combine
Combine audio mix with AI video.

**Request (multipart/form-data):**
- `audio_file`: Combined audio file
- `video_id`: Generated video asset ID
- `user_id`: User ID (VIP only)
- `is_vip`: Boolean flag

**Response:**
```json
{
  "creation_id": "uuid",
  "file_url": "https://s3.../vip/final.mp4"
}
```

### GET /library
Get user's creation library (VIP only).

**Query Parameters:**
- `user_id`: User ID

**Response:**
```json
{
  "creations": [
    {
      "id": "uuid",
      "title": "My Creation",
      "voice_url": "https://s3.../voice.wav",
      "combined_url": "https://s3.../final.mp3",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

### GET /download/{file_id}
Stream file from S3.

**Response:**
Binary file stream with appropriate Content-Type header.

## Error Responses

All endpoints return errors in this format:
```json
{
  "detail": "Error message"
}
```

Common HTTP status codes:
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (asset/file not found)
- `500`: Internal Server Error (API failures, processing errors)

## Rate Limiting

Currently no rate limiting implemented. In production, consider:
- 100 requests/minute per user for generation endpoints
- 1000 requests/minute for download endpoints
- Separate limits for free vs VIP users

## Caching Strategy

### Semantic Similarity
- Uses all-MiniLM-L6-v2 embeddings (384 dimensions)
- Cosine similarity threshold: 0.9
- Duration tolerance: ±5 seconds

### Cache Lookup Process
1. Generate SHA256 hash of normalized prompt + duration + type
2. Check for exact hash match in database
3. If no match, generate embedding and search for similar assets
4. Return cached asset if similarity ≥ 0.9 and duration within tolerance
5. Otherwise, generate new asset and cache it

### Cache Performance
- Expected hit rate: 80%+
- Lookup time: <100ms
- Storage: Unlimited (S3 + Supabase)