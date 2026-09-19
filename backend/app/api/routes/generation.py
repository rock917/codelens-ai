from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.base import get_db
from app.models.repository import Repository, File, Symbol
from app.services.test_generator import (
    generate_unit_tests,
    generate_tests_for_file
)
from app.services.doc_generator import (
    generate_readme,
    generate_architecture_doc,
    generate_api_docs
)
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/generate", tags=["generation"])

class TestGenerationRequest(BaseModel):
    repository_id: str
    file_id: str
    symbol_name: Optional[str] = None

class DocGenerationRequest(BaseModel):
    repository_id: str
    doc_type: str  # readme, architecture, api

@router.post("/tests")
async def generate_tests(
    request: TestGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    # Verify repo
    repo_result = await db.execute(
        select(Repository).where(
            Repository.id == request.repository_id
        )
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")

    if request.symbol_name:
        result = await generate_unit_tests(
            db=db,
            file_id=request.file_id,
            symbol_name=request.symbol_name,
            repository_id=request.repository_id
        )
    else:
        result = await generate_tests_for_file(
            db=db,
            file_id=request.file_id,
            repository_id=request.repository_id
        )

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result

@router.post("/docs")
async def generate_docs(
    request: DocGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    repo_result = await db.execute(
        select(Repository).where(
            Repository.id == request.repository_id
        )
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")

    doc_type = request.doc_type.lower()

    if doc_type == "readme":
        content = await generate_readme(db, request.repository_id)
    elif doc_type == "architecture":
        content = await generate_architecture_doc(
            db, request.repository_id
        )
    elif doc_type == "api":
        content = await generate_api_docs(db, request.repository_id)
    else:
        raise HTTPException(
            400,
            "Invalid doc_type. Use: readme, architecture, api"
        )

    return {
        "repository_id": request.repository_id,
        "doc_type": doc_type,
        "content": content
    }

@router.get("/symbols/{repo_id}/{file_id}")
async def get_testable_symbols(
    repo_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Symbol)
        .where(Symbol.file_id == file_id)
        .where(Symbol.type.in_(["function", "method"]))
        .order_by(Symbol.start_line)
    )
    symbols = result.scalars().all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "signature": s.signature,
            "start_line": s.start_line,
            "end_line": s.end_line,
            "parent_name": s.parent_name
        }
        for s in symbols
    ]