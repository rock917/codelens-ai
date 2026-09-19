from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.base import get_db
from app.models.repository import Symbol, File
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/symbols", tags=["symbols"])

class SymbolResponse(BaseModel):
    id: str
    file_id: str
    name: str
    type: str
    start_line: int
    end_line: int
    parent_name: Optional[str]
    signature: Optional[str]
    docstring: Optional[str]
    complexity: float
    file_path: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/{repo_id}")
async def get_symbols(
    repo_id: str,
    symbol_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Symbol, File.path)
        .join(File, Symbol.file_id == File.id)
        .where(File.repository_id == repo_id)
    )
    if symbol_type:
        query = query.where(Symbol.type == symbol_type)

    result = await db.execute(query)
    rows = result.all()

    symbols = []
    for sym, file_path in rows:
        symbols.append({
            "id": sym.id,
            "file_id": sym.file_id,
            "name": sym.name,
            "type": sym.type,
            "start_line": sym.start_line,
            "end_line": sym.end_line,
            "parent_name": sym.parent_name,
            "signature": sym.signature,
            "docstring": sym.docstring,
            "complexity": sym.complexity,
            "file_path": file_path
        })

    return symbols

@router.get("/file/{file_id}")
async def get_file_symbols(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Symbol).where(Symbol.file_id == file_id)
        .order_by(Symbol.start_line)
    )
    return result.scalars().all()