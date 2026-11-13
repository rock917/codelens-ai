"""Bound memory use and keep inference/vector IO off the API event loop."""
import asyncio
from sqlalchemy import select
from app.config.settings import settings
from app.models.repository import CodeChunk
from app.services.cached_processing import embed as cached_embed
from app.services.vector_store import vector_store


async def index_repository_vectors(db, repository_id: str) -> int:
    last_id = ''
    stored = 0
    while True:
        result = await db.execute(
            select(CodeChunk)
            .where(CodeChunk.repository_id == repository_id, CodeChunk.id > last_id)
            .order_by(CodeChunk.id)
            .limit(settings.EMBEDDING_WRITE_BATCH_SIZE)
        )
        chunks = result.scalars().all()
        if not chunks:
            break
        # IDs, text, vectors and metadata come from the SAME ordered batch.
        texts = [f'File: {c.file_path}\nSymbol: {c.symbol_name or ""} ({c.symbol_type or ""})\n\n{c.content}' for c in chunks]
        embeddings = await asyncio.to_thread(cached_embed, repository_id, texts)
        await asyncio.to_thread(
            vector_store.add_chunks,
            repository_id=repository_id,
            chunk_ids=[c.chroma_id for c in chunks],
            embeddings=embeddings,
            documents=[c.content for c in chunks],
            metadatas=[{
                'repository_id': repository_id,
                'file_path': c.file_path,
                'symbol_name': c.symbol_name or '',
                'symbol_type': c.symbol_type or '',
                'language': c.language or '',
                'start_line': c.start_line,
                'end_line': c.end_line,
            } for c in chunks],
        )
        stored += len(chunks)
        last_id = chunks[-1].id
        print(f'Indexed {stored} chunks for repository {repository_id}', flush=True)
    return stored
