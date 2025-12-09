from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import os
import uuid
import time
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import tempfile
from google.cloud import storage
from datetime import timedelta

from services.music_service import MusicService
from services.lyria_music import LyriaMusic
from services.auth_service import AuthService
from models.requests import MusicGenerateRequest, SignUpRequest, SignInRequest, GoogleAuthRequest, VIPStatusRequest
from models.responses import GenerationResponse, LibraryResponse, UserCreation, AuthResponse

load_dotenv()

app = FastAPI(title="SubliminalGen API", version="1.0.0")

# ---------------------------------------------------
# CORS
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# FILE STORAGE SETUP
# ---------------------------------------------------
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)

app.mount("/files", StaticFiles(directory="uploads"), name="files")

BASE_URL = os.getenv("BASE_URL", "http://0.0.0.0:8080")
PORT = int(os.getenv("PORT", 8080))  # Cloud Run uses 8080

# ---------------------------------------------------
# SERVICES
# ---------------------------------------------------
music_service = MusicService()
music_generator = LyriaMusic()
auth_service = AuthService()

# ---------------------------------------------------
# GCS HELPER FOR LARGE FILES
# ---------------------------------------------------
def upload_to_gcs_and_get_signed_url(file_bytes: bytes, file_name: str, expiration_hours: int = 1) -> str:
    """
    Upload large file to GCS and return signed URL for download.
    Cloud Run cannot serve files >32MB, so we use GCS + signed URLs.
    """
    try:
        client = storage.Client()
        bucket_name = "subliminalgen-temp-files"
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        print(f"☁️ Uploading {len(file_bytes)} bytes to GCS: gs://{bucket_name}/{file_name}")
        
        # Upload file to GCS
        blob.upload_from_string(file_bytes, content_type="audio/wav")
        
        # Generate signed URL (temporary download link)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=expiration_hours),
            method="GET",
            response_disposition=f'attachment; filename="{file_name}"'
        )
        
        print(f"✅ GCS upload successful, signed URL generated (expires in {expiration_hours}h)")
        return signed_url
        
    except Exception as e:
        print(f"❌ GCS upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


# ---------------------------------------------------
# ROOT
# ---------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "SubliminalGen API",
        "version": "1.0.0",
        "status": "suno-only",
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}


