"""Mock services for testing API endpoints without external dependencies"""
import asyncio
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime

class MockSemanticCache:
    def __init__(self):
        self.cache = {}
    
    async def find_similar_music(self, prompt: str, duration: int) -> Optional[Dict[str, Any]]:
        return None  # Always return None for testing
    
    async def find_similar_video(self, prompt: str, duration: int) -> Optional[Dict[str, Any]]:
        return None
    
    async def store_music_asset(self, prompt: str, duration: int, audio_data: bytes) -> Dict[str, Any]:
        asset_id = str(uuid.uuid4())
        return {
            "id": asset_id,
            "file_url": f"https://mock-s3.com/music/{asset_id}.mp3",
            "duration": duration
        }
    
    async def store_video_asset(self, prompt: str, duration: int, video_data: bytes) -> Dict[str, Any]:
        asset_id = str(uuid.uuid4())
        return {
            "id": asset_id,
            "file_url": f"https://mock-s3.com/video/{asset_id}.mp4",
            "duration": duration
        }
    
    async def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        return {
            "id": asset_id,
            "file_url": f"https://mock-s3.com/music/{asset_id}.mp3",
            "duration": 30
        }
    
    async def increment_usage(self, asset_id: str):
        pass
    
    async def store_user_creation(self, user_id: str, voice_data: bytes, 
                                combined_data: bytes, title: str) -> Dict[str, Any]:
        creation_id = str(uuid.uuid4())
        return {
            "id": creation_id,
            "combined_url": f"https://mock-s3.com/vip/{creation_id}.mp3"
        }
    
    async def get_user_creations(self, user_id: str) -> List[Dict[str, Any]]:
        return []
    
    async def store_temp_file(self, file_data: bytes, file_type: str) -> str:
        return f"https://mock-s3.com/temp/{uuid.uuid4()}.{file_type}"

class MockAudioProcessor:
    async def combine_voice_music(self, voice_data: bytes, music_url: str) -> bytes:
        await asyncio.sleep(1)  # Simulate processing
        return b"MOCK_COMBINED_AUDIO_DATA"

class MockVideoProcessor:
    async def process_video(self, video_data: bytes) -> bytes:
        await asyncio.sleep(1)
        return b"MOCK_PROCESSED_VIDEO_DATA"

class MockS3Client:
    def get_file_stream(self, file_id: str):
        # Mock file stream
        return iter([b"MOCK_FILE_DATA"])

def get_mock_s3_client():
    return MockS3Client()