from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class GenerationResponse(BaseModel):
    id: str
    file_url: str
    cached: bool
    duration: int
    created_at: Optional[datetime] = None

class UserCreation(BaseModel):
    id: str
    title: str
    voice_url: Optional[str]
    combined_url: str
    created_at: datetime

class LibraryResponse(BaseModel):
    creations: List[UserCreation]
    total: int = 0
    
    def __init__(self, **data):
        super().__init__(**data)
        self.total = len(self.creations)