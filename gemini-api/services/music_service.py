import os
import time
import random
import string
import hashlib
from typing import List, Optional
from supabase import create_client
from .lyria_music import LyriaMusic

# -----------------------------------------
# Helpers
# -----------------------------------------

def now_ts() -> int:
    return int(time.time())

def normalize_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    return sorted(
        [v.strip().lower() for v in values if v.strip()]
    )

def duration_bucket(seconds: int) -> str:
    if seconds < 60:
        return "short"
    if seconds <= 180:
        return "medium"
    return "long"

def build_cache_key(
    music_type: List[str],
    mood: List[str],
    instruments: List[str],
    duration_seconds: int
) -> str:
    """
    IMPORTANT:
    - tag is NOT included
    - prompt is NOT included
    - vip is NOT included
    """
    payload = {
        "music_type": normalize_list(music_type),
        "mood": normalize_list(mood),
        "instruments": normalize_list(instruments),
        "duration": duration_bucket(duration_seconds)
    }

    raw = str(payload).encode("utf-8")
    return hashlib.md5(raw).hexdigest()

def normalize_tag(tag: str) -> str:
    return tag.strip().lower() if tag else "meditation"

class MusicService:
    def __init__(self):
        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        self.supabase = create_client(supabase_url, supabase_key)
        
        # Initialize Lyria
        self.lyria = LyriaMusic()
    
    # =========================
    # Entry Point
    # =========================
    async def get_music_with_enhanced_prompt(
        self,
        user_id: str,
        request
    ):
        tag = normalize_tag(request.tag)

        cache_key = build_cache_key(
            request.music_type or [],
            request.mood or [],
            request.instruments or [],
            request.duration
        )

        print(f"🔑 Cache key: {cache_key} for tag: {tag}")

        # 1️⃣ Fetch user progress
        try:
            user_resp = self.supabase.table("music_users").select("*").eq("user_id", user_id).execute()
            user_row = user_resp.data[0] if user_resp.data else None
            last_received_uuid = user_row.get("last_received_uuid") if user_row else None
        except Exception as e:
            print(f"⚠️ User lookup failed: {e}")
            last_received_uuid = None

        # 2️⃣ Try cached tracks (same metadata)
        try:
            cached_resp = self.supabase.table("music").select("*").eq("cache_key", cache_key).eq("tag", tag).order("uuid").execute()
            cached_tracks = cached_resp.data or []
        except Exception as e:
            print(f"⚠️ Cache lookup failed: {e}")
            cached_tracks = []

        for track in cached_tracks:
            if track["uuid"] != last_received_uuid:
                await self._update_user(user_id, track["uuid"])
                return self._response(track, cached=True)

        # 3️⃣ Cached exhausted → sequential by tag
        next_track = await self._get_next_by_tag(
            user_id=user_id,
            tag=tag,
            exclude_uuids=[t["uuid"] for t in cached_tracks],
            last_uuid=last_received_uuid
        )

        if next_track:
            return self._response(next_track, cached=True)

        # 4️⃣ Nothing left → generate new
        return await self._generate_new(
            user_id=user_id,
            prompt=request.prompt,
            tag=tag,
            duration=request.duration,
            music_type=request.music_type or [],
            mood=request.mood or [],
            instruments=request.instruments or [],
            cache_key=cache_key
        )

    # =========================
    # Generation
    # =========================
    async def _generate_new(
        self,
        user_id: str,
        prompt: str,
        tag: str,
        duration: int,
        music_type: List[str],
        mood: List[str],
        instruments: List[str],
        cache_key: str
    ):
        # Generate timestamp-based UUID
        epoch = str(int(time.time()))
        rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        uuid = f"{epoch}-{rand}"

        enhanced_prompt = self._enhance_prompt(
            prompt,
            music_type,
            mood,
            instruments
        )

        print(f"🎵 Generating: {enhanced_prompt}")
        
        try:
            audio_data = await self.lyria.generate_music_with_config(enhanced_prompt, tag, duration)
            
            # Upload to Supabase Storage
            file_path = f"{tag}/{uuid}.wav"
            upload_resp = self.supabase.storage.from_("music").upload(file_path, audio_data)
            
            if hasattr(upload_resp, 'error') and upload_resp.error:
                raise Exception(f"Upload failed: {upload_resp.error}")
            
            public_url = self.supabase.storage.from_("music").get_public_url(file_path)

            track = {
                "uuid": uuid,
                "title": f"{tag.title()} Track",
                "tag": tag,
                "supabase_url": public_url,
                "cache_key": cache_key
            }

            self.supabase.table("music").insert(track).execute()
            await self._update_user(user_id, uuid)

            return self._response(track, cached=False)
            
        except Exception as e:
            print(f"❌ Generation failed: {e}")
            raise Exception(f"Music generation error: {str(e)}")

    # =========================
    # Prompt Enhancer (Simple)
    # =========================
    def _enhance_prompt(
        self,
        prompt: str,
        music_type: List[str],
        mood: List[str],
        instruments: List[str]
    ) -> str:
        parts = [prompt]

        if music_type:
            parts.append(f"style: {', '.join(music_type)}")

        if mood:
            parts.append(f"mood: {', '.join(mood)}")

        if instruments:
            parts.append(f"instruments: {', '.join(instruments)}")

        return ", ".join(parts)

    # =========================
    # Sequential Delivery
    # =========================
    async def _get_next_by_tag(
        self,
        user_id: str,
        tag: str,
        exclude_uuids: List[str],
        last_uuid: Optional[str]
    ):
        try:
            query = self.supabase.table("music").select("*").eq("tag", tag).order("uuid")

            if last_uuid:
                query = query.gt("uuid", last_uuid)

            tracks_resp = query.execute()
            tracks = tracks_resp.data or []

            for track in tracks:
                if track["uuid"] not in exclude_uuids:
                    await self._update_user(user_id, track["uuid"])
                    return track

            return None
        except Exception as e:
            print(f"⚠️ Sequential lookup failed: {e}")
            return None

    # =========================
    # User Tracking
    # =========================
    async def _update_user(self, user_id: str, uuid: str):
        try:
            self.supabase.table("music_users").upsert({
                "user_id": user_id,
                "last_received_uuid": uuid,
                "last_received_timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
            }).execute()
        except Exception as e:
            print(f"⚠️ User update failed: {e}")

    # =========================
    # Response
    # =========================
    def _response(self, track: dict, cached: bool):
        return {
            "uuid": track["uuid"],
            "title": track["title"],
            "url": track["supabase_url"],
            "cached": cached
        }
    
    # =========================
    # Legacy Methods (Keep for compatibility)
    # =========================
    async def get_music_for_user(self, user_id: str, tag: str = "meditation"):
        """Legacy method - redirect to new implementation"""
        class SimpleRequest:
            def __init__(self, tag):
                self.prompt = "Ambient instrumental music"
                self.tag = tag
                self.duration = 30
                self.music_type = []
                self.mood = []
                self.instruments = []
        
        return await self.get_music_with_enhanced_prompt(user_id, SimpleRequest(tag))
    
    async def get_music_with_enhanced_prompt(self, user_id: str, request):
        """Generate music with enhanced prompt and hybrid caching"""
        try:
            # Create cache key
            cache_key = self.create_cache_key(request)
            
            # Step 1: Check if this exact enhanced prompt exists (hash-based caching)
            cached_tracks = []
            try:
                music_resp = self.supabase.table("music").select("*").eq("cache_key", cache_key).execute()
                cached_tracks = music_resp.data or []
            except Exception as cache_error:
                print(f"⚠️ Cache lookup failed (cache_key column may not exist): {cache_error}")
            
            # Step 2: Check what user has already received in this tag (sequential caching)
            user_resp = self.supabase.table("music_users").select("*").eq("user_id", user_id).execute()
            user_data = user_resp.data[0] if user_resp.data else None
            last_uuid = user_data.get('last_received_uuid') if user_data else None
            
            # Step 3: Find cached track that user hasn't received yet
            if cached_tracks:
                for track in cached_tracks:
                    # Check if user already received this specific track
                    if last_uuid != track['uuid']:
                        # User hasn't received this cached track yet
                        await self._update_user_record(user_id, track['uuid'])
                        print(f"🎯 Found cached track user hasn't received: {track['uuid']}")
                        return {
                            "uuid": track['uuid'],
                            "title": track['title'],
                            "url": track['supabase_url'],
                            "cached": True
                        }
                
                # User has received all cached tracks for this prompt, find next in tag sequence
                print(f"🔄 User has all cached tracks, finding next in {request.tag} sequence")
                return await self._get_next_track_in_tag_sequence(user_id, request.tag, cached_tracks)
            
            # Step 4: No cached tracks exist, generate new one
            print(f"🆕 No cached tracks found, generating new track")
            return await self._generate_enhanced_track(user_id, request, cache_key)
        
        # Handle fallback from tag sequence (if _get_next_track_in_tag_sequence returns None)
        except Exception as e:
            if "need to generate new" in str(e) or "No more tracks" in str(e):
                print(f"🔄 Fallback: generating new enhanced track")
                return await self._generate_enhanced_track(user_id, request, cache_key)
            raise Exception(f"Music service error: {str(e)}")
                
        except Exception as e:
            raise Exception(f"Music service error: {str(e)}")
    
    async def _get_next_track_in_tag_sequence(self, user_id: str, tag: str, exclude_tracks: list):
        """Get next track in tag sequence, excluding already cached tracks"""
        try:
            # Get user's last received track
            user_resp = self.supabase.table("music_users").select("*").eq("user_id", user_id).execute()
            user_data = user_resp.data[0] if user_resp.data else None
            last_uuid = user_data.get('last_received_uuid') if user_data else None
            
            # Get UUIDs to exclude (cached tracks user might have received)
            exclude_uuids = [track['uuid'] for track in exclude_tracks]
            
            # Find next track in tag sequence, excluding cached ones
            music_query = self.supabase.table("music").select("*").eq("tag", tag).order("uuid")
            
            if last_uuid:
                music_query = music_query.gt("uuid", last_uuid)
            
            music_resp = music_query.execute()
            
            # Find first track not in exclude list
            for track in music_resp.data or []:
                if track['uuid'] not in exclude_uuids:
                    await self._update_user_record(user_id, track['uuid'])
                    print(f"📋 Found next track in {tag} sequence: {track['uuid']}")
                    return {
                        "uuid": track['uuid'],
                        "title": track['title'],
                        "url": track['supabase_url'],
                        "cached": True
                    }
            
            # No more tracks in sequence, fallback to simple tag-based generation
            print(f"🔚 No more tracks in {tag} sequence, fallback to simple generation")
            return await self.get_music_for_user(user_id, tag)
            
        except Exception as e:
            print(f"⚠️ Error in tag sequence lookup: {str(e)}")
            return None
    
    async def _generate_enhanced_track(self, user_id: str, request, cache_key: str):
        """Generate new music track with enhanced prompt and proper config"""
        new_uuid = self.generate_uuid()
        
        # Enhanced prompt
        enhanced_prompt = self.enhance_prompt(
            request.prompt, request.music_type,
            request.instruments, request.mood, request.frequencies
        )
        
        print(f"🎵 Enhanced prompt: {enhanced_prompt}")
        print(f"🏷️ Tag: {request.tag}")
        
        start_time = time.time()
        
        # Apply VIP duration control
        final_duration = request.duration if request.is_vip else 30
        
        # Generate with enhanced prompt and tag-based config
        audio_data = await self.lyria.generate_music_with_config(enhanced_prompt, request.tag, final_duration)
        
        generation_time = time.time() - start_time
        print(f"⏱️ Generation took: {generation_time:.2f} seconds")
        
        # Upload to Supabase Storage
        file_path = f"{request.tag}/{new_uuid}.wav"
        upload_resp = self.supabase.storage.from_("music").upload(file_path, audio_data)
        
        if hasattr(upload_resp, 'error') and upload_resp.error:
            raise Exception(f"Upload failed: {upload_resp.error}")
        
        public_url = self.supabase.storage.from_("music").get_public_url(file_path)
        
        # Store in database (with cache_key if column exists)
        try:
            self.supabase.table("music").insert({
                "uuid": new_uuid,
                "title": f"Enhanced {request.tag.title()} Track",
                "tag": request.tag,
                "supabase_url": public_url,
                "cache_key": cache_key
            }).execute()
        except Exception as db_error:
            print(f"⚠️ Database insert with cache_key failed, trying without: {db_error}")
            # Fallback: insert without cache_key
            self.supabase.table("music").insert({
                "uuid": new_uuid,
                "title": f"Enhanced {request.tag.title()} Track",
                "tag": request.tag,
                "supabase_url": public_url
            }).execute()
        
        await self._update_user_record(user_id, new_uuid)
        
        total_time = time.time() - start_time
        
        return {
            "uuid": new_uuid,
            "title": f"Enhanced {request.tag.title()} Track",
            "url": public_url,
            "cached": False,
            "generation_time": f"{generation_time:.2f}s",
            "total_time": f"{total_time:.2f}s"
        }
    
    async def get_music_for_user(self, user_id: str, tag: str = "meditation"):
        """Get next music track for user, generate if needed"""
        try:
            # Get user's last received track
            user_resp = self.supabase.table("music_users").select("*").eq("user_id", user_id).execute()
            user_data = user_resp.data[0] if user_resp.data else None
            last_uuid = user_data.get('last_received_uuid') if user_data else None
            
            # Find next track after user's last received
            music_query = self.supabase.table("music").select("*").eq("tag", tag).order("uuid")
            
            if last_uuid:
                music_query = music_query.gt("uuid", last_uuid)
            
            music_resp = music_query.limit(1).execute()
            
            if music_resp.data:
                # Return existing track
                track = music_resp.data[0]
                await self._update_user_record(user_id, track['uuid'])
                return {
                    "uuid": track['uuid'],
                    "title": track['title'],
                    "url": track['supabase_url'],
                    "cached": True
                }
            else:
                # Generate new track
                return await self._generate_new_track(user_id, tag)
                
        except Exception as e:
            raise Exception(f"Music service error: {str(e)}")
    
    async def _generate_new_track(self, user_id: str, tag: str):
        """Generate new music track using Lyria"""
        new_uuid = self.generate_uuid()
        
        # Generate prompt based on tag
        prompts = {
            "meditation": "Peaceful ambient meditation music with soft pads and nature sounds",
            "focus": "Minimal ambient focus music with subtle rhythms",
            "sleep": "Gentle lullaby with soft piano and ambient textures",
            "energy": "Uplifting ambient music with gentle rhythms"
        }
        
        prompt = prompts.get(tag, "Ambient instrumental music")
        
        # Generate audio using Lyria with timing
        print(f"🎵 Starting Lyria generation for: {prompt}")
        start_time = time.time()
        
        audio_data = await self.lyria.generate_music(prompt, duration=30)
        
        generation_time = time.time() - start_time
        print(f"⏱️ Lyria generation took: {generation_time:.2f} seconds")
        print(f"📊 Audio data size: {len(audio_data)} bytes")
        
        # Upload to Supabase Storage with timing
        print(f"☁️ Uploading to Supabase Storage...")
        upload_start = time.time()
        
        file_path = f"{tag}/{new_uuid}.wav"
        upload_resp = self.supabase.storage.from_("music").upload(file_path, audio_data)
        
        upload_time = time.time() - upload_start
        print(f"⏱️ Upload took: {upload_time:.2f} seconds")
        
        if hasattr(upload_resp, 'status_code') and upload_resp.status_code != 200:
            raise Exception(f"Upload failed: {upload_resp}")
        elif hasattr(upload_resp, 'error') and upload_resp.error:
            raise Exception(f"Upload failed: {upload_resp.error}")
        
        print(f"✅ File uploaded successfully to: {file_path}")
        
        # Get public URL
        public_url = self.supabase.storage.from_("music").get_public_url(file_path)
        print(f"🔗 Public URL: {public_url}")
        
        # Store in database
        db_start = time.time()
        self.supabase.table("music").insert({
            "uuid": new_uuid,
            "title": f"Generated {tag.title()} Track",
            "tag": tag,
            "supabase_url": public_url
        }).execute()
        
        db_time = time.time() - db_start
        print(f"⏱️ Database insert took: {db_time:.2f} seconds")
        
        # Update user record
        await self._update_user_record(user_id, new_uuid)
        
        total_time = time.time() - start_time
        print(f"🏁 Total process time: {total_time:.2f} seconds")
        
        return {
            "uuid": new_uuid,
            "title": f"Generated {tag.title()} Track",
            "url": public_url,
            "cached": False,
            "generation_time": f"{generation_time:.2f}s",
            "total_time": f"{total_time:.2f}s"
        }
    
    async def _update_user_record(self, user_id: str, track_uuid: str):
        """Update user's last received track"""
        self.supabase.table("music_users").upsert({
            "user_id": user_id,
            "last_received_uuid": track_uuid,
            "last_received_timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }).execute()