from pydantic import BaseModel
from typing import Optional, List

class MusicGenerateRequest(BaseModel):
    prompt: str
    tag: str = "meditation"  # Frontend sends this directly
    duration: int = 30  # seconds, default to 30
    is_vip: bool = False  # VIP status for duration control
    music_type: Optional[List[str]] = None
    instruments: Optional[List[str]] = None
    mood: Optional[List[str]] = None
    frequencies: Optional[List[str]] = None
    # Legacy fields
    style: Optional[str] = "ambient"

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

class SignUpRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class SignInRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str