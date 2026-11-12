import os
import asyncio
import uuid
import hashlib
import shutil
import json
from pathlib import Path
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.repository import (
    Repository,
    File,
    Symbol,
    CodeChunk as CodeChunkModel,
    RepositoryStatus,
)

from app.services.file_filter import (
    should_process_file,
    detect_language,
    is_binary_file,
    get_file_size,
    MAX_FILE_SIZE,
)

from app.services.parser.parser_factory import ParserFactory
from app.services.importance_scorer import calculate_importance_score
from app.services.chunker import chunk_parsed_file
from app.services.vector_indexing import index_repository_vectors
from app.config.settings import settings

import git


def generate_id() -> str:
    return str(uuid.uuid4())


def hash_file(file_path: str) -> str:
    hasher = hashlib.md5()

    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)

        return hasher.hexdigest()

    except Exception:
        return ""


def read_file_content(file_path: str) -> str:
    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as f:
            return f.read()

    except Exception:
        return ""


async def create_repository(
    db: AsyncSession,
    name: str,
    source_type: str,
    source_url: Optional[str] = None,
    *,
    owner_id: str,
) -> Repository:

    repo = Repository(
        id=generate_id(),
        owner_id=owner_id,
        name=name,
        source_type=source_type,
        source_url=source_url,
        status=RepositoryStatus.UPLOADING,
        languages=json.dumps({}),
    )

    db.add(repo)

    await db.commit()
    await db.refresh(repo)

    return repo


async def update_repository_status(
    db: AsyncSession,
    repo_id: str,
    status: str,
    error_message: Optional[str] = None,
):
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )

    repo = result.scalar_one_or_none()

    if repo:
        repo.status = status

        repo.error_message = error_message

        from app.services.admission_service import settle
        await settle(db, repo_id, status)
        await db.commit()


async def process_zip_upload(
    db: AsyncSession,
    repo_id: str,
    zip_path: str,
):
    extract_dir = os.path.join(
        settings.UPLOAD_DIR,
        repo_id,
    )

    try:
        await update_repository_status(
            db,
            repo_id,
            RepositoryStatus.PARSING,
        )

        os.makedirs(
            extract_dir,
            exist_ok=True,
        )

        from app.services.archive_safety import extract_safe
        await asyncio.to_thread(extract_safe, zip_path, extract_dir)

        await index_directory(
            db,
            repo_id,
            extract_dir,
        )

        await update_repository_status(
            db,
            repo_id,
            RepositoryStatus.READY,
        )

        print(
            f"✅ Repository {repo_id} is READY"
        )

        asyncio.create_task(_run_summarization_background(repo_id))

    except Exception as e:

        print(
            f"❌ Repository {repo_id} FAILED: {e}"
        )

        await db.rollback()
        await update_repository_status(
            db,
            repo_id,
            RepositoryStatus.FAILED,
            str(e),
        )
        failed_dir = (Path(settings.UPLOAD_DIR) / repo_id).resolve()
        if failed_dir.parent == Path(settings.UPLOAD_DIR).resolve():
            await asyncio.to_thread(shutil.rmtree, failed_dir, ignore_errors=True)

    finally:

        if os.path.exists(zip_path):
            os.remove(zip_path)


async def process_github_url(
    db: AsyncSession,
    repo_id: str,
    github_url: str,
    revision: str = None,
):
    clone_dir = os.path.join(
        settings.UPLOAD_DIR,
        repo_id,
    )

    try:
        await update_repository_status(
            db,
            repo_id,
            RepositoryStatus.PARSING,
        )

        os.makedirs(
            clone_dir,
            exist_ok=True,
        )

        from app.services.archive_safety import ensure_disk_space, validate_directory
        ensure_disk_space(clone_dir)
        def clone_snapshot():
            # Fetch the admitted commit, never a moving HEAD.
            repo = git.Repo.init(clone_dir)
            with repo.git.custom_environment(GIT_TERMINAL_PROMPT='0'):
                repo.git.fetch('--depth=1', github_url, revision or 'HEAD', kill_after_timeout=180)
                repo.git.checkout('--detach', 'FETCH_HEAD')
            if revision and repo.head.commit.hexsha != revision:
                raise ValueError('Repository revision changed; please retry. No credit was used.')
        await asyncio.to_thread(clone_snapshot)
        await asyncio.to_thread(validate_directory, clone_dir)

        await index_directory(
            db,
            repo_id,
            clone_dir,
        )

        await update_repository_status(
            db,
            repo_id,
            RepositoryStatus.READY,
        )

        print(
            f"✅ Repository {repo_id} is READY"
        )

        asyncio.create_task(_run_summarization_background(repo_id))

    except Exception as e:

        print(
            f"❌ Repository {repo_id} FAILED: {e}"
        )

        await db.rollback()
        await update_repository_status(
            db,
            repo_id,
            RepositoryStatus.FAILED,
            str(e),
        )
        failed_dir = (Path(settings.UPLOAD_DIR) / repo_id).resolve()
        if failed_dir.parent == Path(settings.UPLOAD_DIR).resolve():
            await asyncio.to_thread(shutil.rmtree, failed_dir, ignore_errors=True)


