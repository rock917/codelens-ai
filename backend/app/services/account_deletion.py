"""Durable, retryable deletion for the supported single-worker deployment.

Stop accepting work, remove owned storage, commit SQL cleanup, then remove Auth.
The private request survives failures/restarts and is erased after completion.
"""
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
import json
from pathlib import Path
import shutil
import time
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import select, delete, or_
from app.config.settings import settings
from app.database.base import AsyncSessionLocal
from app.models.deletion import AccountDeletion
from app.models.repository import Repository, File, Symbol, CodeChunk, AnalysisIssue, RepositoryJob
from app.models.conversation import Conversation, Message
from app.models.summary import RepositorySummary
from app.models.usage import AccountUsage, AnalysisAdmission

active = Counter()
closing = set()
recently_deleted = {}


def enabled():
    return bool(settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value())


@asynccontextmanager
async def account_work(owner_id, allow_deleting=False):
    # Increment before awaiting: deletion cannot slip between the DB check and lease.
    active[owner_id] += 1
    try:
        now = time.monotonic()
        for old_owner, deadline in list(recently_deleted.items()):
            if deadline <= now:
                del recently_deleted[old_owner]
        if owner_id in recently_deleted:
            raise HTTPException(401, 'This account has been deleted.')
        if not allow_deleting:
            if owner_id in closing:
                raise HTTPException(409, 'Account deletion is in progress.')
            async with AsyncSessionLocal() as db:
                if await db.get(AccountDeletion, owner_id):
                    raise HTTPException(409, 'Account deletion is in progress. Open Settings for its status.')
        yield
    finally:
        active[owner_id] -= 1
        if not active[owner_id]:
            del active[owner_id]


async def delete_identity(owner_id):
    key = settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()
    if not key:
        raise RuntimeError('Admin credential not configured')
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        response = await client.request('DELETE', f'{settings.SUPABASE_URL.rstrip("/")}/auth/v1/admin/users/{UUID(owner_id)}',
            headers={'apikey': key, 'Authorization': f'Bearer {key}'}, json={'should_soft_delete': False})
    if response.status_code not in (200, 204, 404):
        # Never include provider response data or credentials in errors/logs.
        raise RuntimeError('Auth deletion unavailable')


def erase_storage(repo_id):
    from chromadb.errors import NotFoundError
    from app.services.vector_store import vector_store
    if str(UUID(repo_id)) != repo_id:
        raise ValueError('Invalid stored repository identifier')
    root = Path(settings.UPLOAD_DIR).resolve()
    target = root / repo_id
    if target.is_symlink():
        target.unlink()  # Never follow a source-controlled link.
    elif target.exists():
        if target.resolve().parent != root:
            raise ValueError('Unsafe repository storage path')
        shutil.rmtree(target)
    try:
        vector_store.get_client().delete_collection('repo_' + repo_id.replace('-', '_'))
    except NotFoundError:
        pass  # Missing is success on retry; all other failures must retry.


async def start_deletion(owner_id):
    if not enabled():
        raise HTTPException(503, 'Account deletion is not available yet. Contact support.')
    if owner_id in closing or active[owner_id] > 1:
        raise HTTPException(409, 'Wait for your current requests and jobs to finish, then try again.')
    closing.add(owner_id)
    try:
        async with AsyncSessionLocal() as db:
            request = await db.get(AccountDeletion, owner_id)
            if not request:
                owned = select(Repository.id).where(Repository.owner_id == owner_id)
                busy = await db.scalar(select(Repository.id).where(Repository.owner_id == owner_id,
                    Repository.status.notin_(['READY', 'FAILED'])).limit(1))
                job = await db.scalar(select(RepositoryJob.id).where(RepositoryJob.repository_id.in_(owned),
                    RepositoryJob.status.in_(['PENDING', 'RUNNING'])).limit(1))
                if busy or job:
                    raise HTTPException(409, 'Wait for your imports and jobs to finish before deleting your account.')
                ids = set((await db.scalars(owned)).all())
                # Admissions retain IDs of repositories deleted earlier, whose disk data may remain.
                ids.update((await db.scalars(select(AnalysisAdmission.repository_id).where(AnalysisAdmission.owner_id == owner_id))).all())
                if await db.scalar(select(Repository.id).where(Repository.id.in_(ids),
                        or_(Repository.owner_id != owner_id, Repository.owner_id.is_(None))).limit(1)):
                    raise HTTPException(409, 'Storage ownership requires review. Contact support.')
                for repo_id in ids:
                    if str(UUID(repo_id)) != repo_id:
                        raise HTTPException(409, 'Storage ownership requires review. Contact support.')
                db.add(AccountDeletion(owner_id=owner_id, repository_ids=json.dumps(sorted(ids)), phase='DATA'))
                await db.commit()
        return await finish_deletion(owner_id)
    finally:
        closing.discard(owner_id)


async def finish_deletion(owner_id):
    try:
        async with AsyncSessionLocal() as db:
            request = await db.get(AccountDeletion, owner_id)
            if request is None:
                return True
            ids = json.loads(request.repository_ids)
            if request.phase == 'DATA':
                for repo_id in ids:
                    await asyncio.to_thread(erase_storage, repo_id)
                file_ids = select(File.id).where(File.repository_id.in_(ids))
                conversation_ids = select(Conversation.id).where(Conversation.repository_id.in_(ids))
                await db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
                await db.execute(delete(Conversation).where(Conversation.repository_id.in_(ids)))
                await db.execute(delete(Symbol).where(Symbol.file_id.in_(file_ids)))
                await db.execute(delete(CodeChunk).where(or_(CodeChunk.file_id.in_(file_ids), CodeChunk.repository_id.in_(ids))))
                for model in (AnalysisIssue, RepositoryJob, RepositorySummary, File):
                    await db.execute(delete(model).where(model.repository_id.in_(ids)))
                await db.execute(delete(Repository).where(Repository.owner_id == owner_id))
                await db.execute(delete(AnalysisAdmission).where(AnalysisAdmission.owner_id == owner_id))
                await db.execute(delete(AccountUsage).where(AccountUsage.owner_id == owner_id))
                request.phase = 'AUTH'
                await db.commit()
            await delete_identity(owner_id)
            # An Auth lookup begun before deletion may return late. Block its
            # already-verified identity for longer than the ten-second Auth timeout.
            # This short-lived process cache disappears on restart; no new signup
            # shares the deleted UUID and no permanent identity record is retained.
            recently_deleted[owner_id] = time.monotonic() + 120
            await db.delete(request)
            await db.commit()
        return True
    except Exception:
        # Durable request stays blocked and retryable. No user records or secrets in logs.
        print('Account deletion pending; automatic retry scheduled.')
        return False


async def retry_deletions():
    while True:
        try:
            if enabled():
                async with AsyncSessionLocal() as db:
                    owners = (await db.scalars(select(AccountDeletion.owner_id))).all()
                for owner_id in owners:
                    if active[owner_id] or owner_id in closing:
                        continue
                    closing.add(owner_id)
                    try:
                        await finish_deletion(owner_id)
                    finally:
                        closing.discard(owner_id)
        except Exception:
            print('Account deletion retry unavailable; will retry.')
        await asyncio.sleep(60)
