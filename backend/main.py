from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database.base import init_db
from app.config.settings import settings
from app.api.routes import (
    repository, symbols, search,
    chat, summary, analysis, generation
)
from app.api.routes.websocket import router as ws_router
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting CodeLens AI...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    await init_db()
    print("✅ CodeLens AI is ready!")
    yield
    print("👋 Shutting down CodeLens AI...")

app = FastAPI(
    title="CodeLens AI",
    description="AI-Powered Developer Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(repository.router)
app.include_router(symbols.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(summary.router)
app.include_router(analysis.router)
app.include_router(generation.router)
app.include_router(ws_router)

@app.get("/")
async def root():
    return {
        "message": "CodeLens AI API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}