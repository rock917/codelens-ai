import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from app.database.base import AsyncSessionLocal
from app.models.repository import Repository

router = APIRouter()

# Store active connections per repository
active_connections: dict[str, list[WebSocket]] = {}

async def broadcast_progress(repo_id: str, data: dict):
    """Send progress update to all connected clients for a repo."""
    if repo_id not in active_connections:
        return
    dead = []
    for ws in active_connections[repo_id]:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_connections[repo_id].remove(ws)

@router.websocket("/ws/progress/{repo_id}")
async def websocket_progress(websocket: WebSocket, repo_id: str):
    await websocket.accept()

    if repo_id not in active_connections:
        active_connections[repo_id] = []
    active_connections[repo_id].append(websocket)

    try:
        # Send current status immediately
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Repository).where(Repository.id == repo_id)
            )
            repo = result.scalar_one_or_none()
            if repo:
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "status": repo.status,
                    "total_files": repo.total_files,
                    "processed_files": repo.processed_files,
                    "total_chunks": repo.total_chunks,
                    "message": f"Status: {repo.status}"
                }))

        # Poll for updates
        while True:
            await asyncio.sleep(2)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Repository).where(Repository.id == repo_id)
                )
                repo = result.scalar_one_or_none()
                if not repo:
                    break

                await websocket.send_text(json.dumps({
                    "type": "status",
                    "status": repo.status,
                    "total_files": repo.total_files,
                    "processed_files": repo.processed_files,
                    "total_chunks": repo.total_chunks,
                    "message": _get_message(repo.status)
                }))

                if repo.status in ("READY", "FAILED"):
                    break

    except WebSocketDisconnect:
        pass
    finally:
        if repo_id in active_connections:
            try:
                active_connections[repo_id].remove(websocket)
            except ValueError:
                pass

def _get_message(status: str) -> str:
    messages = {
        "UPLOADING": "Extracting repository...",
        "PARSING": "Parsing source files...",
        "INDEXING": "Generating embeddings...",
        "ANALYZING": "Running AI summarization...",
        "READY": "Repository ready!",
        "FAILED": "Processing failed"
    }
    return messages.get(status, status)