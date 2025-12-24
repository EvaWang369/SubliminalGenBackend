import os
import time
import random
import string
import hashlib
from typing import List, Optional
from supabase import create_client
from .lyria_music import LyriaMusic

# -----------------------------------------
# Prompt Flavor Modifiers (Optional Layer)
# -----------------------------------------

STATE_PROMPT_MODIFIERS = {
    "powerful": "confident, expansive, grounded presence",
    "determined": "focused, steady, forward-moving energy",
    "freedom": "open, spacious, unrestricted flow",
    "dreamy": "ethereal, floating, slow-evolving textures"
}

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

def state_prompt_flavor(states: List[str]) -> str:
    """
    Convert identity states into prompt-only flavor text.
    Does NOT affect cache, tags, or generation config.
    """
    if not states:
        return ""

    flavors = []
    for s in states:
        key = s.strip().lower()
        if key in STATE_PROMPT_MODIFIERS:
            flavors.append(STATE_PROMPT_MODIFIERS[key])

    return ", ".join(flavors)

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

        # Identity → language flavor (no logic, no cache impact)
        state_flavor = state_prompt_flavor(music_type)
        if state_flavor:
            parts.append(f"presence: {state_flavor}")

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