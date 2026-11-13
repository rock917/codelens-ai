from app.auth import AuthUser, get_current_user, owned_file, owned_repository
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.base import get_db
from app.models.repository import File, Repository
from app.services.summarization_service import (
    file_summary_result,
    repository_summary_result
)

router = APIRouter(prefix="/summary", tags=["summary"])

@router.get("/file/{file_id}")
async def get_file_summary(
    file_id: str,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_file(db, file_id, user.id)
    result = await db.execute(
        select(File).where(File.id == file_id)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(404, "File not found")

    # Use cached or generate lazily
    summary, cached = await file_summary_result(db, file_id, force)

    return {
        "file_id": file_id,
        "file_path": file.path,
        "language": file.language,
        "importance_level": file.importance_level,
        "summary": summary,
        "cached": cached
    }

@router.get("/repository/{repo_id}")
async def get_repository_summary(
    repo_id: str,
    force: bool = False,
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

    # Get important files
    files_result = await db.execute(
        select(File)
        .where(File.repository_id == repo_id)
        .order_by(File.importance_score.desc())
    )
    files = files_result.scalars().all()

    # Collect file summaries
    file_summaries = []
    for f in files:
        file_summaries.append({
            "path": f.path,
            "language": f.language,
            "importance_level": f.importance_level,
            "importance_score": f.importance_score,
            "num_classes": f.num_classes,
            "num_functions": f.num_functions,
            "loc": f.loc,
            "summary": f.summary
        })

    repo_summary, cached = await repository_summary_result(db, repo_id, force)

    return {
        "repository_id": repo_id,
        "repository_name": repo.name,
        "summary": repo_summary,
        "cached": cached,
        "files": file_summaries
    }

@router.get("/files/{repo_id}")
async def get_all_file_summaries(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(File)
        .where(File.repository_id == repo_id)
        .order_by(File.importance_score.desc())
    )
    files = result.scalars().all()

    return [
        {
            "id": f.id,
            "path": f.path,
            "language": f.language,
            "importance_level": f.importance_level,
            "importance_score": f.importance_score,
            "summary": f.summary,
            "has_summary": f.summary is not None
        }
        for f in files
    ]
