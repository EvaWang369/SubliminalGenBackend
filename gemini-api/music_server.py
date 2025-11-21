from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from services.music_service import MusicService
from services.lyria_music import LyriaMusic
from models.requests import MusicGenerateRequest
from models.responses import GenerationResponse

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

# Create uploads directory
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)

# Serve static files
app.mount("/files", StaticFiles(directory="uploads"), name="files")

# Initialize Music Service
music_service = MusicService()
music_generator = LyriaMusic()

@app.get("/")
async def root():
    return {"message": "SubliminalGen API", "version": "1.0.0", "status": "suno-only"}

@app.get("/api/music/{user_id}")
async def get_music_for_user(user_id: str, tag: str = "meditation"):
    """Get music track for user with caching"""
    try:
        print(f"🎵 Getting {tag} music for user: {user_id}")
        
        result = await music_service.get_music_for_user(user_id, tag)
        
        status = "from cache" if result['cached'] else "newly generated"
        print(f"✅ Music {status}: {result['url']}")
        
        return result
        
    except Exception as e:
        print(f"❌ Music service failed: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Music service failed: {str(e)}"
        )

@app.post("/api/music/generate", response_model=GenerationResponse)
async def generate_music_direct(request: MusicGenerateRequest):
    """Direct music generation (legacy endpoint)"""
    try:
        print(f"🎵 Direct generation: {request.prompt}")
        
        audio_data = await music_generator.generate_music(request.prompt, request.duration)
        
        # Save to local file
        file_id = str(uuid.uuid4())
        file_path = uploads_dir / f"{file_id}.wav"
        
        with open(file_path, "wb") as f:
            f.write(audio_data)
        
        file_url = f"http://0.0.0.0:8001/files/{file_id}.wav"
        
        return GenerationResponse(
            id=file_id,
            file_url=file_url,
            cached=False,
            duration=request.duration
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Music generation failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)