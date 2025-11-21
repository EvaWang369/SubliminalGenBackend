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