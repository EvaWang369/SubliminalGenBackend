from fastapi import HTTPException, UploadFile, File, Form
import uuid
import tempfile
import subprocess
from pathlib import Path
from google.cloud import storage
from datetime import timedelta
import os


async def extend_audio_gcs(
    combined_file: UploadFile = File(...),
    loops: int = Form(...),
    target_duration_label: str = Form(...),
    user_id: str = Form(...),
    is_vip: str = Form("false"),
    title: str = Form(None),
):
    """
    FINAL PRODUCTION VERSION (Cloud Run + GCS + MP3 320kbps):

    Flow:
      1. iOS uploads pre-mixed WAV (voice + music)
      2. Backend:
         - probes duration with ffprobe
         - applies 2s fade-in + 2s fade-out
         - loops the faded clip N times
         - converts to MP3 320kbps
      3. Uploads to Google Cloud Storage
      4. Returns a signed URL for iOS to download

    Notes:
      - No local file streaming from Cloud Run → avoids 32MB limit
      - Output MP3 is smaller and universally compatible
    """

    try:
        is_vip_bool = is_vip.lower() in ("true", "1", "yes")

        print("\n" + "=" * 60)
        print("🚀 PLATINUM EXTEND-AUDIO (GCS VERSION) STARTED")
        print("=" * 60)
        print(f"📥 user_id={user_id} | loops={loops} | target={target_duration_label} | is_vip={is_vip_bool}")

        if loops < 1:
            raise HTTPException(status_code=400, detail="loops must be >= 1")

        # ------------------------------------------------------------
        # 1. Read input file
        # ------------------------------------------------------------
        combined_bytes = await combined_file.read()
        if not combined_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Save input to a temp WAV
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            input_path = Path(tmp.name)
            tmp.write(combined_bytes)

        print(f"📁 Input temp file: {input_path}")

        # ------------------------------------------------------------
        # 2. Probe duration (ffprobe)
        # ------------------------------------------------------------
        try:
            probe_cmd = [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(input_path),
            ]
            probe_result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            dur_str = probe_result.stdout.strip()
            dur = float(dur_str)
        except Exception as e:
            print(f"❌ ffprobe failed: {e}")
            # Clean up input temp file before raising
            try:
                if input_path.exists():
                    input_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Could not analyze input duration: {str(e)}")

        print(f"🎧 Input duration: {dur:.2f}s (~{dur/60:.2f} min)")

        # ------------------------------------------------------------
        # 3. Apply fade-in / fade-out
        # ------------------------------------------------------------
        fade_in = 2.0
        fade_out = 2.0
        fade_out_start = max(0.0, dur - fade_out)

        faded_path = Path(tempfile.gettempdir()) / f"faded_{uuid.uuid4()}.wav"
        print(f"🎨 Faded temp file: {faded_path}")

        # We force PCM 16-bit, 44.1kHz, stereo here for compatibility
        fade_cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-filter_complex",
            (
                f"[0:a]"
                f"afade=t=in:ss=0:d={fade_in},"
                f"afade=t=out:st={fade_out_start}:d={fade_out}"
                f"[f]"
            ),
            "-map", "[f]",
            "-ac", "2",              # stereo
            "-ar", "44100",          # 44.1kHz sample rate
            "-c:a", "pcm_s16le",     # 16-bit PCM → super compatible
            str(faded_path),
        ]

        try:
            fade_proc = subprocess.run(
                fade_cmd,
                capture_output=True,
                check=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as e:
            print("❌ Fade processing error")
            print(e.stderr.decode("utf-8", errors="ignore")[-400:])
            # cleanup
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="Fade processing failed")
        except subprocess.TimeoutExpired:
            print("❌ Fade processing timeout")
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="Fade processing timeout")

        print("🌊 Fade applied successfully")

        # ------------------------------------------------------------
        # 4. Loop the faded file N times
        # ------------------------------------------------------------
        output_path = Path(tempfile.gettempdir()) / f"extended_{uuid.uuid4()}.wav"
        print(f"🔁 Extended temp file: {output_path}")

        # loops: we already have one copy, so stream_loop = loops - 1
        # This keeps the audio codec & format (pcm_s16le) via -c copy
        loop_cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops - 1),
            "-i", str(faded_path),
            "-c", "copy",            # no re-encode; keeps pcm_s16le
            str(output_path),
        ]

        try:
            loop_proc = subprocess.run(
                loop_cmd,
                capture_output=True,
                check=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            print("❌ Loop processing error")
            print(e.stderr.decode("utf-8", errors="ignore")[-400:])
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
                if output_path.exists():
                    output_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="Loop processing failed")
        except subprocess.TimeoutExpired:
            print("❌ Loop processing timeout")
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
                if output_path.exists():
                    output_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="Loop processing timeout")

        print(f"✅ Looping done (loops={loops})")

        # ------------------------------------------------------------
        # 5. Convert WAV to MP3 (320kbps default)
        # ------------------------------------------------------------
        if not output_path.exists():
            print("❌ Output file not created")
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="Output file not created")

        # Convert to MP3 320kbps (default)
        mp3_output_path = Path(tempfile.gettempdir()) / f"extended_{uuid.uuid4()}.mp3"
        print(f"🎵 Converting to MP3 320kbps: {mp3_output_path}")
        
        mp3_cmd = [
            "ffmpeg", "-y",
            "-i", str(output_path),
            "-codec:a", "libmp3lame",
            "-b:a", "320k",  # 320kbps for high quality
            "-ac", "2",
            str(mp3_output_path)
        ]
        
        # Alternative 256kbps for larger files (commented for now)
        # mp3_cmd = [
        #     "ffmpeg", "-y",
        #     "-i", str(output_path),
        #     "-codec:a", "libmp3lame",
        #     "-b:a", "256k",  # 256kbps for better compression
        #     "-ac", "2",
        #     str(mp3_output_path)
        # ]
        
        try:
            mp3_proc = subprocess.run(
                mp3_cmd,
                capture_output=True,
                check=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            print("❌ MP3 conversion error")
            print(e.stderr.decode("utf-8", errors="ignore")[-400:])
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
                if output_path.exists():
                    output_path.unlink()
                if mp3_output_path.exists():
                    mp3_output_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="MP3 conversion failed")
        except subprocess.TimeoutExpired:
            print("❌ MP3 conversion timeout")
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
                if output_path.exists():
                    output_path.unlink()
                if mp3_output_path.exists():
                    mp3_output_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="MP3 conversion timeout")

        print("🎵 MP3 conversion completed")

        # ------------------------------------------------------------
        # 6. Read final MP3 output bytes
        # ------------------------------------------------------------
        if not mp3_output_path.exists():
            print("❌ MP3 output file not created")
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
                if output_path.exists():
                    output_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail="MP3 output file not created")

        result_bytes = mp3_output_path.read_bytes()
        final_size_mb = len(result_bytes) / (1024 * 1024)
        final_duration = dur * loops  # approximate (fades shorten a tiny bit)

        print(f"✨ Final duration ≈ {final_duration:.1f}s ({final_duration/60:.1f} min)")
        print(f"📦 Final MP3 size ≈ {final_size_mb:.2f} MB (320kbps)")

        # ------------------------------------------------------------
        # 7. Upload to Google Cloud Storage (GCS)
        # ------------------------------------------------------------
        bucket_name = os.getenv("GCS_TEMP_BUCKET", "subliminalgen-temp-files")
        gcs_file_name = f"extended/{user_id}/{uuid.uuid4()}.mp3"

        print(f"☁️ Uploading to GCS: gs://{bucket_name}/{gcs_file_name}")

        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(gcs_file_name)
            blob.upload_from_string(result_bytes, content_type="audio/mpeg")
        except Exception as e:
            print(f"❌ GCS upload failed: {e}")
            # cleanup temp files
            try:
                if input_path.exists():
                    input_path.unlink()
                if faded_path.exists():
                    faded_path.unlink()
                if output_path.exists():
                    output_path.unlink()
                if mp3_output_path.exists():
                    mp3_output_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"GCS upload failed: {str(e)}")

        # Generate signed URL for download (24 hours)
        try:
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=24),
                method="GET"
            )
        except Exception as e:
            print(f"❌ Signed URL generation failed: {e}")
            raise HTTPException(status_code=500, detail="Could not generate download URL")

        print(f"✅ Upload successful! Signed URL generated")
        print(f"🔗 Download URL expires in 24 hours")

        # Cleanup temp files
        try:
            if input_path.exists():
                input_path.unlink()
            if faded_path.exists():
                faded_path.unlink()
            if output_path.exists():
                output_path.unlink()
            if mp3_output_path.exists():
                mp3_output_path.unlink()
        except Exception as e:
            print(f"⚠️ Temp file cleanup warning: {e}")

        print("🎉 EXTEND-AUDIO COMPLETED SUCCESSFULLY")
        print("=" * 60)

        return {
            "success": True,
            "file_id": gcs_file_name.split("/")[-1].replace(".mp3", ""),
            "download_url": signed_url,
            "duration_seconds": int(final_duration),
            "duration_minutes": round(final_duration / 60, 1),
            "file_size_mb": round(final_size_mb, 2),
            "format": "mp3",
            "bitrate": "320kbps",
            "loops": loops,
            "expires_at": "24 hours"
        }

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        # Final cleanup attempt
        try:
            if 'input_path' in locals() and input_path.exists():
                input_path.unlink()
            if 'faded_path' in locals() and faded_path.exists():
                faded_path.unlink()
            if 'output_path' in locals() and output_path.exists():
                output_path.unlink()
            if 'mp3_output_path' in locals() and mp3_output_path.exists():
                mp3_output_path.unlink()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")