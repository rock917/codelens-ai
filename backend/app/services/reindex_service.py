"""Refresh derived indexes without charging another import credit."""
import asyncio
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from app.config.settings import settings
from app.models.repository import Repository, RepositoryJob
from app.services import result_cache
from app.services.cached_processing import pipeline_version


async def schedule_reindex(db, repo, background_tasks, only_if_stale=False):
    async with result_cache.repository_lock(repo.id):
        await db.refresh(repo)
        if repo.status != 'READY':
            if only_if_stale:
                return False
            raise HTTPException(409, 'Wait for the current import or indexing to finish.')
        if only_if_stale and await asyncio.to_thread(result_cache.read, repo.id, 'index-version') == pipeline_version():
            return False
        busy = await db.scalar(select(RepositoryJob.id).where(RepositoryJob.repository_id == repo.id,
            RepositoryJob.status.in_(['PENDING', 'RUNNING'])).limit(1))
        if busy:
            raise HTTPException(409, 'Wait for the current analysis to finish before refreshing the index.')
        repo.status = 'INDEXING'
        await db.commit()
        background_tasks.add_task(run_reindex, repo.id, repo.owner_id)
        return True


async def run_reindex(repo_id, owner_id):
    from app.database.base import AsyncSessionLocal
    from app.services.account_deletion import account_work
    from app.services.incremental_indexer import incremental_index
    async with account_work(owner_id), result_cache.repository_lock(repo_id):
        async with AsyncSessionLocal() as db:
            repo = await db.get(Repository, repo_id)
            if repo is None or repo.owner_id != owner_id:
                return
            try:
                directory = Path(settings.UPLOAD_DIR) / repo_id
                if not directory.is_dir():
                    raise ValueError('Source files are missing')
                await incremental_index(db, repo_id, str(directory))
                repo.status, repo.error_message = 'READY', None
                await db.commit()
            except Exception:
                await db.rollback()
                repo = await db.get(Repository, repo_id)
                if repo:
                    repo.status = 'FAILED'
                    repo.error_message = 'Index refresh failed. Check server storage and retry the import.'
                    await db.commit()
