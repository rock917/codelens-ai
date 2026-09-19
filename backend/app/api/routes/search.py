from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.base import get_db
from app.models.repository import Repository
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    repository_id: str
    query: str
    n_results: int = 10
    language: Optional[str] = None

class SearchResult(BaseModel):
    file_path: str
    symbol_name: str
    symbol_type: str
    language: str
    start_line: int
    end_line: int
    content: str
    score: float

@router.post("")
async def search_code(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    # Check repo exists
    result = await db.execute(
        select(Repository).where(Repository.id == request.repository_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")

    if repo.status != "READY":
        raise HTTPException(400, f"Repository is not ready. Status: {repo.status}")

    # Embed query
    query_embedding = embedding_service.embed_text(request.query)

    # Build filter
    where = None
    if request.language:
        where = {"language": request.language}

    # Search ChromaDB
    results = vector_store.search(
        repository_id=request.repository_id,
        query_embedding=query_embedding,
        n_results=request.n_results,
        where=where
    )

    # Format results
    search_results = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, (doc_id, doc, meta, dist) in enumerate(
        zip(ids, documents, metadatas, distances)
    ):
        score = round(1 - dist, 4)  # cosine similarity
        search_results.append(SearchResult(
            file_path=meta.get("file_path", ""),
            symbol_name=meta.get("symbol_name", ""),
            symbol_type=meta.get("symbol_type", ""),
            language=meta.get("language", ""),
            start_line=meta.get("start_line", 0),
            end_line=meta.get("end_line", 0),
            content=doc,
            score=score
        ))

    return {
        "query": request.query,
        "total_results": len(search_results),
        "results": search_results
    }