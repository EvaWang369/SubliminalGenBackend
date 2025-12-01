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
# BACKEND COMBINE (PLATINUM FEATURE) - FFMPEG VERSION
# DEPRECATED: Complex mixing approach - kept for reference
# ---------------------------------------------------
# @app.post("/api/platinum/backend-combine")
async def combine_audio(
    voice_file: UploadFile = File(...),
    music_id: str = Form(...),
    user_id: str = Form(...),
    is_vip: str = Form("false"),
    title: str = Form(None),
    duration: int = Form(None),
):
    """
    Combine voice recording with AI music using ffmpeg (streaming, low-RAM).

    Flow:
    - Download music from Supabase by music_id
    - Save both voice + music to temp WAV files
    - Use ffmpeg to:
        - loop both inputs with -stream_loop -1
        - apply volumes (voice ~0.8, music ~0.4)
        - stop at target duration (-t)
    - VIP: upload final file to Supabase + user_creations
    - Free: store as temp local file and return temp_url
    """
    try:
        # Convert string to boolean
        is_vip_bool = is_vip.lower() in ("true", "1", "yes")

        print("\n" + "="*60)
        print("🚀 PLATINUM BACKEND-COMBINE STARTED")
        print("="*60)
        print(f"📥 Request Details:")
        print(f"   music_id = {music_id}")
        print(f"   user_id  = {user_id}")
        print(f"   is_vip   = {is_vip} -> {is_vip_bool}")
        print(f"   title    = {title}")
        print(f"   filename = {voice_file.filename}")
        print(f"   duration = {duration}s")

        if not music_id:
            print("❌ STEP 1 FAILED: music_id is required")
            raise HTTPException(status_code=400, detail="music_id is required")

        # ------------------------------------------------------------------
        # 1) Read voice file into bytes (short, user recording)
        # ------------------------------------------------------------------
        print("\n🎤 STEP 1: Reading voice file...")
        voice_data = await voice_file.read()
        if not voice_data:
            print("❌ STEP 1 FAILED: Empty voice file")
            raise HTTPException(status_code=400, detail="Empty voice_file")
        
        print(f"✅ STEP 1 SUCCESS: Voice file read ({len(voice_data)} bytes)")
        combined_file_id = str(uuid.uuid4())
        print(f"🆔 Generated combined_file_id: {combined_file_id}")

        # ------------------------------------------------------------------
        # 2) Fetch music track from Supabase
        # ------------------------------------------------------------------
        print("\n🎵 STEP 2: Fetching music track from database...")
        print(f"   Looking for music_id: {music_id}")
        
        music_result = (
            music_service.supabase
            .from_("music")
            .select("*")
            .eq("uuid", music_id)
            .execute()
        )

        if not music_result.data:
            print(f"❌ STEP 2 FAILED: Music track {music_id} not found in database")
            raise HTTPException(status_code=404, detail=f"Music track {music_id} not found")

        music_track = music_result.data[0]
        music_url = music_track["supabase_url"]
        print(f"✅ STEP 2 SUCCESS: Found music track")
        print(f"   Title: {music_track['title']}")
        print(f"   URL: {music_url}")

        # Download music file from Supabase Storage
        music_path_in_bucket = music_url.split("/music/")[-1]  # Extract path from URL
        print(f"\n📥 STEP 3: Downloading music file...")
        print(f"   Bucket path: {music_path_in_bucket}")

        try:
            music_data = music_service.supabase.storage.from_("music").download(music_path_in_bucket)
            print(f"✅ STEP 3 SUCCESS: Music downloaded ({len(music_data)} bytes)")
        except Exception as e:
            print(f"❌ STEP 3 FAILED: Music download error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to download music: {str(e)}")

        # ------------------------------------------------------------------
        # 4) Write both inputs to temporary WAV files
        # ------------------------------------------------------------------
        print("\n📝 STEP 4: Creating temporary files...")
        # NOTE: We keep these files small (original lengths), ffmpeg handles looping
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as voice_tmp:
            voice_tmp_path = Path(voice_tmp.name)
            voice_tmp.write(voice_data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as music_tmp:
            music_tmp_path = Path(music_tmp.name)
            music_tmp.write(music_data)

        print(f"✅ STEP 4 SUCCESS: Temporary files created")
        print(f"   Voice temp: {voice_tmp_path}")
        print(f"   Music temp: {music_tmp_path}")

        # ------------------------------------------------------------------
        # 5) Decide final target duration (seconds) - OPTIMIZED FOR LOW RESOURCES
        # ------------------------------------------------------------------
        print("\n🎛️ STEP 5: Setting target duration...")
        final_duration = duration if duration else 300  # default 5min for Render compatibility
        
        # Smart limits based on environment capabilities
        import os
        is_render = os.getenv('RENDER') is not None
        is_cloud_run = os.getenv('K_SERVICE') is not None  # Cloud Run detection
        
        if is_render:
            max_allowed = 600  # 10 minutes max on Render (limited resources)
            print("🔧 Render environment detected - applying resource limits")
        elif is_cloud_run:
            max_allowed = 3600  # 60 minutes max on Cloud Run (powerful resources)
            print("☁️ Google Cloud Run detected - high performance mode")
        else:
            max_allowed = 4 * 3600  # 4 hours for local/powerful servers
            
        if final_duration > max_allowed:
            print(f"⚠️ Duration clamped: {final_duration}s -> {max_allowed}s (resource limit)")
            final_duration = max_allowed

        print(f"✅ STEP 5 SUCCESS: Target duration set")
        print(f"   Duration: {final_duration}s ({final_duration//60}min {final_duration%60}s)")
        env_name = 'Render (limited)' if is_render else 'Cloud Run (powerful)' if is_cloud_run else 'Local/Server'
        print(f"   Environment: {env_name}")

        # ------------------------------------------------------------------
        # 6) Use ffmpeg to loop + mix both streams into final WAV
        # ------------------------------------------------------------------
        print("\n🎬 STEP 6: Starting FFmpeg audio processing...")
        # Output file (in temp first)
        output_tmp_path = Path(tempfile.gettempdir()) / f"platinum_mix_{combined_file_id}.wav"
        print(f"   Output path: {output_tmp_path}")
        
        # Memory management based on environment
        if is_render and final_duration > 300:
            print("   Using memory-efficient mode for Render")
        elif is_cloud_run:
            print("   Using high-performance mode for Cloud Run")
        else:
            print("   Using standard processing mode")

        # Resource-optimized FFmpeg with high quality audio:
        # - Keep high quality for subliminal content
        # - Optimize memory usage and processing
        base_cmd = [
            "ffmpeg",
            "-y",                         # overwrite
            "-stream_loop", "-1", "-i", str(music_tmp_path),  # loop music
            "-stream_loop", "-1", "-i", str(voice_tmp_path),  # loop voice
            "-filter_complex",
            "[0:a]volume=0.4[a0];"
            "[1:a]volume=0.8[a1];"
            "[a0][a1]amix=inputs=2:normalize=0[aout]",
            "-map", "[aout]",
            "-ac", "2",                   # stereo (keep quality)
            "-ar", "44100",               # 44.1kHz (keep quality)
            "-threads", "1",              # single thread (predictable memory)
            "-t", str(final_duration),    # stop at target duration
        ]
        
        # Environment-specific optimizations
        if is_render:
            # Render: Memory-constrained optimizations
            ffmpeg_cmd = base_cmd + [
                "-preset", "ultrafast",       # fastest encoding
                "-bufsize", "64k",            # smaller buffer
                "-maxrate", "320k",           # limit bitrate spikes
                str(output_tmp_path),
            ]
        elif is_cloud_run:
            # Cloud Run: High-performance optimizations
            ffmpeg_cmd = base_cmd + [
                "-threads", "2",              # use both vCPUs
                "-preset", "fast",            # balanced speed/quality
                str(output_tmp_path),
            ]
        else:
            # Local: No restrictions
            ffmpeg_cmd = base_cmd + [str(output_tmp_path)]

        print("   FFmpeg command:")
        print(f"   {' '.join(ffmpeg_cmd)}")
        print("   Processing... (this may take a moment)")

        try:
            # Environment-specific timeouts
            if is_render:
                timeout_seconds = min(final_duration * 2 + 120, 900)  # Max 15min timeout on Render
            elif is_cloud_run:
                timeout_seconds = min(final_duration * 1.5 + 60, 3600)  # Max 60min timeout on Cloud Run
            else:
                timeout_seconds = final_duration * 3 + 60  # 3x duration + 1min buffer locally
            print(f"   FFmpeg timeout: {timeout_seconds}s")
            
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=timeout_seconds,  # Prevent hanging processes
            )
            print("✅ STEP 6 SUCCESS: FFmpeg processing completed")
            if result.stderr:
                # ffmpeg logs a lot on stderr; keep for debugging
                stderr_output = result.stderr.decode("utf-8", errors="ignore")
                print("   FFmpeg stderr output:")
                # Only show last few lines to avoid spam
                stderr_lines = stderr_output.strip().split('\n')
                for line in stderr_lines[-5:]:
                    if line.strip():
                        print(f"   {line}")
        except subprocess.TimeoutExpired as e:
            print("❌ STEP 6 FAILED: FFmpeg timeout (resource limit exceeded)")
            print(f"   Timeout after {timeout_seconds}s")
            if is_render:
                print("   Render free tier limit reached - try duration ≤5min or upgrade plan")
                raise HTTPException(status_code=500, detail="Processing timeout on free tier - try shorter duration (≤5min) or upgrade to paid plan")
            elif is_cloud_run:
                print("   Cloud Run timeout - try shorter duration or check request limits")
                raise HTTPException(status_code=500, detail=f"Processing timeout on Cloud Run after {timeout_seconds}s")
            else:
                print("   Try shorter duration or check system resources")
                raise HTTPException(status_code=500, detail=f"Audio processing timeout after {timeout_seconds}s")
        except subprocess.CalledProcessError as e:
            print("❌ STEP 6 FAILED: FFmpeg processing error")
            stderr_output = e.stderr.decode("utf-8", errors="ignore")
            print("   FFmpeg error output:")
            for line in stderr_output.strip().split('\n')[-10:]:
                if line.strip():
                    print(f"   {line}")
            raise HTTPException(status_code=500, detail="Audio processing failed via ffmpeg")

        # Read final output into memory for upload / file save
        print("\n📊 STEP 7: Reading final output...")
        if not output_tmp_path.exists():
            print("❌ STEP 7 FAILED: FFmpeg did not produce output file")
            raise HTTPException(status_code=500, detail="ffmpeg did not produce output file")

        combined_data = output_tmp_path.read_bytes()
        file_size_mb = len(combined_data) / (1024 * 1024)
        print(f"✅ STEP 7 SUCCESS: Final mix ready")
        print(f"   File size: {len(combined_data)} bytes ({file_size_mb:.1f} MB)")

        # Clean up temp input files (keep output until after upload)
        print("\n🧹 STEP 8: Cleaning up temporary input files...")
        try:
            if voice_tmp_path.exists():
                voice_tmp_path.unlink()
                print("   ✅ Voice temp file deleted")
            if music_tmp_path.exists():
                music_tmp_path.unlink()
                print("   ✅ Music temp file deleted")
            print("✅ STEP 8 SUCCESS: Temp input files cleaned up")
        except Exception as cleanup_err:
            print(f"⚠️ STEP 8 WARNING: Temp input cleanup error (non-fatal): {cleanup_err}")

        # ------------------------------------------------------------------
        # 9) VIP FLOW: upload to Supabase + DB
        # ------------------------------------------------------------------
        if is_vip_bool and user_id:
            print("\n☁️ STEP 9: VIP FLOW - Uploading to cloud storage...")
            try:
                file_path = f"vip/{user_id}/{combined_file_id}.wav"
                print(f"   Cloud path: {file_path}")
                print(f"   Uploading {file_size_mb:.1f} MB to Supabase...")

                upload_result = music_service.supabase.storage.from_("music").upload(
                    file_path,
                    combined_data,
                    {"content-type": "audio/wav"},
                )
                print(f"   ✅ Upload successful: {upload_result}")

                # Get public URL
                cloud_url = music_service.supabase.storage.from_("music").get_public_url(
                    file_path
                )
                print(f"   📎 Public URL: {cloud_url}")

                creation_title = title or f"Creation {int(time.time())}"
                creation_data = {
                    "user_id": user_id,
                    "title": creation_title,
                    "voice_url": None,
                    "combined_url": cloud_url,
                    "music_id": music_id,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }

                print("\n🗄️ STEP 10: Saving to database...")
                print(f"   Creation data: {creation_data}")

                db_result = (
                    music_service.supabase
                    .from_("user_creations")
                    .insert(creation_data)
                    .execute()
                )
                print(f"   ✅ Database insert successful: {db_result}")

                # Cleanup output temp file after upload
                print("\n🧹 STEP 11: Final cleanup...")
                try:
                    if output_tmp_path.exists():
                        output_tmp_path.unlink()
                        print("   ✅ Output temp file deleted")
                except Exception as cleanup_err:
                    print(f"   ⚠️ Temp output cleanup error (non-fatal): {cleanup_err}")

                if getattr(db_result, "data", None):
                    creation_row = db_result.data[0]
                    print("\n" + "="*60)
                    print("🎉 PLATINUM BACKEND-COMBINE COMPLETED SUCCESSFULLY (VIP)")
                    print("="*60)
                    print(f"✅ Creation ID: {creation_row['id']}")
                    print(f"✅ File URL: {cloud_url}")
                    print(f"✅ Title: {creation_title}")
                    print(f"✅ Duration: {final_duration}s")
                    print(f"✅ Storage: Cloud (VIP)")
                    print("="*60)
                    return {
                        "creation_id": creation_row["id"],
                        "file_url": cloud_url,
                        "title": creation_title,
                        "storage": "cloud",
                        "duration": final_duration,
                    }
                else:
                    print("❌ STEP 10 FAILED: No data returned from database insert")
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to store creation in database",
                    )

            except HTTPException:
                # Don't swallow HTTPException
                raise
            except Exception as e:
                print(f"❌ STEP 9-10 FAILED: Cloud upload/database error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Cloud upload failed: {str(e)}")

        # ------------------------------------------------------------------
        # 9) FREE FLOW: save temp file locally, return temp_url
        # ------------------------------------------------------------------
        print("\n💾 STEP 9: FREE FLOW - Saving to local storage...")
        combined_file_name = f"{combined_file_id}_temp.wav"
        combined_file_path = uploads_dir / combined_file_name
        print(f"   Local path: {combined_file_path}")

        with open(combined_file_path, "wb") as f:
            f.write(combined_data)
        print(f"   ✅ File saved locally ({file_size_mb:.1f} MB)")

        # Cleanup temp output file after copying
        print("\n🧹 STEP 10: Final cleanup...")
        try:
            if output_tmp_path.exists():
                output_tmp_path.unlink()
                print("   ✅ Output temp file deleted")
        except Exception as cleanup_err:
            print(f"   ⚠️ Temp output cleanup error (non-fatal): {cleanup_err}")

        temp_url = f"{BASE_URL}/files/{combined_file_name}"
        
        print("\n" + "="*60)
        print("🎉 PLATINUM BACKEND-COMBINE COMPLETED SUCCESSFULLY (FREE)")
        print("="*60)
        print(f"✅ Temp URL: {temp_url}")
        print(f"✅ Duration: {final_duration}s")
        print(f"✅ Storage: Local (24h expiry)")
        print(f"✅ File size: {file_size_mb:.1f} MB")
        print("="*60)

        return {
            "temp_url": temp_url,
            "expires_in": 86400,
            "storage": "local",
            "duration": final_duration,
            "message": "File will be deleted after 24 hours. Upgrade to VIP to save permanently.",
        }

    except HTTPException:
        raise
    except Exception as e:
        print("\n" + "="*60)
        print("💥 PLATINUM BACKEND-COMBINE FAILED")
        print("="*60)
        print(f"❌ Error: {str(e)}")
        print("="*60)
        raise HTTPException(status_code=500, detail=f"Audio combination failed: {str(e)}")


