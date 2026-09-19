from typing import List, Dict, Any, AsyncGenerator, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.repository import Repository, CodeChunk

from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.services.rag.reranker import rerank_chunks
from app.services.rag.context_builder import (
    build_context,
    build_system_prompt
)
from app.services.llm.groq_provider import groq_provider

import re


# ============================================================
# RETRIEVE RELEVANT CODE CHUNKS
# ============================================================

async def retrieve_chunks(
    repository_id: str,
    query: str,
    db: AsyncSession,
    n_initial: int = 30,
    n_final: int = 8
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant code chunks using:

    1. Semantic/vector search
    2. Keyword-based file/symbol matching
    3. Reranking

    Returns a list of normalized code chunks.
    """

    # ========================================================
    # 1. EMBED QUERY
    # ========================================================

    query_embedding = embedding_service.embed_text(
        query
    )

    # ========================================================
    # 2. VECTOR SEARCH
    # ========================================================

    results = vector_store.search(
        repository_id=repository_id,
        query_embedding=query_embedding,
        n_results=n_initial
    )

    ids = results.get(
        "ids",
        [[]]
    )[0]

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    distances = results.get(
        "distances",
        [[]]
    )[0]

    chunks: List[Dict[str, Any]] = []

    for doc_id, doc, meta, dist in zip(
        ids,
        documents,
        metadatas,
        distances
    ):
        meta = meta or {}

        chunks.append({
            "id": doc_id,
            "content": doc or "",
            "file_path": meta.get(
                "file_path",
                ""
            ),
            "symbol_name": meta.get(
                "symbol_name",
                ""
            ),
            "symbol_type": meta.get(
                "symbol_type",
                ""
            ),
            "language": meta.get(
                "language",
                ""
            ),
            "start_line": meta.get(
                "start_line",
                0
            ),
            "end_line": meta.get(
                "end_line",
                0
            ),
            "score": round(
                1 - dist,
                4
            )
        })

    # ========================================================
    # 3. KEYWORD BOOST
    # ========================================================

    # Check the database for direct file/symbol matches.
    #
    # This helps when the user asks about an exact function,
    # file, class, module, etc. that semantic search might
    # otherwise rank lower.
    # ========================================================

    query_lower = query.lower()

    query_terms = set(
        re.findall(
            r"\b\w+\b",
            query_lower
        )
    )

    result = await db.execute(
        select(CodeChunk).where(
            CodeChunk.repository_id == repository_id
        )
    )

    all_db_chunks = result.scalars().all()

    existing_ids = {
        chunk["id"]
        for chunk in chunks
    }

    for db_chunk in all_db_chunks:

        if db_chunk.chroma_id in existing_ids:
            continue

        symbol = (
            db_chunk.symbol_name or ""
        ).lower()

        path = (
            db_chunk.file_path or ""
        ).lower()

        for term in query_terms:

            # Ignore extremely short terms because they
            # produce too many accidental matches.
            if len(term) <= 3:
                continue

            if (
                term in symbol
                or term in path
            ):
                chunks.append({
                    "id": db_chunk.chroma_id,
                    "content": db_chunk.content,
                    "file_path": db_chunk.file_path,
                    "symbol_name": (
                        db_chunk.symbol_name
                        or ""
                    ),
                    "symbol_type": (
                        db_chunk.symbol_type
                        or ""
                    ),
                    "language": (
                        db_chunk.language
                        or ""
                    ),
                    "start_line": (
                        db_chunk.start_line
                    ),
                    "end_line": (
                        db_chunk.end_line
                    ),
                    "score": 0.3
                })

                existing_ids.add(
                    db_chunk.chroma_id
                )

                break

    # ========================================================
    # 4. RERANK
    # ========================================================

    reranked = rerank_chunks(
        query,
        chunks,
        top_k=n_final
    )

    return reranked


# ============================================================
# BUILD LLM USER MESSAGE
# ============================================================

def build_user_message(
    question: str,
    context: str
) -> str:
    """
    Build the user message sent to the LLM.

    IMPORTANT:
    The LLM receives the code context but is explicitly told
    not to generate a separate Sources section.

    Source metadata is returned separately by build_context().
    """

    return f"""Question: {question}

{context}

Answer the question using only the code context above.

Important response rules:
- Do not create a Sources section.
- Do not create a source list.
- Do not output internal source metadata.
- Do not output internal citation IDs or markers.
- Do not output strings such as "svg..." or other source artifacts.
- Do not invent files, functions, classes, or line numbers.
- Mention relevant filenames naturally when useful.
- Use clean Markdown.
"""


# ============================================================
# ASK QUESTION - NON STREAMING
# ============================================================

async def ask_question(
    repository_id: str,
    question: str,
    db: AsyncSession,
    conversation_history: List[Dict] = None,
    stream: bool = False
) -> Tuple[str, List[Dict]]:
    """
    Ask a question about a repository.

    Returns:

        answer:
            Clean LLM-generated answer.

        sources:
            Structured source metadata generated by the
            application, not by the LLM.
    """

    # ========================================================
    # 1. GET REPOSITORY
    # ========================================================

    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id
        )
    )

    repo = result.scalar_one_or_none()

    if not repo:
        raise ValueError(
            "Repository not found"
        )

    # ========================================================
    # 2. RETRIEVE RELEVANT CHUNKS
    # ========================================================

    chunks = await retrieve_chunks(
        repository_id=repository_id,
        query=question,
        db=db
    )

    # ========================================================
    # 3. BUILD CONTEXT + STRUCTURED SOURCES
    # ========================================================

    context, sources = build_context(
        query=question,
        chunks=chunks,
        conversation_history=(
            conversation_history or []
        )
    )

    # ========================================================
    # 4. BUILD SYSTEM PROMPT
    # ========================================================

    system_prompt = build_system_prompt(
        repo.name
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # ========================================================
    # 5. ADD CONVERSATION HISTORY
    # ========================================================

    if conversation_history:

        for msg in conversation_history[-4:]:

            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # ========================================================
    # 6. ADD CURRENT QUESTION + CONTEXT
    # ========================================================

    user_message = build_user_message(
        question=question,
        context=context
    )

    messages.append({
        "role": "user",
        "content": user_message
    })

    # ========================================================
    # 7. GET LLM ANSWER
    # ========================================================

    answer = await groq_provider.chat(
        messages=messages,
        max_tokens=1500,
        temperature=0.1
    )

    # ========================================================
    # 8. RETURN ANSWER + SOURCES SEPARATELY
    # ========================================================

    return answer, sources


# ============================================================
# ASK QUESTION - STREAMING
# ============================================================

async def stream_question(
    repository_id: str,
    question: str,
    db: AsyncSession,
    conversation_history: List[Dict] = None
) -> AsyncGenerator:
    """
    Streaming version of ask_question().

    Each yielded item is:

        token, sources

    The same structured sources are returned with every token
    so the API layer can send them after streaming finishes.
    """

    # ========================================================
    # 1. GET REPOSITORY
    # ========================================================

    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id
        )
    )

    repo = result.scalar_one_or_none()

    if not repo:
        raise ValueError(
            "Repository not found"
        )

    # ========================================================
    # 2. RETRIEVE RELEVANT CHUNKS
    # ========================================================

    chunks = await retrieve_chunks(
        repository_id=repository_id,
        query=question,
        db=db
    )

    # ========================================================
    # 3. BUILD CONTEXT + STRUCTURED SOURCES
    # ========================================================

    context, sources = build_context(
        query=question,
        chunks=chunks,
        conversation_history=(
            conversation_history or []
        )
    )

    # ========================================================
    # 4. BUILD SYSTEM PROMPT
    # ========================================================

    system_prompt = build_system_prompt(
        repo.name
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # ========================================================
    # 5. ADD CONVERSATION HISTORY
    # ========================================================

    if conversation_history:

        for msg in conversation_history[-4:]:

            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # ========================================================
    # 6. ADD CURRENT QUESTION + CONTEXT
    # ========================================================

    user_message = build_user_message(
        question=question,
        context=context
    )

    messages.append({
        "role": "user",
        "content": user_message
    })

    # ========================================================
    # 7. STREAM LLM ANSWER
    # ========================================================

    async for token in groq_provider.stream(
        messages=messages,
        max_tokens=1500,
        temperature=0.1
    ):
        yield token, sources