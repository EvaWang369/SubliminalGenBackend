from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import os
import uuid
import time
from pathlib import Path
from dotenv import load_dotenv
from services.music_service import MusicService
from services.lyria_music import LyriaMusic
from models.requests import MusicGenerateRequest
from models.responses import GenerationResponse, LibraryResponse, UserCreation

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

@app.post("/api/audio/combine")
async def combine_audio(
    voice_file: UploadFile = File(...),
    music_id: str = None,
    user_id: str = None,
    is_vip: bool = False,
    title: str = None
):
    """Combine voice recording with AI music"""
    try:
        # Process voice file
        voice_data = await voice_file.read()
        
        if not music_id:
            raise HTTPException(status_code=400, detail="music_id is required")
        
        # For now, create a simple combined file (mock implementation)
        combined_file_id = str(uuid.uuid4())
        combined_file_path = uploads_dir / f"{combined_file_id}_combined.wav"
        
        # Mock audio combining - in production, use actual audio processing
        with open(combined_file_path, "wb") as f:
            f.write(voice_data)  # Simplified - would combine with music
        
        file_url = f"http://0.0.0.0:8001/files/{combined_file_id}_combined.wav"
        
        if is_vip and user_id:
            # Store for VIP users in Supabase
            creation_title = title or f"Creation {int(time.time())}"
            
            creation_data = {
                "user_id": user_id,
                "title": creation_title,
                "voice_url": None,  # Could store voice separately if needed
                "combined_url": file_url,
                "music_id": music_id,
                "created_at": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Store in Supabase user_creations table
            result = music_service.supabase.table("user_creations").insert(creation_data).execute()
            
            if result.data:
                creation_id = result.data[0]['id']
                return {
                    "creation_id": creation_id,
                    "file_url": file_url,
                    "title": creation_title
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to store creation")
        else:
            # Return temporary URL for free users
            return {
                "temp_url": file_url,
                "expires_in": 86400,  # 24 hours
                "message": "File will be deleted after 24 hours. Upgrade to VIP to save permanently."
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio combination failed: {str(e)}")

@app.get("/api/library", response_model=LibraryResponse)
async def get_user_library(user_id: str):
    """Get user's creation library (VIP only)"""
    try:
        # Get user creations from Supabase
        result = music_service.supabase.table("user_creations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        creations = []
        for item in result.data:
            creation = UserCreation(
                id=item['id'],
                title=item['title'],
                voice_url=item.get('voice_url'),
                combined_url=item['combined_url'],
                created_at=item['created_at']
            )
            creations.append(creation)
        
        return LibraryResponse(creations=creations)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get library: {str(e)}")

@app.delete("/api/creation/{creation_id}")
async def delete_creation(creation_id: str, user_id: str):
    """Delete a user creation (VIP only)"""
    try:
        # Verify ownership and delete from Supabase
        result = music_service.supabase.table("user_creations").delete().eq("id", creation_id).eq("user_id", user_id).execute()
        
        if result.data:
            # Also delete the physical file
            try:
                file_name = result.data[0]['combined_url'].split('/')[-1]
                file_path = uploads_dir / file_name
                if file_path.exists():
                    file_path.unlink()
            except:
                pass  # File deletion is not critical
            
            return {"message": "Creation deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Creation not found or not owned by user")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete creation: {str(e)}")

@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    """Stream/download files"""
    try:
        file_path = uploads_dir / file_id
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        def file_generator():
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        
        return StreamingResponse(
            file_generator(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={file_id}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)