import os
import uuid
import json

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.base import get_db
from app.models.repository import Repository, File as FileModel, AnalysisIssue
from app.schemas.repository import (
    RepositoryUploadResponse,
    GithubIngestRequest,
    RepositoryResponse,
    FileResponse,
    RepositoryStatsResponse
)
from app.services.repository_service import (
    create_repository,
    process_zip_upload,
    process_github_url
)
from app.config.settings import settings


router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("/upload", response_model=RepositoryUploadResponse)
async def upload_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # Validate file
    if not file.filename.endswith(".zip"):
        raise HTTPException(400, "Only ZIP files are supported")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)

    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            400,
            f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Save ZIP temporarily
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    temp_path = os.path.join(
        settings.UPLOAD_DIR,
        f"temp_{uuid.uuid4()}.zip"
    )

    with open(temp_path, "wb") as f:
        f.write(content)

    # Create repo record
    name = file.filename.replace(".zip", "")
    repo = await create_repository(db, name, "zip")

    # Process in background
    background_tasks.add_task(
        process_zip_upload,
        db,
        repo.id,
        temp_path
    )

    return RepositoryUploadResponse(
        id=repo.id,
        name=repo.name,
        status=repo.status,
        message="Repository upload started. Processing in background."
    )


@router.post("/github", response_model=RepositoryUploadResponse)
async def ingest_github(
    request: GithubIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    url = request.url.strip()

    if not ("github.com" in url or "gitlab.com" in url):
        raise HTTPException(
            400,
            "Only GitHub/GitLab URLs are supported"
        )

    name = request.name or url.rstrip("/").split("/")[-1]
    repo = await create_repository(db, name, "github", url)

    background_tasks.add_task(
        process_github_url,
        db,
        repo.id,
        url
    )

    return RepositoryUploadResponse(
        id=repo.id,
        name=repo.name,
        status=repo.status,
        message="GitHub repository cloning started."
    )


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Repository).order_by(Repository.created_at.desc())
    )

    return result.scalars().all()


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: str,
    db: AsyncSession = Depends(get_db)
):
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
    db: AsyncSession = Depends(get_db)
):
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
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(FileModel)
        .where(FileModel.repository_id == repo_id)
        .order_by(FileModel.importance_score.desc())
    )

    return result.scalars().all()


@router.get("/{repo_id}/stats", response_model=RepositoryStatsResponse)
async def get_stats(
    repo_id: str,
    db: AsyncSession = Depends(get_db)
):
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
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )

    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    await db.delete(repo)
    await db.commit()

    return {
        "message": "Repository deleted successfully"
    }


@router.post("/{repo_id}/reindex")
async def reindex_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
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

    async def run_reindex():
        from app.services.incremental_indexer import incremental_index

        directory = os.path.join(
            settings.UPLOAD_DIR,
            repo_id
        )

        if os.path.exists(directory):
            async with __import__(
                "app.database.base",
                fromlist=["AsyncSessionLocal"]
            ).AsyncSessionLocal() as db2:
                await incremental_index(
                    db2,
                    repo_id,
                    directory
                )

    background_tasks.add_task(run_reindex)

    return {
        "message": "Reindexing started",
        "repository_id": repo_id
    }
@router.get("/{repo_id}/files/{file_id}/content")
async def get_file_content(
    repo_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
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