# ---------------------------------------------------
# EXTEND AUDIO (NEW PLATINUM FEATURE) - SIMPLE LOOP APPROACH
# ---------------------------------------------------
@app.post("/api/platinum/extend-audio")
async def extend_audio(
    combined_file: UploadFile = File(...),
    loops: int = Form(...),
    target_duration_label: str = Form(...),
    user_id: str = Form(...),
    is_vip: str = Form("false"),
    title: str = Form(None),
):
    """
    Extend pre-mixed audio by looping with fade in/out.
    
    New approach:
    1. iOS pre-mixes voice + music (30s-5min)
    2. Backend applies fade in/out to input
    3. Backend loops the faded version
    4. Return extended audio (~10min, ~15min, ~30min)
    
    Much faster than complex mixing!
    """
    try:
        is_vip_bool = is_vip.lower() in ("true", "1", "yes")
        
        print("\n" + "="*60)
        print("🚀 PLATINUM EXTEND-AUDIO STARTED")
        print("="*60)
        print(f"📥 Request Details:")
        print(f"   user_id = {user_id}")
        print(f"   is_vip = {is_vip} -> {is_vip_bool}")
        print(f"   title = {title}")
        print(f"   filename = {combined_file.filename}")
        print(f"   loops = {loops}")
        print(f"   target_label = {target_duration_label}")
        
        if loops < 1:
            print("❌ VALIDATION FAILED: loops must be >= 1")
            raise HTTPException(status_code=400, detail="loops must be >= 1")
            
        # ------------------------------------------------------------------
        # 1) Read pre-mixed file from iOS
        # ------------------------------------------------------------------
        print("\n🎧 STEP 1: Reading pre-mixed audio file...")
        combined_data = await combined_file.read()
        if not combined_data:
            print("❌ STEP 1 FAILED: Empty combined_file")
            raise HTTPException(status_code=400, detail="Empty combined_file")
            
        print(f"✅ STEP 1 SUCCESS: Pre-mixed file read ({len(combined_data)} bytes)")
        extended_file_id = str(uuid.uuid4())
        print(f"🆔 Generated extended_file_id: {extended_file_id}")
        
        # ------------------------------------------------------------------
        # 2) Save input to temporary file
        # ------------------------------------------------------------------
        print("\n📝 STEP 2: Creating temporary input file...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as input_tmp:
            input_tmp_path = Path(input_tmp.name)
            input_tmp.write(combined_data)
            
        print(f"✅ STEP 2 SUCCESS: Input temp file created")
        print(f"   Path: {input_tmp_path}")
        
        # ------------------------------------------------------------------
        # 3) Get input duration for fade calculation
        # ------------------------------------------------------------------
        print("\n🔍 STEP 3: Analyzing input duration...")
        try:
            probe_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(input_tmp_path)]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            input_duration = float(result.stdout.strip())
            print(f"✅ STEP 3 SUCCESS: Input duration = {input_duration:.1f}s ({input_duration//60:.0f}min {input_duration%60:.0f}s)")
        except Exception as e:
            print(f"❌ STEP 3 FAILED: Could not analyze input duration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Could not analyze input duration: {str(e)}")
            
        # ------------------------------------------------------------------
        # 4) Apply fade in/out to input file
        # ------------------------------------------------------------------
        print("\n🌊 STEP 4: Applying fade in/out...")
        faded_tmp_path = Path(tempfile.gettempdir()) / f"faded_{extended_file_id}.wav"
        
        fade_duration = 2  # 2 second fades (optimal for meditation)
        fade_out_start = max(0, input_duration - fade_duration)
        
        fade_cmd = [
            "ffmpeg", "-y",
            "-i", str(input_tmp_path),
            "-filter_complex",
            f"[0:a]afade=t=in:ss=0:d={fade_duration},afade=t=out:st={fade_out_start}:d={fade_duration}[faded]",
            "-map", "[faded]",
            "-ac", "2",  # stereo
            "-ar", "44100",  # 44.1kHz
            str(faded_tmp_path)
        ]
        
        print(f"   Fade in: 0-{fade_duration}s")
        print(f"   Fade out: {fade_out_start:.1f}-{input_duration:.1f}s")
        print("   Running fade command...")
        
        try:
            result = subprocess.run(fade_cmd, capture_output=True, check=True, timeout=60)
            print("✅ STEP 4 SUCCESS: Fade in/out applied")
        except subprocess.CalledProcessError as e:
            print("❌ STEP 4 FAILED: Fade processing error")
            print(f"   Error: {e.stderr.decode('utf-8', errors='ignore')[-200:]}")
            raise HTTPException(status_code=500, detail="Fade processing failed")
        except subprocess.TimeoutExpired:
            print("❌ STEP 4 FAILED: Fade processing timeout")
            raise HTTPException(status_code=500, detail="Fade processing timeout")
            
        # ------------------------------------------------------------------
        # 5) Loop the faded version
        # ------------------------------------------------------------------
        print(f"\n🔁 STEP 5: Looping faded audio {loops} times...")
        output_tmp_path = Path(tempfile.gettempdir()) / f"extended_{extended_file_id}.wav"
        
        loop_cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops - 1),  # -1 because original counts as first loop
            "-i", str(faded_tmp_path),
            "-c", "copy",  # copy without re-encoding for speed
            str(output_tmp_path)
        ]
        
        print(f"   Total loops: {loops}")
        print(f"   Expected duration: ~{input_duration * loops:.0f}s ({(input_duration * loops)//60:.0f}min {(input_duration * loops)%60:.0f}s)")
        print("   Running loop command...")
        
        try:
            result = subprocess.run(loop_cmd, capture_output=True, check=True, timeout=120)
            print("✅ STEP 5 SUCCESS: Audio looping completed")
        except subprocess.CalledProcessError as e:
            print("❌ STEP 5 FAILED: Loop processing error")
            print(f"   Error: {e.stderr.decode('utf-8', errors='ignore')[-200:]}")
            raise HTTPException(status_code=500, detail="Loop processing failed")
        except subprocess.TimeoutExpired:
            print("❌ STEP 5 FAILED: Loop processing timeout")
            raise HTTPException(status_code=500, detail="Loop processing timeout")
            
        # ------------------------------------------------------------------
        # 6) Read final output
        # ------------------------------------------------------------------
        print("\n📊 STEP 6: Reading final output...")
        if not output_tmp_path.exists():
            print("❌ STEP 6 FAILED: Output file not created")
            raise HTTPException(status_code=500, detail="Output file not created")
            
        extended_data = output_tmp_path.read_bytes()
        actual_duration = input_duration * loops
        file_size_mb = len(extended_data) / (1024 * 1024)
        
        print(f"✅ STEP 6 SUCCESS: Final output ready")
        print(f"   File size: {len(extended_data)} bytes ({file_size_mb:.1f} MB)")
        print(f"   Actual duration: {actual_duration:.0f}s ({actual_duration//60:.0f}min {actual_duration%60:.0f}s)")
        
        # ------------------------------------------------------------------
        # 7) Cleanup temp files
        # ------------------------------------------------------------------
        print("\n🧹 STEP 7: Cleaning up temporary files...")
        try:
            if input_tmp_path.exists():
                input_tmp_path.unlink()
                print("   ✅ Input temp file deleted")
            if faded_tmp_path.exists():
                faded_tmp_path.unlink()
                print("   ✅ Faded temp file deleted")
        except Exception as cleanup_err:
            print(f"   ⚠️ Temp cleanup warning (non-fatal): {cleanup_err}")
            
        # ------------------------------------------------------------------
        # 8) VIP FLOW: Upload to Supabase + DB
        # ------------------------------------------------------------------
        if is_vip_bool and user_id:
            print("\n☁️ STEP 8: VIP FLOW - Uploading to cloud storage...")
            try:
                file_path = f"vip/{user_id}/{extended_file_id}.wav"
                print(f"   Cloud path: {file_path}")
                print(f"   Uploading {file_size_mb:.1f} MB to Supabase...")
                
                upload_result = music_service.supabase.storage.from_("music").upload(
                    file_path,
                    extended_data,
                    {"content-type": "audio/wav"},
                )
                print(f"   ✅ Upload successful")
                
                cloud_url = music_service.supabase.storage.from_("music").get_public_url(file_path)
                print(f"   🔗 Public URL: {cloud_url}")
                
                creation_title = title or f"Extended {target_duration_label} Session"
                creation_data = {
                    "user_id": user_id,
                    "title": creation_title,
                    "voice_url": None,
                    "combined_url": cloud_url,
                    "music_id": None,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                
                print("\n🗄️ STEP 9: Saving to database...")
                db_result = (
                    music_service.supabase
                    .from_("user_creations")
                    .insert(creation_data)
                    .execute()
                )
                print(f"   ✅ Database insert successful")
                
                # Cleanup output temp file after upload
                try:
                    if output_tmp_path.exists():
                        output_tmp_path.unlink()
                        print("   ✅ Output temp file deleted")
                except Exception as cleanup_err:
                    print(f"   ⚠️ Output cleanup warning: {cleanup_err}")
                    
                if getattr(db_result, "data", None):
                    creation_row = db_result.data[0]
                    print("\n" + "="*60)
                    print("🎉 PLATINUM EXTEND-AUDIO COMPLETED SUCCESSFULLY (VIP)")
                    print("="*60)
                    print(f"✅ Creation ID: {creation_row['id']}")
                    print(f"✅ File URL: {cloud_url}")
                    print(f"✅ Title: {creation_title}")
                    print(f"✅ Actual Duration: {actual_duration:.0f}s")
                    print(f"✅ Target Label: {target_duration_label}")
                    print(f"✅ Loops Applied: {loops}")
                    print(f"✅ Storage: Cloud (VIP)")
                    print("="*60)
                    return {
                        "creation_id": creation_row["id"],
                        "file_url": cloud_url,
                        "title": creation_title,
                        "actual_duration": int(actual_duration),
                        "target_label": target_duration_label,
                        "loops_applied": loops,
                        "storage": "cloud",
                        "user_id": user_id,
                        "file_id": extended_file_id,
                    }
                else:
                    print("❌ STEP 9 FAILED: No data returned from database")
                    raise HTTPException(status_code=500, detail="Failed to store creation in database")
                    
            except HTTPException:
                raise
            except Exception as e:
                print(f"❌ STEP 8-9 FAILED: Cloud upload/database error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Cloud upload failed: {str(e)}")
                
        # ------------------------------------------------------------------
        # 8) FREE FLOW: Save locally
        # ------------------------------------------------------------------
        print("\n💾 STEP 8: FREE FLOW - Saving to local storage...")
        extended_file_name = f"{extended_file_id}_temp.wav"
        extended_file_path = uploads_dir / extended_file_name
        
        with open(extended_file_path, "wb") as f:
            f.write(extended_data)
        print(f"   ✅ File saved locally ({file_size_mb:.1f} MB)")
        
        # Cleanup output temp file after copying
        try:
            if output_tmp_path.exists():
                output_tmp_path.unlink()
                print("   ✅ Output temp file deleted")
        except Exception as cleanup_err:
            print(f"   ⚠️ Output cleanup warning: {cleanup_err}")
            
        temp_url = f"{BASE_URL}/files/{extended_file_name}"
        
        print("\n" + "="*60)
        print("🎉 PLATINUM EXTEND-AUDIO COMPLETED SUCCESSFULLY (FREE)")
        print("="*60)
        print(f"✅ Temp URL: {temp_url}")
        print(f"✅ Actual Duration: {actual_duration:.0f}s")
        print(f"✅ Target Label: {target_duration_label}")
        print(f"✅ Loops Applied: {loops}")
        print(f"✅ File Size: {file_size_mb:.1f} MB")
        print(f"✅ Storage: Local (24h expiry)")
        print("="*60)
        
        return {
            "temp_url": temp_url,
            "expires_in": 86400,
            "actual_duration": int(actual_duration),
            "target_label": target_duration_label,
            "loops_applied": loops,
            "storage": "local",
            "user_id": user_id,
            "file_id": extended_file_id,
            "message": "File will be deleted after 24 hours. Upgrade to VIP to save permanently.",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print("\n" + "="*60)
        print("💥 PLATINUM EXTEND-AUDIO FAILED")
        print("="*60)
        print(f"❌ Error: {str(e)}")
        print("="*60)
        raise HTTPException(status_code=500, detail=f"Audio extension failed: {str(e)}")


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
