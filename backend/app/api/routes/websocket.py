import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy import select
from app.auth import authenticate_token
from app.config.settings import settings
from app.database.base import AsyncSessionLocal
from app.models.repository import Repository

router = APIRouter()


@router.websocket('/ws/progress/{repo_id}')
async def websocket_progress(websocket: WebSocket, repo_id: str):
    if websocket.headers.get('origin') != settings.FRONTEND_URL.rstrip('/'):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        # Tokens stay out of URLs and access logs. Authenticate before sending data.
        message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        if not isinstance(message, dict) or message.get('type') != 'authenticate':
            await websocket.close(code=4401)
            return
        token = message.get('access_token')
        if not isinstance(token, str):
            await websocket.close(code=4401)
            return
        user = await authenticate_token(token)
        verified_at = asyncio.get_running_loop().time()
        while True:
            if asyncio.get_running_loop().time() - verified_at >= 30:
                user = await authenticate_token(token)
                verified_at = asyncio.get_running_loop().time()
            async with AsyncSessionLocal() as db:
                repo = (await db.execute(select(Repository).where(
                    Repository.id == repo_id, Repository.owner_id == user.id,
                ))).scalar_one_or_none()
                if repo is None:
                    await websocket.close(code=4404)
                    return
                await websocket.send_json({
                    'type': 'status', 'status': repo.status,
                    'total_files': repo.total_files, 'processed_files': repo.processed_files,
                    'total_chunks': repo.total_chunks,
                    'message': repo.error_message or f'Status: {repo.status}',
                })
                if repo.status in ('READY', 'FAILED'):
                    await websocket.close(code=1000)
                    return
            await asyncio.sleep(2)
    except HTTPException as exc:
        await websocket.close(code=1013 if exc.status_code == 503 else 4401)
    except (asyncio.TimeoutError, ValueError):
        await websocket.close(code=4401)
    except WebSocketDisconnect:
        pass
