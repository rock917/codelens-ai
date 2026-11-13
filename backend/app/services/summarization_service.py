import json
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.repository import Repository, File, Symbol
from app.services.llm.groq_provider import groq_provider

async def summarize_function(
    file_path: str,
    symbol_name: str,
    code: str,
    language: str
) -> str:
    messages = [
        {
            "role": "system",
            "content": "You are a code analysis expert. Give concise, accurate summaries."
        },
        {
            "role": "user",
            "content": f"""Summarize this {language} function/method in 2-3 sentences.
Focus on: what it does, inputs, outputs, and any important side effects.

File: {file_path}
Symbol: {symbol_name}

```{language}
{code[:2000]}
```

Respond with ONLY the summary, no preamble."""
        }
    ]
    return await groq_provider.chat(messages, max_tokens=200, temperature=0.1)


async def summarize_file(
    file_path: str,
    language: str,
    symbols: List[dict],
    imports: List[dict],
    loc: int,
    sample_code: str = ""
) -> str:
    symbol_list = "\n".join([
        f"- {s['type']}: {s['name']}" +
        (f" (in {s['parent_name']})" if s.get('parent_name') else "")
        for s in symbols[:20]
    ])

    import_list = "\n".join([
        f"- {i.get('module', '')}"
        for i in imports[:10]
    ])

    messages = [
        {
            "role": "system",
            "content": "You are a code analysis expert. Give concise, accurate summaries."
        },
        {
            "role": "user",
            "content": f"""Summarize this {language} file in 3-4 sentences.
Focus on: purpose, main components, and role in the codebase.

File: {file_path}
Language: {language}
Lines of code: {loc}

Symbols defined:
{symbol_list or 'None'}

Imports:
{import_list or 'None'}

{f'Sample code:{chr(10)}```{language}{chr(10)}{sample_code[:1000]}{chr(10)}```' if sample_code else ''}

Respond with ONLY the summary, no preamble."""
        }
    ]
    return await groq_provider.chat(messages, max_tokens=300, temperature=0.1)


async def summarize_repository(
    repo_name: str,
    total_files: int,
    total_loc: int,
    languages: dict,
    important_files: List[dict]
) -> str:
    lang_str = ", ".join([
        f"{lang} ({count} files)"
        for lang, count in languages.items()
    ])

    files_str = "\n".join([
        f"- {f['path']} (importance: {f['importance_level']}, "
        f"{f['num_classes']} classes, {f['num_functions']} functions)"
        for f in important_files[:15]
    ])

    messages = [
        {
            "role": "system",
            "content": "You are a code analysis expert. Give concise, accurate summaries."
        },
        {
            "role": "user",
            "content": f"""Provide a high-level overview of this repository in 4-5 sentences.
Focus on: purpose, architecture, main components, and tech stack.

Repository: {repo_name}
Total files: {total_files}
Total lines of code: {total_loc}
Languages: {lang_str}

Most important files:
{files_str}

Respond with ONLY the summary, no preamble."""
        }
    ]
    return await groq_provider.chat(messages, max_tokens=400, temperature=0.1)


async def validate_repository(db, repo_id):
    from fastapi import HTTPException
    status = await db.scalar(select(Repository.status).where(Repository.id == repo_id))
    if status is None:
        raise HTTPException(404, 'Repository not found')
    if status != 'READY':
        raise HTTPException(409, 'Wait for repository indexing to finish.')


def summary_version():
    from app.services import result_cache as cache
    return cache.fingerprint(groq_provider.model, cache.code_version('summarization_service.py', 'llm/groq_provider.py'))


async def file_summary_result(db, file_id, force=False):
    from app.services import result_cache as cache
    file = await db.get(File, file_id)
    if file is None:
        return None, False
    symbols = (await db.scalars(select(Symbol).where(Symbol.file_id == file_id).order_by(Symbol.start_line, Symbol.name))).all()
    inputs = dict(file_path=file.path, language=file.language or 'unknown',
                  symbols=[dict(name=s.name, type=s.type, parent_name=s.parent_name) for s in symbols],
                  imports=json.loads(file.imports or '[]'), loc=file.loc or 0)
    key = cache.fingerprint('file-summary', summary_version(), file.hash, inputs)
    async def produce():
        return await summarize_file(**inputs)
    summary, reused = await cache.generated(file.repository_id, key, produce, force,
        lambda: validate_repository(db, file.repository_id))
    file.summary = summary
    await db.commit()
    return summary, reused


async def generate_file_summary_lazy(db, file_id):
    summary, _ = await file_summary_result(db, file_id)
    return summary


async def repository_summary_result(db, repo_id, force=False):
    from app.services import result_cache as cache
    repo = await db.get(Repository, repo_id)
    if repo is None:
        return None, False
    files = (await db.scalars(select(File).where(File.repository_id == repo_id)
                             .order_by(File.importance_score.desc(), File.path))).all()
    inputs = dict(repo_name=repo.name, total_files=repo.total_files, total_loc=repo.total_loc,
                  languages=json.loads(repo.languages or '{}'),
                  important_files=[dict(path=f.path, importance_level=f.importance_level,
                                        num_classes=f.num_classes, num_functions=f.num_functions) for f in files])
    key = cache.fingerprint('repository-summary', summary_version(), [(f.path, f.hash) for f in files], inputs)
    async def produce():
        return await summarize_repository(**inputs)
    return await cache.generated(repo_id, key, produce, force, lambda: validate_repository(db, repo_id))


async def run_selective_summarization(db, repo_id):
    files = (await db.scalars(select(File).where(File.repository_id == repo_id, File.importance_level == 'HIGH'))).all()
    for file in files:
        try:
            await file_summary_result(db, file.id)
        except Exception:
            await db.rollback()
    summary, _ = await repository_summary_result(db, repo_id)
    return summary
