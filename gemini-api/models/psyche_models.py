from pydantic import BaseModel
from typing import List, Optional

class PsycheTrack(BaseModel):
    id: str
    title: str
    duration: int
    tags: List[str]
    downloadURL: Optional[str] = None  # Optional for metadata-only responses

class PsycheTracksResponse(BaseModel):
    tracks: List[PsycheTrack]

class PsycheErrorResponse(BaseModel):
    error: str
    message: str