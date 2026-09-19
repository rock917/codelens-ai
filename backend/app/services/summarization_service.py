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


async def generate_file_summary_lazy(
    db: AsyncSession,
    file_id: str
) -> Optional[str]:
    # Get file
    result = await db.execute(
        select(File).where(File.id == file_id)
    )
    file = result.scalar_one_or_none()
    if not file:
        return None

    # Already has summary
    if file.summary:
        return file.summary

    # Get symbols
    result = await db.execute(
        select(Symbol).where(Symbol.file_id == file_id)
    )
    symbols = result.scalars().all()

    symbol_dicts = [
        {
            "name": s.name,
            "type": s.type,
            "parent_name": s.parent_name
        }
        for s in symbols
    ]

    imports = []
    try:
        imports = json.loads(file.imports or "[]")
    except Exception:
        pass

    # Generate summary
    summary = await summarize_file(
        file_path=file.path,
        language=file.language or "unknown",
        symbols=symbol_dicts,
        imports=imports,
        loc=file.loc or 0
    )

    # Cache it
    file.summary = summary
    await db.commit()

    return summary


async def run_selective_summarization(
    db: AsyncSession,
    repo_id: str
):
    print(f"⏳ Running selective summarization for repo {repo_id}...")

    # Get HIGH importance files
    result = await db.execute(
        select(File).where(
            File.repository_id == repo_id,
            File.importance_level == "HIGH"
        )
    )
    high_files = result.scalars().all()

    for file in high_files:
        if file.summary:
            continue

        # Get symbols
        sym_result = await db.execute(
            select(Symbol).where(Symbol.file_id == file.id)
        )
        symbols = sym_result.scalars().all()

        symbol_dicts = [
            {
                "name": s.name,
                "type": s.type,
                "parent_name": s.parent_name
            }
            for s in symbols
        ]

        imports = []
        try:
            imports = json.loads(file.imports or "[]")
        except Exception:
            pass

        try:
            summary = await summarize_file(
                file_path=file.path,
                language=file.language or "unknown",
                symbols=symbol_dicts,
                imports=imports,
                loc=file.loc or 0
            )
            file.summary = summary
            print(f"  ✅ Summarized: {file.path}")
        except Exception as e:
            print(f"  ❌ Failed to summarize {file.path}: {e}")

    # Generate repository summary
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()

    if repo:
        result = await db.execute(
            select(File).where(File.repository_id == repo_id)
            .order_by(File.importance_score.desc())
        )
        all_files = result.scalars().all()

        important_files = [
            {
                "path": f.path,
                "importance_level": f.importance_level,
                "num_classes": f.num_classes,
                "num_functions": f.num_functions
            }
            for f in all_files
        ]

        languages = {}
        try:
            languages = json.loads(repo.languages or "{}")
        except Exception:
            pass

        try:
            repo_summary = await summarize_repository(
                repo_name=repo.name,
                total_files=repo.total_files,
                total_loc=repo.total_loc,
                languages=languages,
                important_files=important_files
            )

            # Store in repository record
            # We reuse error_message field pattern — add a summary field
            # Store in a summary table or use existing field
            # For now store in a dedicated file record
            print(f"  ✅ Repository summary generated")
        except Exception as e:
            print(f"  ❌ Failed to generate repo summary: {e}")
            repo_summary = ""

    await db.commit()
    print(f"✅ Selective summarization complete!")
    return repo_summary if repo else ""