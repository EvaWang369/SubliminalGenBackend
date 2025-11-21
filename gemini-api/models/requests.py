from pydantic import BaseModel
from typing import Optional

class MusicGenerateRequest(BaseModel):
    prompt: str
    duration: int  # seconds
    style: Optional[str] = "ambient"
    mood: Optional[str] = "calm"

class VideoGenerateRequest(BaseModel):
    prompt: str
    duration: int  # seconds
    style: Optional[str] = "abstract"
    resolution: Optional[str] = "1080p"

class CombineRequest(BaseModel):
    voice_file_id: str
    music_id: Optional[str] = None
    video_id: Optional[str] = None
    user_id: Optional[str] = None
    is_vip: bool = False
    title: Optional[str] = None