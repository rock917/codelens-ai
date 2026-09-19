import os
import hashlib
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.repository import (
    File, Symbol, CodeChunk, Repository
)
from app.services.file_filter import (
    should_process_file, detect_language,
    is_binary_file, get_file_size, MAX_FILE_SIZE
)
from app.services.parser.parser_factory import ParserFactory
from app.services.importance_scorer import calculate_importance_score
from app.services.chunker import chunk_parsed_file
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.config.settings import settings
from pathlib import Path
import uuid

def generate_id() -> str:
    return str(uuid.uuid4())

def hash_file(file_path: str) -> str:
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""

def read_file_content(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ""

async def incremental_index(
    db: AsyncSession,
    repo_id: str,
    directory: str
) -> dict:
    """
    Only reprocess files that have changed since last indexing.
    Files with same hash are skipped entirely.
    """
    print(f"⏳ Running incremental index for repo {repo_id}...")

    IGNORED_DIRS = {
        'node_modules', '.git', '__pycache__',
        'dist', 'build', 'target', 'coverage',
        'vendor', '.venv', 'venv'
    }

    # Get existing file hashes from DB
    result = await db.execute(
        select(File).where(File.repository_id == repo_id)
    )
    existing_files = {f.path: f for f in result.scalars().all()}

    stats = {
        "unchanged": 0,
        "updated": 0,
        "added": 0,
        "deleted": 0
    }

    current_paths = set()

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for filename in files:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(
                file_path, directory
            ).replace('\\', '/')

            if not should_process_file(relative_path):
                continue
            if is_binary_file(file_path):
                continue

            file_size = get_file_size(file_path)
            if file_size > MAX_FILE_SIZE:
                continue

            current_paths.add(relative_path)
            new_hash = hash_file(file_path)

            # Check if file exists and hash matches
            if relative_path in existing_files:
                existing = existing_files[relative_path]
                if existing.hash == new_hash:
                    stats["unchanged"] += 1
                    continue

                # File changed — reprocess it
                print(f"  🔄 Updated: {relative_path}")
                await _reprocess_file(
                    db, repo_id, file_path,
                    relative_path, new_hash, file_size,
                    list(existing_files.keys())
                )
                stats["updated"] += 1
            else:
                # New file
                print(f"  ➕ Added: {relative_path}")
                await _reprocess_file(
                    db, repo_id, file_path,
                    relative_path, new_hash, file_size,
                    list(existing_files.keys())
                )
                stats["added"] += 1

    # Find deleted files
    for path, file in existing_files.items():
        if path not in current_paths:
            print(f"  🗑️ Deleted: {path}")
            await db.delete(file)
            stats["deleted"] += 1

    await db.commit()

    print(f"✅ Incremental index complete: {stats}")
    return stats


async def _reprocess_file(
    db: AsyncSession,
    repo_id: str,
    file_path: str,
    relative_path: str,
    file_hash: str,
    file_size: int,
    all_paths: list
):
    language = detect_language(file_path)
    content = read_file_content(file_path)
    loc = len(content.splitlines())

    # Delete existing file record + cascade
    result = await db.execute(
        select(File).where(
            File.repository_id == repo_id,
            File.path == relative_path
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Remove from ChromaDB
        result2 = await db.execute(
            select(CodeChunk).where(CodeChunk.file_id == existing.id)
        )
        old_chunks = result2.scalars().all()
        if old_chunks:
            try:
                collection = vector_store.get_collection(repo_id)
                old_ids = [c.chroma_id for c in old_chunks if c.chroma_id]
                if old_ids:
                    collection.delete(ids=old_ids)
            except Exception:
                pass
        await db.delete(existing)
        await db.flush()

    file_id = generate_id()
    parsed = None
    importance_score = 0.0
    importance_level = "LOW"
    num_classes = 0
    num_functions = 0
    complexity_score = 0.0
    imports_json = "[]"

    if language in ("python", "javascript", "typescript"):
        parsed = ParserFactory.parse_file(
            relative_path, content, language
        )

        if parsed and not parsed.error:
            importance_score, importance_level = calculate_importance_score(
                parsed, all_paths, 0
            )
            num_classes = parsed.num_classes
            num_functions = parsed.num_functions
            complexity_score = parsed.complexity_score
            imports_json = json.dumps([
                {"module": i.module, "line": i.line}
                for i in parsed.imports
            ])

            # Add symbols
            for sym in parsed.symbols:
                db.add(Symbol(
                    id=generate_id(),
                    file_id=file_id,
                    name=sym.name,
                    type=sym.type,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    parent_name=sym.parent_name,
                    signature=sym.signature,
                    docstring=sym.docstring,
                    complexity=sym.complexity
                ))

            # Create chunks
            chunks = chunk_parsed_file(
                parsed_file=parsed,
                file_content=content,
                repository_id=repo_id,
                file_id=file_id
            )

            # Embed and store
            if chunks:
                texts = [
                    f"File: {c.file_path}\n"
                    f"Symbol: {c.symbol_name or ''}\n\n{c.content}"
                    for c in chunks
                ]
                embeddings = embedding_service.embed_batch(texts)
                chunk_ids = [generate_id() for _ in chunks]
                documents = [c.content for c in chunks]
                metadatas = [{
                    "repository_id": repo_id,
                    "file_path": c.file_path,
                    "symbol_name": c.symbol_name or "",
                    "symbol_type": c.symbol_type or "",
                    "language": c.language or "",
                    "start_line": c.start_line,
                    "end_line": c.end_line
                } for c in chunks]

                vector_store.add_chunks(
                    repository_id=repo_id,
                    chunk_ids=chunk_ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )

                for i, chunk in enumerate(chunks):
                    db.add(CodeChunk(
                        id=generate_id(),
                        file_id=file_id,
                        repository_id=repo_id,
                        symbol_name=chunk.symbol_name,
                        symbol_type=chunk.symbol_type,
                        language=chunk.language,
                        file_path=chunk.file_path,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        chroma_id=chunk_ids[i]
                    ))

    db.add(File(
        id=file_id,
        repository_id=repo_id,
        path=relative_path,
        language=language,
        extension=Path(file_path).suffix.lower(),
        size=file_size,
        loc=loc,
        hash=file_hash,
        num_classes=num_classes,
        num_functions=num_functions,
        imports=imports_json,
        complexity_score=complexity_score,
        importance_score=importance_score,
        importance_level=importance_level
    ))