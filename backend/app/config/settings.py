from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import Field

class Settings(BaseSettings):
    # App
    APP_NAME: str = "CodeLens AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-in-production"
    USE_GPU: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./codelens.db"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_WRITE_BATCH_SIZE: int = Field(default=32, ge=1, le=512)
    EMBEDDING_CPU_THREADS: int = Field(default=2, ge=1)
    # In-process ingestion requires exactly one API worker and one instance.
    RECOVER_INTERRUPTED_JOBS: bool = True

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 100
    UPLOAD_DIR: str = "./uploads"

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"

settings = Settings()
