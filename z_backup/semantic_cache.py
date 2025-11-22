import hashlib
import numpy as np
from typing import Optional, List, Dict, Any
from sentence_transformers import SentenceTransformer
from z_backup.supabase_client import get_supabase_client
from z_backup.supabase_storage import get_supabase_storage
import uuid
from datetime import datetime

class SemanticCache:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.supabase = get_supabase_client()
        self.storage = get_supabase_storage()
        self.similarity_threshold = 0.9
        self.duration_tolerance = 5  # seconds
    
    def _normalize_prompt(self, prompt: str) -> str:
        """Normalize prompt for consistent matching"""
        return prompt.lower().strip().replace('\n', ' ')
    
    def _generate_hash(self, prompt: str, duration: int, asset_type: str) -> str:
        """Generate hash for exact matching"""
        normalized = self._normalize_prompt(prompt)
        content = f"{normalized}:{duration}:{asset_type}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for semantic search"""
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    async def find_similar_music(self, prompt: str, duration: int) -> Optional[Dict[str, Any]]:
        """Find similar music asset"""
        return await self._find_similar_asset(prompt, duration, "music")
    
    async def find_similar_video(self, prompt: str, duration: int) -> Optional[Dict[str, Any]]:
        """Find similar video asset"""
        return await self._find_similar_asset(prompt, duration, "video")
    
    async def _find_similar_asset(self, prompt: str, duration: int, 
                                asset_type: str) -> Optional[Dict[str, Any]]:
        """Core similarity search logic"""
        # 1. Try exact hash match first
        hash_signature = self._generate_hash(prompt, duration, asset_type)
        exact_match = await self.supabase.find_asset_by_hash(hash_signature)
        if exact_match:
            return exact_match
        
        # 2. Try semantic similarity search
        normalized_prompt = self._normalize_prompt(prompt)
        embedding = self._generate_embedding(normalized_prompt)
        
        similar_assets = await self.supabase.find_similar_assets(
            embedding, asset_type, self.similarity_threshold
        )
        
        # Filter by duration tolerance
        for asset in similar_assets:
            duration_diff = abs(asset['duration'] - duration)
            if duration_diff <= self.duration_tolerance:
                return asset
        
        return None
    
    async def store_music_asset(self, prompt: str, duration: int, 
                              audio_data: bytes) -> Dict[str, Any]:
        """Store new music asset"""
        return await self._store_asset(prompt, duration, "music", audio_data)
    
    async def store_video_asset(self, prompt: str, duration: int, 
                              video_data: bytes) -> Dict[str, Any]:
        """Store new video asset"""
        return await self._store_asset(prompt, duration, "video", video_data)
    
    async def _store_asset(self, prompt: str, duration: int, asset_type: str, 
                         file_data: bytes) -> Dict[str, Any]:
        """Core asset storage logic"""
        # Upload to Supabase Storage
        if asset_type == "music":
            file_url = self.storage.upload_shared_music(file_data, prompt)
        else:
            file_url = self.storage.upload_shared_video(file_data, prompt)
        
        # Generate metadata
        normalized_prompt = self._normalize_prompt(prompt)
        hash_signature = self._generate_hash(prompt, duration, asset_type)
        embedding = self._generate_embedding(normalized_prompt)
        
        # Store in database
        asset_data = {
            "id": str(uuid.uuid4()),
            "type": asset_type,
            "prompt": prompt,
            "normalized_prompt": normalized_prompt,
            "duration": duration,
            "embedding": embedding,
            "file_url": file_url,
            "hash_signature": hash_signature,
            "usage_count": 1,
            "tags": {"tier": "shared", "cached": True}
        }
        
        return await self.supabase.insert_generated_asset(asset_data)
    
    async def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get asset by ID"""
        return await self.supabase.get_asset_by_id(asset_id)
    
    async def increment_usage(self, asset_id: str):
        """Increment usage count"""
        await self.supabase.increment_usage_count(asset_id)
    
    async def store_user_creation(self, user_id: str, voice_data: bytes, 
                                combined_data: bytes, title: str) -> Dict[str, Any]:
        """Store VIP user creation"""
        creation_id = str(uuid.uuid4())
        
        # Upload files
        voice_url = self.storage.upload_vip_voice(voice_data, user_id, creation_id)
        combined_url = self.storage.upload_vip_final(combined_data, user_id, creation_id)
        
        # Store in database
        creation_data = {
            "id": creation_id,
            "user_id": user_id,
            "voice_url": voice_url,
            "combined_url": combined_url,
            "title": title,
            "metadata": {"tier": "vip"}
        }
        
        return await self.supabase.insert_user_creation(creation_data)
    
    async def get_user_creations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all user creations"""
        return await self.supabase.get_user_creations(user_id)
    
    async def store_temp_file(self, file_data: bytes, file_type: str) -> str:
        """Store temporary file for free users"""
        session_id = str(uuid.uuid4())
        return self.storage.upload_temp_file(file_data, session_id, file_type)