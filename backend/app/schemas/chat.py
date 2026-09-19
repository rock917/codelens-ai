from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    repository_id: str
    question: str
    conversation_id: Optional[str] = None
    stream: bool = False

class SourceReference(BaseModel):
    file_path: str
    symbol_name: str
    symbol_type: str
    start_line: int
    end_line: int
    score: float

class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: List[SourceReference]
    repository_id: str

class ConversationResponse(BaseModel):
    id: str
    repository_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True