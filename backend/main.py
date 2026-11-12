from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.guards import RequestGuards
from sqlalchemy import text
import asyncio
from contextlib import suppress
from app.database.base import init_db, recover_interrupted_jobs, engine
from app.config.settings import settings
from app.api.routes import (
    repository, symbols, search,
    chat, summary, analysis, generation, account
)
from app.api.routes.websocket import router as ws_router
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting CodeLens AI...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    await init_db()
    if settings.RECOVER_INTERRUPTED_JOBS:
        await recover_interrupted_jobs()
    from app.services.account_deletion import retry_deletions
    deletion_task = asyncio.create_task(retry_deletions())
    print("✅ CodeLens AI is ready!")
    try:
        yield
    finally:
        deletion_task.cancel()
        with suppress(asyncio.CancelledError):
            await deletion_task
        await engine.dispose()
    print("👋 Shutting down CodeLens AI...")

app = FastAPI(
    title="CodeLens AI",
    description="AI-Powered Developer Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(RequestGuards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

@app.middleware("http")
async def private_response_cache_policy(request, call_next):
    response = await call_next(request)
    if request.url.path not in ('/', '/health', '/docs', '/redoc', '/openapi.json'):
        response.headers['Cache-Control'] = 'no-store'
    return response


# Routes
app.include_router(repository.router)
app.include_router(symbols.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(summary.router)
app.include_router(analysis.router)
app.include_router(generation.router)
app.include_router(ws_router)
app.include_router(account.router)

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


@app.get('/ready', include_in_schema=False)
async def ready():
    from starlette.responses import JSONResponse
    from app.services.archive_safety import ensure_disk_space
    from app.database.base import AsyncSessionLocal
    try:
        async with asyncio.timeout(5):
            async with AsyncSessionLocal() as db:
                await db.execute(text('SELECT 1'))
        ensure_disk_space(settings.UPLOAD_DIR)
        return JSONResponse({'status': 'ready'}, headers={'Cache-Control': 'no-store'})
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503, headers={'Cache-Control': 'no-store'})
