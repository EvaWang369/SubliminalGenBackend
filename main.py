from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import os
from dotenv import load_dotenv

from services.suno_ai import SunoAI
from services.mock_services import MockSemanticCache, MockAudioProcessor, MockVideoProcessor, get_mock_s3_client
from models.requests import MusicGenerateRequest, VideoGenerateRequest, CombineRequest
from models.responses import GenerationResponse, LibraryResponse

load_dotenv()

app = FastAPI(title="SubliminalGen API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services with mocks (avoiding import issues)
semantic_cache = MockSemanticCache()

suno_ai = SunoAI()
audio_processor = MockAudioProcessor()
video_processor = MockVideoProcessor()

@app.get("/")
async def root():
    return {"message": "SubliminalGen API", "version": "1.0.0", "status": "testing"}

@app.post("/api/music/generate", response_model=GenerationResponse)
async def generate_music(request: MusicGenerateRequest):
    """Generate AI music with semantic caching"""
    try:
        # Check semantic cache first
        cached_asset = await semantic_cache.find_similar_music(
            request.prompt, request.duration
        )
        
        if cached_asset:
            await semantic_cache.increment_usage(cached_asset["id"])
            return GenerationResponse(
                id=cached_asset["id"],
                file_url=cached_asset["file_url"],
                cached=True,
                duration=cached_asset["duration"]
            )
        
        # Generate new music using Suno AI
        try:
            audio_data = await suno_ai.generate_music(request.prompt, request.duration)
        except Exception as e:
            # Fallback to mock data for testing
            audio_data = b"MOCK_AUDIO_DATA"
        
        # Store in cache
        asset = await semantic_cache.store_music_asset(
            prompt=request.prompt,
            duration=request.duration,
            audio_data=audio_data
        )
        
        return GenerationResponse(
            id=asset["id"],
            file_url=asset["file_url"],
            cached=False,
            duration=asset["duration"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/video/generate", response_model=GenerationResponse)
async def generate_video(request: VideoGenerateRequest):
    """Generate AI video with semantic caching"""
    try:
        # Check semantic cache
        cached_asset = await semantic_cache.find_similar_video(
            request.prompt, request.duration
        )
        
        if cached_asset:
            await semantic_cache.increment_usage(cached_asset["id"])
            return GenerationResponse(
                id=cached_asset["id"],
                file_url=cached_asset["file_url"],
                cached=True,
                duration=cached_asset["duration"]
            )
        
        # Generate mock video data
        video_data = b"MOCK_VIDEO_DATA"
        
        # Store in cache
        asset = await semantic_cache.store_video_asset(
            prompt=request.prompt,
            duration=request.duration,
            video_data=video_data
        )
        
        return GenerationResponse(
            id=asset["id"],
            file_url=asset["file_url"],
            cached=False,
            duration=asset["duration"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audio/combine")
async def combine_audio(
    voice_file: UploadFile = File(...),
    music_id: str = None,
    user_id: str = None,
    is_vip: bool = False
):
    """Combine voice recording with AI music"""
    try:
        # Process voice file
        voice_data = await voice_file.read()
        
        # Get music asset
        music_asset = await semantic_cache.get_asset(music_id)
        if not music_asset:
            raise HTTPException(status_code=404, detail="Music asset not found")
        
        # Combine audio
        combined_audio = await audio_processor.combine_voice_music(
            voice_data, music_asset["file_url"]
        )
        
        if is_vip and user_id:
            # Store for VIP users
            creation = await semantic_cache.store_user_creation(
                user_id=user_id,
                voice_data=voice_data,
                combined_data=combined_audio,
                title=f"Creation {len(await semantic_cache.get_user_creations(user_id)) + 1}"
            )
            return {"creation_id": creation["id"], "file_url": creation["combined_url"]}
        else:
            # Return temporary URL for free users
            temp_url = await semantic_cache.store_temp_file(combined_audio, "audio")
            return {"temp_url": temp_url, "expires_in": 86400}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library")
async def get_library(user_id: str):
    """Get user's creation library (VIP only)"""
    try:
        creations = await semantic_cache.get_user_creations(user_id)
        return LibraryResponse(creations=creations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    """Stream file from S3"""
    try:
        s3_client = get_mock_s3_client()
        file_stream = s3_client.get_file_stream(file_id)
        
        return StreamingResponse(
            file_stream,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={file_id}"}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)