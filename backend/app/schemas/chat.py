from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    repository_id: str
    question: str = Field(min_length=1, max_length=12000)
    conversation_id: Optional[str] = None
    stream: bool = False

    @field_validator('question')
    @classmethod
    def nonempty_question(cls, value):
        if not value.strip():
            raise ValueError('Enter a question')
        return value.strip()


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator('title')
    @classmethod
    def nonempty_title(cls, value):
        if not value.strip():
            raise ValueError('Enter a conversation title')
        return value.strip()

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