async def index_directory(
    db: AsyncSession,
    repo_id: str,
    directory: str,
):

    IGNORED_DIRS = {
        "node_modules",
        ".git",
        "__pycache__",
        "dist",
        "build",
        "target",
        "coverage",
        "vendor",
        ".venv",
        "venv",
    }

    raw_files = []
    language_counts = {}
    total_loc = 0

    # First pass: collect all files
    for root, dirs, files in os.walk(directory):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORED_DIRS
        ]

        for filename in files:

            file_path = os.path.join(
                root,
                filename,
            )

            relative_path = os.path.relpath(
                file_path,
                directory,
            )

            relative_path = relative_path.replace(
                "\\",
                "/",
            )

            if not should_process_file(
                relative_path
            ):
                continue

            if not Path(file_path).resolve().is_relative_to(Path(directory).resolve()):
                continue

            if is_binary_file(file_path):
                continue

            file_size = get_file_size(
                file_path
            )

            if file_size > MAX_FILE_SIZE:
                continue

            language = detect_language(
                file_path
            )

            raw_files.append(
                {
                    "path": relative_path,
                    "full_path": file_path,
                    "language": language,
                    "size": file_size,
                }
            )

    all_paths = [
        f["path"]
        for f in raw_files
    ]

    dependent_counts = {
        p: 0
        for p in all_paths
    }

    file_records = []
    total_chunks = 0

    await update_repository_status(
        db,
        repo_id,
        RepositoryStatus.INDEXING,
    )

    for raw in raw_files:

        content = read_file_content(
            raw["full_path"]
        )

        loc = len(
            content.splitlines()
        )

        file_hash = hash_file(
            raw["full_path"]
        )

        total_loc += loc

        lang = raw["language"]

        parsed = None

        if lang in (
            "python",
            "javascript",
            "typescript",
        ):

            parsed = await asyncio.to_thread(
                ParserFactory.parse_file,
                raw["path"],
                content,
                lang,
            )

            if parsed and not parsed.error:

                for imp in parsed.imports:

                    for other_path in all_paths:

                        if (
                            imp.module.replace(
                                ".",
                                "/",
                            )
                            in other_path
                        ):

                            dependent_counts[
                                other_path
                            ] = (
                                dependent_counts.get(
                                    other_path,
                                    0,
                                )
                                + 1
                            )

        if lang not in (
            "unknown",
            "markdown",
            "json",
            "yaml",
            "toml",
        ):

            language_counts[lang] = (
                language_counts.get(
                    lang,
                    0,
                )
                + 1
            )

        file_id = generate_id()

        importance_score = 0.0
        importance_level = "LOW"

        num_classes = 0
        num_functions = 0

        complexity_score = 0.0

        imports_json = "[]"

        if parsed and not parsed.error:

            (
                importance_score,
                importance_level,
            ) = calculate_importance_score(
                parsed,
                all_paths,
                dependent_counts.get(
                    raw["path"],
                    0,
                ),
            )

            num_classes = parsed.num_classes

            num_functions = parsed.num_functions

            complexity_score = (
                parsed.complexity_score
            )

            imports_json = json.dumps(
                [
                    {
                        "module": i.module,
                        "line": i.line,
                    }
                    for i in parsed.imports
                ]
            )

            # Create symbols
            for sym in parsed.symbols:

                db.add(
                    Symbol(
                        id=generate_id(),
                        file_id=file_id,
                        name=sym.name,
                        type=sym.type,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        parent_name=sym.parent_name,
                        signature=sym.signature,
                        docstring=sym.docstring,
                        complexity=sym.complexity,
                    )
                )

            # Create chunks
            chunks = chunk_parsed_file(
                parsed_file=parsed,
                file_content=content,
                repository_id=repo_id,
                file_id=file_id,
            )

            total_chunks += len(chunks)

            # Save chunks to DB
            for chunk in chunks:

                chunk_id = generate_id()

                db.add(
                    CodeChunkModel(
                        id=chunk_id,
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
                        chroma_id=chunk_id,
                    )
                )

        file_record = File(
            id=file_id,
            repository_id=repo_id,
            path=raw["path"],
            language=lang,
            extension=Path(
                raw["full_path"]
            ).suffix.lower(),
            size=raw["size"],
            loc=loc,
            hash=file_hash,
            num_classes=num_classes,
            num_functions=num_functions,
            imports=imports_json,
            complexity_score=complexity_score,
            importance_score=importance_score,
            importance_level=importance_level,
        )

        file_records.append(
            file_record
        )

        db.add(file_record)
        await db.flush()

    await db.commit()

    # Update final stats
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id
        )
    )

    repo = result.scalar_one_or_none()

    if repo:

        repo.total_files = len(
            file_records
        )

        repo.processed_files = len(
            file_records
        )

        repo.total_loc = total_loc

        repo.languages = json.dumps(
            language_counts
        )

        repo.total_chunks = total_chunks

        await db.commit()

    # Publish file counts before the potentially slow inference stage.
    if total_chunks:
        await update_repository_status(db, repo_id, RepositoryStatus.ANALYZING)
        await index_repository_vectors(db, repo_id)

    return file_records


async def _run_summarization_background(repo_id: str):
    """Runs summarization after READY — non-blocking."""
    print(f"⏳ Background summarization starting for {repo_id}...")
    try:
        import asyncio
        from app.database.base import AsyncSessionLocal
        from app.services.summarization_service import run_selective_summarization
        from app.services.account_deletion import account_work
        async with AsyncSessionLocal() as db:
            repo = await db.get(Repository, repo_id)
            if repo is None or not repo.owner_id:
                return
            async with account_work(repo.owner_id):
                await asyncio.wait_for(run_selective_summarization(db, repo_id), timeout=300.0)
        print(f"✅ Background summarization complete for {repo_id}")
    except asyncio.TimeoutError:
        print(f"⚠️ Summarization timed out for {repo_id}")
    except Exception as e:
        print(f"⚠️ Summarization failed for {repo_id}: {e}")
