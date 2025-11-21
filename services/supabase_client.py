import os
from supabase import create_client, Client
from typing import Optional, List, Dict, Any

class SupabaseClient:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.client: Client = create_client(url, key)
    
    async def insert_generated_asset(self, asset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new generated asset"""
        result = self.client.table("generated_assets").insert(asset_data).execute()
        return result.data[0] if result.data else None
    
    async def find_similar_assets(self, embedding: List[float], asset_type: str, 
                                threshold: float = 0.9) -> List[Dict[str, Any]]:
        """Find similar assets using vector similarity"""
        # Note: This requires pgvector extension in Supabase
        result = self.client.rpc(
            "match_assets",
            {
                "query_embedding": embedding,
                "match_threshold": threshold,
                "asset_type": asset_type,
                "match_count": 5
            }
        ).execute()
        return result.data or []
    
    async def find_asset_by_hash(self, hash_signature: str) -> Optional[Dict[str, Any]]:
        """Find asset by exact hash match"""
        result = self.client.table("generated_assets").select("*").eq(
            "hash_signature", hash_signature
        ).limit(1).execute()
        return result.data[0] if result.data else None
    
    async def get_asset_by_id(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get asset by ID"""
        result = self.client.table("generated_assets").select("*").eq(
            "id", asset_id
        ).limit(1).execute()
        return result.data[0] if result.data else None
    
    async def increment_usage_count(self, asset_id: str):
        """Increment usage count for an asset"""
        self.client.table("generated_assets").update({
            "usage_count": "usage_count + 1"
        }).eq("id", asset_id).execute()
    
    async def insert_user_creation(self, creation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new user creation"""
        result = self.client.table("user_creations").insert(creation_data).execute()
        return result.data[0] if result.data else None
    
    async def get_user_creations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all creations for a user"""
        result = self.client.table("user_creations").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).execute()
        return result.data or []

# Global instance
_supabase_client = None

def get_supabase_client() -> SupabaseClient:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client