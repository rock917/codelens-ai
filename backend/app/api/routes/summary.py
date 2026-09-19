import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.base import get_db
from app.models.repository import File, Repository
from app.services.summarization_service import (
    generate_file_summary_lazy,
    summarize_repository
)
import json

router = APIRouter(prefix="/summary", tags=["summary"])

@router.get("/file/{file_id}")
async def get_file_summary(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(File).where(File.id == file_id)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(404, "File not found")

    # Use cached or generate lazily
    summary = await generate_file_summary_lazy(db, file_id)

    return {
        "file_id": file_id,
        "file_path": file.path,
        "language": file.language,
        "importance_level": file.importance_level,
        "summary": summary,
        "cached": file.summary is not None
    }

@router.get("/repository/{repo_id}")
async def get_repository_summary(
    repo_id: str,
    db: AsyncSession = Depends(get_db)
):
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

    # Generate repo summary on demand
    languages = {}
    try:
        languages = json.loads(repo.languages or "{}")
    except Exception:
        pass

    important_files = [
        {
            "path": f.path,
            "importance_level": f.importance_level,
            "num_classes": f.num_classes,
            "num_functions": f.num_functions
        }
        for f in files
    ]

    repo_summary = await summarize_repository(
        repo_name=repo.name,
        total_files=repo.total_files,
        total_loc=repo.total_loc,
        languages=languages,
        important_files=important_files
    )

    return {
        "repository_id": repo_id,
        "repository_name": repo.name,
        "summary": repo_summary,
        "files": file_summaries
    }

@router.get("/files/{repo_id}")
async def get_all_file_summaries(
    repo_id: str,
    db: AsyncSession = Depends(get_db)
):
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