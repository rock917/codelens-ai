from app.auth import AuthUser, get_current_user, owned_file, owned_repository
import os
import asyncio
from pathlib import Path
import hashlib
import uuid
import json

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database.base import get_db
from app.models.repository import Repository, File as FileModel, AnalysisIssue
from app.schemas.repository import (
    RepositoryUploadResponse,
    GithubIngestRequest,
    RepositoryResponse,
    FileResponse,
    RepositoryStatsResponse
)
from app.services.admission_service import admit, usage, normalize_url, resolve_revision
from app.workers.ingestion_worker import run_zip_ingestion, run_github_ingestion
from app.config.settings import settings
from app.services import result_cache
from app.services.reindex_service import schedule_reindex


router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get("/usage")
async def get_usage(db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    return await usage(db, user.id)


@router.post("/upload", response_model=RepositoryUploadResponse)
async def upload_zip(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                     db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    if not file.filename or not file.filename.lower().endswith('.zip'):
        raise HTTPException(400, 'Only ZIP files are supported')
    from app.services.archive_safety import ensure_disk_space
    try:
        ensure_disk_space(settings.UPLOAD_DIR)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    temp_path = os.path.join(settings.UPLOAD_DIR, f'temp_{uuid.uuid4()}.zip')
    try:
        size, digest = 0, hashlib.sha256()
        with open(temp_path, 'wb') as output:
            while block := await file.read(1024 * 1024):
                size += len(block)
                if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                    raise HTTPException(413, f'File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB')
                digest.update(block)
                output.write(block)
        revision = digest.hexdigest()
        repo, reused = await admit(db, user.id, file.filename[:-4], 'zip', 'zip:' + revision, revision)
        if not reused:
            background_tasks.add_task(run_zip_ingestion, repo.id, temp_path)
            temp_path = None
        if reused:
            await schedule_reindex(db, repo, background_tasks, only_if_stale=True)
        return RepositoryUploadResponse(id=repo.id, name=repo.name, status=repo.status, reused=reused,
            message='Opening your existing repository. No credit used.' if reused else 'Import started. One slot reserved until it succeeds.')
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/github", response_model=RepositoryUploadResponse)
async def ingest_github(request: GithubIngestRequest, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    url = normalize_url(request.url)
    revision = await resolve_revision(url)
    repo, reused = await admit(db, user.id, request.name or url.rsplit('/', 1)[-1],
                              'github', url, revision, request.confirmed_revision)
    if not reused:
        background_tasks.add_task(run_github_ingestion, repo.id, url, revision)
    else:
        await schedule_reindex(db, repo, background_tasks, only_if_stale=True)
    return RepositoryUploadResponse(id=repo.id, name=repo.name, status=repo.status, reused=reused,
        message='Opening your existing repository. No credit used.' if reused else 'Import started. One slot reserved until it succeeds.')


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Repository).where(Repository.owner_id == user.id).order_by(Repository.created_at.desc())
    )

    return result.scalars().all()


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )

    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    return repo


@router.get("/{repo_id}/status")
async def get_status(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )

    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    return {
        "id": repo.id,
        "status": repo.status,
        "total_files": repo.total_files,
        "processed_files": repo.processed_files,
        "total_chunks": repo.total_chunks,
        "error_message": repo.error_message
    }


@router.get("/{repo_id}/files", response_model=list[FileResponse])
async def get_files(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(FileModel)
        .where(FileModel.repository_id == repo_id)
        .order_by(FileModel.importance_score.desc())
    )

    return result.scalars().all()


@router.get("/{repo_id}/stats", response_model=RepositoryStatsResponse)
async def get_stats(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )

    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    files_result = await db.execute(
        select(FileModel).where(FileModel.repository_id == repo_id)
    )

    files = files_result.scalars().all()

    issues_result = await db.execute(
        select(func.count(AnalysisIssue.id))
        .where(AnalysisIssue.repository_id == repo_id)
    )

    issues_count = issues_result.scalar() or 0

    total_classes = sum(f.num_classes for f in files)
    total_functions = sum(f.num_functions for f in files)

    avg_complexity = (
        sum(f.complexity_score for f in files) / len(files)
        if files
        else 0.0
    )

    importance_breakdown = {
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0
    }

    for f in files:
        level = f.importance_level or "LOW"
        importance_breakdown[level] = (
            importance_breakdown.get(level, 0) + 1
        )

    return RepositoryStatsResponse(
        total_files=repo.total_files,
        total_loc=repo.total_loc,
        total_chunks=repo.total_chunks,
        languages=json.loads(repo.languages or "{}"),
        total_classes=total_classes,
        total_functions=total_functions,
        avg_complexity=round(avg_complexity, 2),
        issues_count=issues_count,
        importance_breakdown=importance_breakdown
    )


@router.delete("/{repo_id}")
async def delete_repository(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    async with result_cache.repository_lock(repo_id):
        await owned_repository(db, repo_id, user.id)
        result = await db.execute(
            select(Repository).where(Repository.id == repo_id)
        )

        repo = result.scalar_one_or_none()

        if not repo:
            raise HTTPException(404, "Repository not found")

        if repo.status not in ('READY', 'FAILED'):
            raise HTTPException(409, 'Wait for this import to finish before deleting it.')
        from app.models.repository import RepositoryJob
        busy = await db.scalar(select(RepositoryJob.id).where(RepositoryJob.repository_id == repo_id,
            RepositoryJob.status.in_(['PENDING', 'RUNNING'])).limit(1))
        if busy:
            raise HTTPException(409, 'Wait for current analysis to finish before deleting this repository.')
        from app.models.summary import RepositorySummary
        await db.execute(delete(RepositorySummary).where(RepositorySummary.repository_id == repo_id))
        await asyncio.to_thread(result_cache.erase, repo_id)
        await db.delete(repo)
        await db.commit()

        return {
            "message": "Repository deleted successfully"
        }


@router.post("/{repo_id}/reindex")
async def reindex_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )

    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    if repo.status != "READY":
        raise HTTPException(
            400,
            "Repository must be READY to reindex"
        )

    await schedule_reindex(db, repo, background_tasks)

    return {
        "message": "Reindexing started",
        "repository_id": repo_id
    }
@router.get("/{repo_id}/files/{file_id}/content")
async def get_file_content(
    repo_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_file(db, file_id, user.id, repo_id)
    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.repository_id == repo_id
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(404, "File not found")

    # Find actual file on disk
    repo_dir = os.path.join(settings.UPLOAD_DIR, repo_id)
    file_path = os.path.join(repo_dir, file.path)

    if not os.path.exists(file_path):
        # Try without first directory component
        parts = file.path.split('/', 1)
        if len(parts) > 1:
            file_path = os.path.join(repo_dir, parts[1])

    if not os.path.exists(file_path):
        raise HTTPException(404, "File content not found on disk")

    if not Path(file_path).resolve().is_relative_to(Path(repo_dir).resolve()):
        raise HTTPException(404, "File content not found")

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return {
            "file_id": file_id,
            "path": file.path,
            "language": file.language,
            "content": content,
            "loc": file.loc
        }
    except Exception as e:
        raise HTTPException(500, f"Could not read file: {str(e)}")
