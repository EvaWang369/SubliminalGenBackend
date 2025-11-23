import os
import time
import random
import string
from supabase import create_client
from .lyria_music import LyriaMusic

class MusicService:
    def __init__(self):
        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        self.supabase = create_client(supabase_url, supabase_key)
        
        # Initialize Lyria
        self.lyria = LyriaMusic()
    
    def generate_uuid(self):
        """Generate timestamp-based UUID for ordering"""
        epoch = str(int(time.time()))
        rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"{epoch}-{rand}"
    
    def enhance_prompt(self, base_prompt: str, music_type: list = None, instruments: list = None, mood: list = None, frequencies: list = None) -> str:
        """Enhance base prompt with additional parameters"""
        parts = [base_prompt]
        
        if music_type:
            parts.append(f"{', '.join(music_type)} style")
        
        if instruments:
            parts.append(f"featuring {', '.join(instruments)}")
        
        if mood:
            parts.append(f"with {', '.join(mood).lower()} atmosphere")
        
        if frequencies:
            parts.append(f"tuned to {', '.join(frequencies)}")
        
        return ", ".join(parts)
    
    def create_cache_key(self, request) -> str:
        """Create hash from all parameters that affect output"""
        import hashlib
        
        try:
            # Enhanced prompt
            enhanced_prompt = self.enhance_prompt(
                request.prompt, request.music_type, 
                request.instruments, request.mood, request.frequencies
            )
            
            # Include tag in cache key
            cache_string = f"{enhanced_prompt}:{request.tag}"
            cache_key = hashlib.md5(cache_string.encode()).hexdigest()
            print(f"🔑 Generated cache key: {cache_key} from: {cache_string}")
            return cache_key
        except Exception as e:
            print(f"❌ Cache key generation failed: {str(e)}")
            # Fallback to simple hash
            return hashlib.md5(f"{request.prompt}:{request.tag}".encode()).hexdigest()
    
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