# ---------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------
@app.post("/auth/signup", response_model=AuthResponse)
async def sign_up(request: SignUpRequest):
    """Create new user account"""
    try:
        user_data = await auth_service.sign_up(
            email=request.email,
            password=request.password,
            name=request.name
        )
        print(f"✅ Signup success: {request.email} -> {user_data['id']}")
        return AuthResponse(**user_data)
    except ValueError as e:
        print(f"❌ Signup failed: {request.email} - {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"💥 Signup error: {request.email} - {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sign up failed: {str(e)}")


@app.post("/auth/signin", response_model=AuthResponse)
async def sign_in(request: SignInRequest):
    """Authenticate user with email/password"""
    try:
        user_data = await auth_service.sign_in(
            email=request.email,
            password=request.password
        )
        print(f"✅ Signin success: {request.email} -> {user_data['id']}")
        return AuthResponse(**user_data)
    except ValueError as e:
        print(f"❌ Signin failed: {request.email} - {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        print(f"💥 Signin error: {request.email} - {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sign in failed: {str(e)}")


@app.post("/auth/google", response_model=AuthResponse)
async def sign_in_with_google(request: GoogleAuthRequest):
    """Authenticate user with Google ID token"""
    try:
        user_data = await auth_service.sign_in_with_google(request.id_token)
        print(f"✅ Google signin success: {user_data['email']} -> {user_data['id']}")
        return AuthResponse(**user_data)
    except ValueError as e:
        print(f"❌ Google signin failed: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        print(f"💥 Google signin error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Google sign in failed: {str(e)}")


@app.post("/user/vip-status", response_model=AuthResponse)
async def update_vip_status(request: VIPStatusRequest):
    """Update user VIP status after in-app purchase"""
    try:
        user_data = await auth_service.update_vip_status(
            user_id=request.user_id,
            transaction_id=request.transaction_id,
            subscription_type=request.subscription_type,
            subscription_duration_days=request.subscription_duration_days,
            vip_level=request.vip_level
        )
        print(f"✅ VIP UPGRADE: {request.user_id} -> VIP: {user_data.get('isVIP', False)} | Type: {request.subscription_type} | Days: {request.subscription_duration_days} | Transaction: {request.transaction_id} | End: {user_data.get('vip_end_date', 'N/A')}")
        return AuthResponse(**user_data)
    except ValueError as e:
        print(f"❌ VIP UPGRADE FAILED: {request.user_id} | Transaction: {request.transaction_id} | Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"💥 VIP UPGRADE ERROR: {request.user_id} | Transaction: {request.transaction_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"VIP update failed: {str(e)}")


@app.get("/user/profile/{user_id}", response_model=AuthResponse)
async def get_user_profile(user_id: str):
    """Get user profile with current VIP status"""
    try:
        print(f"📋 Getting profile for user: {user_id}")
        user_data = await auth_service.get_user_profile(user_id)
        print(f"✅ Profile retrieved: VIP={user_data.get('isVIP', False)}")
        return AuthResponse(**user_data)
    except ValueError as e:
        print(f"❌ Profile not found: {user_id} - {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"💥 Profile error: {user_id} - {str(e)}")
        raise HTTPException(status_code=500, detail=f"Get profile failed: {str(e)}")


# ---------------------------------------------------
# MUSIC GENERATION (CACHED / HYBRID)
# ---------------------------------------------------
@app.post("/api/music/{user_id}")
async def generate_music_for_user(user_id: str, request: MusicGenerateRequest):
    """
    Unified endpoint - handles both simple and enhanced requests via MusicService.
    """
    try:
        print(f"🎵 Generating music for user: {user_id}")
        print(f"📝 Request: {request.prompt} (tag: {request.tag})")

        print("🎆 Enhanced mode (hybrid caching)")
        result = await music_service.get_music_with_enhanced_prompt(user_id, request)

        status = "from cache" if result.get("cached") else "newly generated"
        print(f"✅ Music {status}: {result.get('url')}")
        return result

    except Exception as e:
        print(f"❌ Music service failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Music service failed: {str(e)}",
        )


# ---------------------------------------------------
# DIRECT MUSIC GENERATION (LOCAL FILE)
# ---------------------------------------------------
@app.post("/api/music/generate", response_model=GenerationResponse)
async def generate_music_direct(request: MusicGenerateRequest):
    """
    Direct music generation with enhanced prompts (local storage, no caching).
    """
    try:
        enhanced_prompt = music_service.enhance_prompt(
            request.prompt,
            request.music_type,
            request.instruments,
            request.mood,
            request.frequencies,
        )

        print(f"🎵 Direct generation with enhanced prompt: {enhanced_prompt}")

        audio_data = await music_generator.generate_music_with_config(
            enhanced_prompt,
            request.tag,
        )

        file_id = str(uuid.uuid4())
        file_path = uploads_dir / f"{file_id}.wav"

        with open(file_path, "wb") as f:
            f.write(audio_data)

        file_url = f"{BASE_URL}/files/{file_id}.wav"

        return GenerationResponse(
            id=file_id,
            file_url=file_url,
            cached=False,
            duration=request.duration,
        )

    except Exception as e:
        print(f"❌ Music generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Music generation failed: {str(e)}",
        )


# ---------------------------------------------------
# UPLOAD PRE-COMBINED AUDIO (FRONTEND COMBINED)
# ---------------------------------------------------
@app.post("/api/audio/upload")
async def upload_combined_audio(
    combined_file: UploadFile = File(...),
    user_id: str = Form(...),
    creation_id: str = Form(...),
    title: str = Form(...),
):
    """
    Upload pre-combined audio file from VIP users only.
    creation_id is provided by iOS client.
    """
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        if not creation_id:
            raise HTTPException(status_code=400, detail="creation_id is required")
        if not title:
            raise HTTPException(status_code=400, detail="title is required")

        print("📥 /api/audio/upload called (VIP only)")
        print(f"   user_id     = {user_id}")
        print(f"   creation_id = {creation_id}")
        print(f"   title       = {title}")
        print(f"   filename    = {combined_file.filename}")

        combined_data = await combined_file.read()
        if not combined_data:
            raise HTTPException(status_code=400, detail="Empty combined_file")

        # Upload to Supabase Storage using provided creation_id
        file_path = f"vip/{user_id}/{creation_id}.wav"
        print(f"☁️ Uploading to Supabase path: {file_path}")

        upload_result = music_service.supabase.storage.from_("music").upload(
            file_path,
            combined_data,
            {"content-type": "audio/wav"},
        )
        print(f"   Supabase upload result: {upload_result}")

        # Get public URL
        cloud_url = music_service.supabase.storage.from_("music").get_public_url(
            file_path
        )
        print(f"   Public URL: {cloud_url}")

        # Insert into database with provided creation_id
        creation_data = {
            "creation_id": creation_id,
            "user_id": user_id,
            "title": title,
            "voice_url": None,
            "combined_url": cloud_url,
            "music_id": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        print("🗄 Inserting into user_creations:", creation_data)

        db_result = (
            music_service.supabase
            .from_("user_creations")
            .insert(creation_data)
            .execute()
        )
        print("   Supabase insert result:", db_result)

        if getattr(db_result, "data", None):
            return {
                "url": cloud_url,
                "creation_id": creation_id,
            }
        else:
            print("❌ No data returned from Supabase user_creations insert")
            raise HTTPException(
                status_code=500,
                detail="Failed to store creation in database",
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Audio upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio upload failed: {str(e)}")


# ---------------------------------------------------
# EXTEND AUDIO (NEW PLATINUM FEATURE) - SIMPLE LOOP APPROACH
# ---------------------------------------------------
from extend_audio_gcs import extend_audio_gcs

@app.post("/api/platinum/extend-audio")
async def extend_audio_endpoint(
    combined_file: UploadFile = File(...),
    loops: int = Form(...),
    target_duration_label: str = Form(...),
    user_id: str = Form(...),
    is_vip: str = Form("false"),
    title: str = Form(None),
):
    """Platinum extend-audio endpoint - delegates to GCS storage"""
    return await extend_audio_gcs(
        combined_file=combined_file,
        loops=loops,
        target_duration_label=target_duration_label,
        user_id=user_id,
        is_vip=is_vip,
        title=title
    )


# ---------------------------------------------------
# VIP LIBRARY
# ---------------------------------------------------
@app.get("/api/library", response_model=LibraryResponse)
async def get_user_library(user_id: str):
    """
    Get user's creation library (VIP only).
    """
    try:
        print(f"📚 Fetching library for user_id={user_id}")
        result = (
            music_service.supabase
            .from_("user_creations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        print("   Supabase select result:", result)

        creations = []
        for item in (result.data or []):
            creation = UserCreation(
                id=item["creation_id"],
                title=item["title"],
                voice_url=item.get("voice_url"),
                combined_url=item["combined_url"],
                created_at=item["created_at"],
            )
            creations.append(creation)

        return LibraryResponse(creations=creations)

    except Exception as e:
        print(f"❌ Failed to get library: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get library: {str(e)}")



# ---------------------------------------------------
# DELETE CREATION
# ---------------------------------------------------
@app.delete("/api/creation/{creation_id}")
async def delete_creation(creation_id: str, user_id: str):
    """
    Delete a user creation (VIP only)
    """
    try:
        print(f"🗑 Deleting creation {creation_id} for user {user_id}")
        result = (
            music_service.supabase
            .from_("user_creations")
            .delete()
            .eq("creation_id", creation_id)
            .eq("user_id", user_id)
            .execute()
        )
        print("   Supabase delete result:", result)

        if result.data:
            # Try to delete local file if path points to local uploads
            try:
                combined_url = result.data[0].get("combined_url")
                if combined_url and "/files/" in combined_url:
                    file_name = combined_url.split("/files/")[-1]
                    file_path = uploads_dir / file_name
                    if file_path.exists():
                        file_path.unlink()
                        print(f"   Deleted local file: {file_path}")
            except Exception as e:
                print(f"   (Non-critical) file delete error: {e}")

            return {"message": "Creation deleted successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail="Creation not found or not owned by user",
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Failed to delete creation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete creation: {str(e)}")


# ---------------------------------------------------
# FILE DOWNLOAD / STREAM
# ---------------------------------------------------
@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    """
    Stream/download files from local uploads folder.
    """
    try:
        file_path = uploads_dir / file_id
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        def file_generator():
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

        return StreamingResponse(
            file_generator(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={file_id}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Download failed: {str(e)}")
        raise HTTPException(status_code=404, detail="File not found")


# ---------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
