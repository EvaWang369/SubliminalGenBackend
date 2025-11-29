from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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

BASE_URL = os.getenv("BASE_URL", "http://0.0.0.0:8001")
PORT = int(os.getenv("PORT", 8001))

# ---------------------------------------------------
# SERVICES
# ---------------------------------------------------
music_service = MusicService()
music_generator = LyriaMusic()
auth_service = AuthService()


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
    is_vip: str = Form("false"),
    title: str = Form(None),
):
    """
    Upload pre-combined audio file from frontend.

    - Free users: file stored locally, temp URL, not in DB.
    - VIP users: file uploaded to Supabase Storage + inserted into user_creations.
    """
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        # Convert string to boolean
        is_vip_bool = is_vip.lower() in ("true", "1", "yes")

        print("📥 /api/audio/upload called")
        print(f"   user_id   = {user_id}")
        print(f"   is_vip    = {is_vip} -> {is_vip_bool}")
        print(f"   title     = {title}")
        print(f"   filename  = {combined_file.filename}")

        combined_data = await combined_file.read()
        if not combined_data:
            raise HTTPException(status_code=400, detail="Empty combined_file")

        file_id = str(uuid.uuid4())

        # ---------------- VIP FLOW: store in Supabase + DB ----------------
        if is_vip_bool:
            try:
                file_path = f"vip/{user_id}/{file_id}.wav"
                print(f"☁️ Uploading to Supabase path: {file_path}")

                # Upload to Supabase Storage bucket "music"
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

                creation_title = title or f"Creation {int(time.time())}"
                creation_data = {
                    "user_id": user_id,
                    "title": creation_title,
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
                    creation_row = db_result.data[0]
                    return {
                        "creation_id": creation_row["id"],
                        "file_url": cloud_url,
                        "title": creation_title,
                        "storage": "cloud",
                    }
                else:
                    print("❌ No data returned from Supabase user_creations insert")
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to store creation in database",
                    )

            except Exception as e:
                print(f"❌ Cloud upload failed: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Cloud upload failed: {str(e)}")

        # ---------------- FREE FLOW: local temp file ----------------
        local_file_path = uploads_dir / f"{file_id}_temp.wav"
        with open(local_file_path, "wb") as f:
            f.write(combined_data)

        temp_url = f"{BASE_URL}/files/{file_id}_temp.wav"
        print(f"💾 Stored temporary file at: {local_file_path}")
        print(f"   Accessible at: {temp_url}")

        return {
            "temp_url": temp_url,
            "expires_in": 86400,
            "storage": "local",
            "message": "File will be deleted after 24 hours. Upgrade to VIP to save permanently.",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Audio upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio upload failed: {str(e)}")


# ---------------------------------------------------
# BACKEND COMBINE (PLATINUM FEATURE)
# ---------------------------------------------------
@app.post("/api/platinum/backend-combine")
async def combine_audio(
    voice_file: UploadFile = File(...),
    music_id: str = None,
    user_id: str = None,
    is_vip: str = "false",
    title: str = None,
):
    """
    Combine voice recording with AI music (VIP backend processing).

    For now: mock combination – just saves the voice as combined file.
    """
    try:
        # Convert string to boolean
        is_vip_bool = is_vip.lower() in ("true", "1", "yes")

        print("📥 /api/audio/combine called")
        print(f"   music_id = {music_id}")
        print(f"   user_id  = {user_id}")
        print(f"   is_vip   = {is_vip} -> {is_vip_bool}")
        print(f"   title    = {title}")
        print(f"   filename = {voice_file.filename}")

        if not music_id:
            raise HTTPException(status_code=400, detail="music_id is required")

        voice_data = await voice_file.read()
        if not voice_data:
            raise HTTPException(status_code=400, detail="Empty voice_file")

        combined_file_id = str(uuid.uuid4())
        combined_file_name = f"{combined_file_id}_combined.wav"
        combined_file_path = uploads_dir / combined_file_name

        # TODO: real audio mixing in production
        with open(combined_file_path, "wb") as f:
            f.write(voice_data)

        file_url = f"{BASE_URL}/files/{combined_file_name}"
        print(f"🎛 Combined file stored at {combined_file_path}")
        print(f"   URL: {file_url}")

        # VIP: store in DB
        if is_vip_bool and user_id:
            creation_title = title or f"Creation {int(time.time())}"
            creation_data = {
                "user_id": user_id,
                "title": creation_title,
                "voice_url": None,
                "combined_url": file_url,
                "music_id": music_id,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            print("🗄 Inserting VIP creation:", creation_data)

            result = (
                music_service.supabase
                .from_("user_creations")
                .insert(creation_data)
                .execute()
            )
            print("   Supabase insert result:", result)

            if getattr(result, "data", None):
                creation_id = result.data[0]["id"]
                return {
                    "creation_id": creation_id,
                    "file_url": file_url,
                    "title": creation_title,
                }
            else:
                print("❌ No data returned from Supabase on VIP insert")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to store creation in database",
                )

        # Free users: just return temporary URL
        return {
            "temp_url": file_url,
            "expires_in": 86400,
            "message": "File will be deleted after 24 hours. Upgrade to VIP to save permanently.",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Audio combination failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio combination failed: {str(e)}")


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
                id=item["id"],
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
            .eq("id", creation_id)
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
