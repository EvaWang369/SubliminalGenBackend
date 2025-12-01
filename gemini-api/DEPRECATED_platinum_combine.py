# # ---------------------------------------------------
# # BACKEND COMBINE (PLATINUM FEATURE) - FFMPEG VERSION
# # DEPRECATED: Complex mixing approach - kept for reference
# # ---------------------------------------------------
# # @app.post("/api/platinum/backend-combine")
# async def combine_audio(
#         voice_file: UploadFile = File(...),
#         music_id: str = Form(...),
#         user_id: str = Form(...),
#         is_vip: str = Form("false"),
#         title: str = Form(None),
#         duration: int = Form(None),
# ):
#     """
#     Combine voice recording with AI music using ffmpeg (streaming, low-RAM).
#
#     Flow:
#     - Download music from Supabase by music_id
#     - Save both voice + music to temp WAV files
#     - Use ffmpeg to:
#         - loop both inputs with -stream_loop -1
#         - apply volumes (voice ~0.8, music ~0.4)
#         - stop at target duration (-t)
#     - VIP: upload final file to Supabase + user_creations
#     - Free: store as temp local file and return temp_url
#     """
#     try:
#         # Convert string to boolean
#         is_vip_bool = is_vip.lower() in ("true", "1", "yes")
#
#         print("\n" + "=" * 60)
#         print("🚀 PLATINUM BACKEND-COMBINE STARTED")
#         print("=" * 60)
#         print(f"📥 Request Details:")
#         print(f"   music_id = {music_id}")
#         print(f"   user_id  = {user_id}")
#         print(f"   is_vip   = {is_vip} -> {is_vip_bool}")
#         print(f"   title    = {title}")
#         print(f"   filename = {voice_file.filename}")
#         print(f"   duration = {duration}s")
#
#         if not music_id:
#             print("❌ STEP 1 FAILED: music_id is required")
#             raise HTTPException(status_code=400, detail="music_id is required")
#
#         # ------------------------------------------------------------------
#         # 1) Read voice file into bytes (short, user recording)
#         # ------------------------------------------------------------------
#         print("\n🎤 STEP 1: Reading voice file...")
#         voice_data = await voice_file.read()
#         if not voice_data:
#             print("❌ STEP 1 FAILED: Empty voice file")
#             raise HTTPException(status_code=400, detail="Empty voice_file")
#
#         print(f"✅ STEP 1 SUCCESS: Voice file read ({len(voice_data)} bytes)")
#         combined_file_id = str(uuid.uuid4())
#         print(f"🆔 Generated combined_file_id: {combined_file_id}")
#
#         # ------------------------------------------------------------------
#         # 2) Fetch music track from Supabase
#         # ------------------------------------------------------------------
#         print("\n🎵 STEP 2: Fetching music track from database...")
#         print(f"   Looking for music_id: {music_id}")
#
#         music_result = (
#             music_service.supabase
#             .from_("music")
#             .select("*")
#             .eq("uuid", music_id)
#             .execute()
#         )
#
#         if not music_result.data:
#             print(f"❌ STEP 2 FAILED: Music track {music_id} not found in database")
#             raise HTTPException(status_code=404, detail=f"Music track {music_id} not found")
#
#         music_track = music_result.data[0]
#         music_url = music_track["supabase_url"]
#         print(f"✅ STEP 2 SUCCESS: Found music track")
#         print(f"   Title: {music_track['title']}")
#         print(f"   URL: {music_url}")
#
#         # Download music file from Supabase Storage
#         music_path_in_bucket = music_url.split("/music/")[-1]  # Extract path from URL
#         print(f"\n📥 STEP 3: Downloading music file...")
#         print(f"   Bucket path: {music_path_in_bucket}")
#
#         try:
#             music_data = music_service.supabase.storage.from_("music").download(music_path_in_bucket)
#             print(f"✅ STEP 3 SUCCESS: Music downloaded ({len(music_data)} bytes)")
#         except Exception as e:
#             print(f"❌ STEP 3 FAILED: Music download error: {str(e)}")
#             raise HTTPException(status_code=500, detail=f"Failed to download music: {str(e)}")
#
#         # ------------------------------------------------------------------
#         # 4) Write both inputs to temporary WAV files
#         # ------------------------------------------------------------------
#         print("\n📝 STEP 4: Creating temporary files...")
#         # NOTE: We keep these files small (original lengths), ffmpeg handles looping
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as voice_tmp:
#             voice_tmp_path = Path(voice_tmp.name)
#             voice_tmp.write(voice_data)
#
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as music_tmp:
#             music_tmp_path = Path(music_tmp.name)
#             music_tmp.write(music_data)
#
#         print(f"✅ STEP 4 SUCCESS: Temporary files created")
#         print(f"   Voice temp: {voice_tmp_path}")
#         print(f"   Music temp: {music_tmp_path}")
#
#         # ------------------------------------------------------------------
#         # 5) Decide final target duration (seconds) - OPTIMIZED FOR LOW RESOURCES
#         # ------------------------------------------------------------------
#         print("\n🎛️ STEP 5: Setting target duration...")
#         final_duration = duration if duration else 300  # default 5min for Render compatibility
#
#         # Smart limits based on environment capabilities
#         import os
#         is_render = os.getenv('RENDER') is not None
#         is_cloud_run = os.getenv('K_SERVICE') is not None  # Cloud Run detection
#
#         if is_render:
#             max_allowed = 600  # 10 minutes max on Render (limited resources)
#             print("🔧 Render environment detected - applying resource limits")
#         elif is_cloud_run:
#             max_allowed = 3600  # 60 minutes max on Cloud Run (powerful resources)
#             print("☁️ Google Cloud Run detected - high performance mode")
#         else:
#             max_allowed = 4 * 3600  # 4 hours for local/powerful servers
#
#         if final_duration > max_allowed:
#             print(f"⚠️ Duration clamped: {final_duration}s -> {max_allowed}s (resource limit)")
#             final_duration = max_allowed
#
#         print(f"✅ STEP 5 SUCCESS: Target duration set")
#         print(f"   Duration: {final_duration}s ({final_duration // 60}min {final_duration % 60}s)")
#         env_name = 'Render (limited)' if is_render else 'Cloud Run (powerful)' if is_cloud_run else 'Local/Server'
#         print(f"   Environment: {env_name}")
#
#         # ------------------------------------------------------------------
#         # 6) Use ffmpeg to loop + mix both streams into final WAV
#         # ------------------------------------------------------------------
#         print("\n🎬 STEP 6: Starting FFmpeg audio processing...")
#         # Output file (in temp first)
#         output_tmp_path = Path(tempfile.gettempdir()) / f"platinum_mix_{combined_file_id}.wav"
#         print(f"   Output path: {output_tmp_path}")
#
#         # Memory management based on environment
#         if is_render and final_duration > 300:
#             print("   Using memory-efficient mode for Render")
#         elif is_cloud_run:
#             print("   Using high-performance mode for Cloud Run")
#         else:
#             print("   Using standard processing mode")
#
#         # Resource-optimized FFmpeg with high quality audio:
#         # - Keep high quality for subliminal content
#         # - Optimize memory usage and processing
#         base_cmd = [
#             "ffmpeg",
#             "-y",  # overwrite
#             "-stream_loop", "-1", "-i", str(music_tmp_path),  # loop music
#             "-stream_loop", "-1", "-i", str(voice_tmp_path),  # loop voice
#             "-filter_complex",
#             "[0:a]volume=0.4[a0];"
#             "[1:a]volume=0.8[a1];"
#             "[a0][a1]amix=inputs=2:normalize=0[aout]",
#             "-map", "[aout]",
#             "-ac", "2",  # stereo (keep quality)
#             "-ar", "44100",  # 44.1kHz (keep quality)
#             "-threads", "1",  # single thread (predictable memory)
#             "-t", str(final_duration),  # stop at target duration
#         ]
#
#         # Environment-specific optimizations
#         if is_render:
#             # Render: Memory-constrained optimizations
#             ffmpeg_cmd = base_cmd + [
#                 "-preset", "ultrafast",  # fastest encoding
#                 "-bufsize", "64k",  # smaller buffer
#                 "-maxrate", "320k",  # limit bitrate spikes
#                 str(output_tmp_path),
#             ]
#         elif is_cloud_run:
#             # Cloud Run: High-performance optimizations
#             ffmpeg_cmd = base_cmd + [
#                 "-threads", "2",  # use both vCPUs
#                 "-preset", "fast",  # balanced speed/quality
#                 str(output_tmp_path),
#             ]
#         else:
#             # Local: No restrictions
#             ffmpeg_cmd = base_cmd + [str(output_tmp_path)]
#
#         print("   FFmpeg command:")
#         print(f"   {' '.join(ffmpeg_cmd)}")
#         print("   Processing... (this may take a moment)")
#
#         try:
#             # Environment-specific timeouts
#             if is_render:
#                 timeout_seconds = min(final_duration * 2 + 120, 900)  # Max 15min timeout on Render
#             elif is_cloud_run:
#                 timeout_seconds = min(final_duration * 1.5 + 60, 3600)  # Max 60min timeout on Cloud Run
#             else:
#                 timeout_seconds = final_duration * 3 + 60  # 3x duration + 1min buffer locally
#             print(f"   FFmpeg timeout: {timeout_seconds}s")
#
#             result = subprocess.run(
#                 ffmpeg_cmd,
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 check=True,
#                 timeout=timeout_seconds,  # Prevent hanging processes
#             )
#             print("✅ STEP 6 SUCCESS: FFmpeg processing completed")
#             if result.stderr:
#                 # ffmpeg logs a lot on stderr; keep for debugging
#                 stderr_output = result.stderr.decode("utf-8", errors="ignore")
#                 print("   FFmpeg stderr output:")
#                 # Only show last few lines to avoid spam
#                 stderr_lines = stderr_output.strip().split('\n')
#                 for line in stderr_lines[-5:]:
#                     if line.strip():
#                         print(f"   {line}")
#         except subprocess.TimeoutExpired as e:
#             print("❌ STEP 6 FAILED: FFmpeg timeout (resource limit exceeded)")
#             print(f"   Timeout after {timeout_seconds}s")
#             if is_render:
#                 print("   Render free tier limit reached - try duration ≤5min or upgrade plan")
#                 raise HTTPException(status_code=500,
#                                     detail="Processing timeout on free tier - try shorter duration (≤5min) or upgrade to paid plan")
#             elif is_cloud_run:
#                 print("   Cloud Run timeout - try shorter duration or check request limits")
#                 raise HTTPException(status_code=500, detail=f"Processing timeout on Cloud Run after {timeout_seconds}s")
#             else:
#                 print("   Try shorter duration or check system resources")
#                 raise HTTPException(status_code=500, detail=f"Audio processing timeout after {timeout_seconds}s")
#         except subprocess.CalledProcessError as e:
#             print("❌ STEP 6 FAILED: FFmpeg processing error")
#             stderr_output = e.stderr.decode("utf-8", errors="ignore")
#             print("   FFmpeg error output:")
#             for line in stderr_output.strip().split('\n')[-10:]:
#                 if line.strip():
#                     print(f"   {line}")
#             raise HTTPException(status_code=500, detail="Audio processing failed via ffmpeg")
#
#         # Read final output into memory for upload / file save
#         print("\n📊 STEP 7: Reading final output...")
#         if not output_tmp_path.exists():
#             print("❌ STEP 7 FAILED: FFmpeg did not produce output file")
#             raise HTTPException(status_code=500, detail="ffmpeg did not produce output file")
#
#         combined_data = output_tmp_path.read_bytes()
#         file_size_mb = len(combined_data) / (1024 * 1024)
#         print(f"✅ STEP 7 SUCCESS: Final mix ready")
#         print(f"   File size: {len(combined_data)} bytes ({file_size_mb:.1f} MB)")
#
#         # Clean up temp input files (keep output until after upload)
#         print("\n🧹 STEP 8: Cleaning up temporary input files...")
#         try:
#             if voice_tmp_path.exists():
#                 voice_tmp_path.unlink()
#                 print("   ✅ Voice temp file deleted")
#             if music_tmp_path.exists():
#                 music_tmp_path.unlink()
#                 print("   ✅ Music temp file deleted")
#             print("✅ STEP 8 SUCCESS: Temp input files cleaned up")
#         except Exception as cleanup_err:
#             print(f"⚠️ STEP 8 WARNING: Temp input cleanup error (non-fatal): {cleanup_err}")
#
#         # ------------------------------------------------------------------
#         # 9) VIP FLOW: upload to Supabase + DB
#         # ------------------------------------------------------------------
#         if is_vip_bool and user_id:
#             print("\n☁️ STEP 9: VIP FLOW - Uploading to cloud storage...")
#             try:
#                 file_path = f"vip/{user_id}/{combined_file_id}.wav"
#                 print(f"   Cloud path: {file_path}")
#                 print(f"   Uploading {file_size_mb:.1f} MB to Supabase...")
#
#                 upload_result = music_service.supabase.storage.from_("music").upload(
#                     file_path,
#                     combined_data,
#                     {"content-type": "audio/wav"},
#                 )
#                 print(f"   ✅ Upload successful: {upload_result}")
#
#                 # Get public URL
#                 cloud_url = music_service.supabase.storage.from_("music").get_public_url(
#                     file_path
#                 )
#                 print(f"   📎 Public URL: {cloud_url}")
#
#                 creation_title = title or f"Creation {int(time.time())}"
#                 creation_data = {
#                     "user_id": user_id,
#                     "title": creation_title,
#                     "voice_url": None,
#                     "combined_url": cloud_url,
#                     "music_id": music_id,
#                     "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
#                 }
#
#                 print("\n🗄️ STEP 10: Saving to database...")
#                 print(f"   Creation data: {creation_data}")
#
#                 db_result = (
#                     music_service.supabase
#                     .from_("user_creations")
#                     .insert(creation_data)
#                     .execute()
#                 )
#                 print(f"   ✅ Database insert successful: {db_result}")
#
#                 # Cleanup output temp file after upload
#                 print("\n🧹 STEP 11: Final cleanup...")
#                 try:
#                     if output_tmp_path.exists():
#                         output_tmp_path.unlink()
#                         print("   ✅ Output temp file deleted")
#                 except Exception as cleanup_err:
#                     print(f"   ⚠️ Temp output cleanup error (non-fatal): {cleanup_err}")
#
#                 if getattr(db_result, "data", None):
#                     creation_row = db_result.data[0]
#                     print("\n" + "=" * 60)
#                     print("🎉 PLATINUM BACKEND-COMBINE COMPLETED SUCCESSFULLY (VIP)")
#                     print("=" * 60)
#                     print(f"✅ Creation ID: {creation_row['id']}")
#                     print(f"✅ File URL: {cloud_url}")
#                     print(f"✅ Title: {creation_title}")
#                     print(f"✅ Duration: {final_duration}s")
#                     print(f"✅ Storage: Cloud (VIP)")
#                     print("=" * 60)
#                     return {
#                         "creation_id": creation_row["id"],
#                         "file_url": cloud_url,
#                         "title": creation_title,
#                         "storage": "cloud",
#                         "duration": final_duration,
#                     }
#                 else:
#                     print("❌ STEP 10 FAILED: No data returned from database insert")
#                     raise HTTPException(
#                         status_code=500,
#                         detail="Failed to store creation in database",
#                     )
#
#             except HTTPException:
#                 # Don't swallow HTTPException
#                 raise
#             except Exception as e:
#                 print(f"❌ STEP 9-10 FAILED: Cloud upload/database error: {str(e)}")
#                 raise HTTPException(status_code=500, detail=f"Cloud upload failed: {str(e)}")
#
#         # ------------------------------------------------------------------
#         # 9) FREE FLOW: save temp file locally, return temp_url
#         # ------------------------------------------------------------------
#         print("\n💾 STEP 9: FREE FLOW - Saving to local storage...")
#         combined_file_name = f"{combined_file_id}_temp.wav"
#         combined_file_path = uploads_dir / combined_file_name
#         print(f"   Local path: {combined_file_path}")
#
#         with open(combined_file_path, "wb") as f:
#             f.write(combined_data)
#         print(f"   ✅ File saved locally ({file_size_mb:.1f} MB)")
#
#         # Cleanup temp output file after copying
#         print("\n🧹 STEP 10: Final cleanup...")
#         try:
#             if output_tmp_path.exists():
#                 output_tmp_path.unlink()
#                 print("   ✅ Output temp file deleted")
#         except Exception as cleanup_err:
#             print(f"   ⚠️ Temp output cleanup error (non-fatal): {cleanup_err}")
#
#         temp_url = f"{BASE_URL}/files/{combined_file_name}"
#
#         print("\n" + "=" * 60)
#         print("🎉 PLATINUM BACKEND-COMBINE COMPLETED SUCCESSFULLY (FREE)")
#         print("=" * 60)
#         print(f"✅ Temp URL: {temp_url}")
#         print(f"✅ Duration: {final_duration}s")
#         print(f"✅ Storage: Local (24h expiry)")
#         print(f"✅ File size: {file_size_mb:.1f} MB")
#         print("=" * 60)
#
#         return {
#             "temp_url": temp_url,
#             "expires_in": 86400,
#             "storage": "local",
#             "duration": final_duration,
#             "message": "File will be deleted after 24 hours. Upgrade to VIP to save permanently.",
#         }
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         print("\n" + "=" * 60)
#         print("💥 PLATINUM BACKEND-COMBINE FAILED")
#         print("=" * 60)
#         print(f"❌ Error: {str(e)}")
#         print("=" * 60)
#         raise HTTPException(status_code=500, detail=f"Audio combination failed: {str(e)}")
