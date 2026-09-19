from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class RepositoryUploadResponse(BaseModel):
    id: str
    name: str
    status: str
    message: str

class GithubIngestRequest(BaseModel):
    url: str
    name: Optional[str] = None

class RepositoryResponse(BaseModel):
    id: str
    name: str
    source_type: str
    source_url: Optional[str]
    status: str
    total_files: int
    processed_files: int
    total_chunks: int
    total_loc: int
    languages: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FileResponse(BaseModel):
    id: str
    repository_id: str
    path: str
    language: Optional[str]
    extension: Optional[str]
    size: int
    loc: int
    num_classes: int
    num_functions: int
    complexity_score: float
    importance_score: float
    importance_level: str

    class Config:
        from_attributes = True

class RepositoryStatsResponse(BaseModel):
    total_files: int
    total_loc: int
    total_chunks: int
    languages: dict
    total_classes: int
    total_functions: int
    avg_complexity: float
    issues_count: int
    importance_breakdown: dict