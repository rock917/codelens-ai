import json
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.repository import Repository, File, Symbol, AnalysisIssue
from app.services.llm.groq_provider import groq_provider

async def generate_readme(
    db: AsyncSession,
    repo_id: str
) -> str:
    # Get repo
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        return "Repository not found"

    # Get files ordered by importance
    files_result = await db.execute(
        select(File)
        .where(File.repository_id == repo_id)
        .order_by(File.importance_score.desc())
    )
    files = files_result.scalars().all()

    # Get symbols
    all_symbols = []
    for file in files[:10]:
        sym_result = await db.execute(
            select(Symbol).where(Symbol.file_id == file.id)
        )
        syms = sym_result.scalars().all()
        all_symbols.extend(syms)

    # Get issues summary
    issues_result = await db.execute(
        select(AnalysisIssue)
        .where(AnalysisIssue.repository_id == repo_id)
    )
    issues = issues_result.scalars().all()

    languages = {}
    try:
        languages = json.loads(repo.languages or "{}")
    except Exception:
        pass

    file_structure = "\n".join([
        f"  {'  ' * f.path.count('/')}{f.path.split('/')[-1]} "
        f"({f.language}, {f.loc} LOC)"
        for f in files
    ])

    important_symbols = "\n".join([
        f"- `{s.name}` ({s.type})" +
        (f": {s.docstring[:80]}" if s.docstring else "")
        for s in all_symbols[:20]
        if s.type in ('class', 'function')
    ])

    lang_str = ", ".join([
        f"{lang} ({count} files)"
        for lang, count in languages.items()
    ])

    issues_summary = f"""
- Critical: {sum(1 for i in issues if i.severity == 'CRITICAL')}
- High: {sum(1 for i in issues if i.severity == 'HIGH')}
- Medium: {sum(1 for i in issues if i.severity == 'MEDIUM')}
- Low: {sum(1 for i in issues if i.severity == 'LOW')}
""" if issues else "No issues analyzed yet."

    messages = [
        {
            "role": "system",
            "content": "You are a technical writer. Generate clear, professional README files."
        },
        {
            "role": "user",
            "content": f"""Generate a professional README.md for this project.

Project: {repo.name}
Total files: {repo.total_files}
Total LOC: {repo.total_loc}
Languages: {lang_str}

File structure:
{file_structure}

Key components:
{important_symbols}

Code quality issues:
{issues_summary}

Generate a complete README.md with:
1. Project title and description
2. Features
3. Tech stack
4. Project structure
5. Installation instructions
6. Usage examples
7. API documentation (if applicable)
8. Code quality notes
9. Contributing guidelines
10. License section

Make it professional and detailed."""
        }
    ]

    return await groq_provider.chat(
        messages=messages,
        max_tokens=2000,
        temperature=0.3
    )


async def generate_architecture_doc(
    db: AsyncSession,
    repo_id: str
) -> str:
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        return "Repository not found"

    files_result = await db.execute(
        select(File)
        .where(File.repository_id == repo_id)
        .order_by(File.importance_score.desc())
    )
    files = files_result.scalars().all()

    high_files = [f for f in files if f.importance_level == "HIGH"]
    medium_files = [f for f in files if f.importance_level == "MEDIUM"]

    high_list = "\n".join([
        f"- {f.path} (score: {f.importance_score}, "
        f"classes: {f.num_classes}, functions: {f.num_functions})"
        + (f"\n  Summary: {f.summary}" if f.summary else "")
        for f in high_files
    ])

    medium_list = "\n".join([
        f"- {f.path} (score: {f.importance_score})"
        for f in medium_files
    ])

    messages = [
        {
            "role": "system",
            "content": "You are a software architect. Generate clear architecture documentation."
        },
        {
            "role": "user",
            "content": f"""Generate architecture documentation for this codebase.

Project: {repo.name}
Total files: {repo.total_files}
Total LOC: {repo.total_loc}

HIGH importance files (core components):
{high_list}

MEDIUM importance files (supporting components):
{medium_list}

Generate:
1. Architecture Overview
2. Core Components description
3. Data Flow explanation
4. Module dependencies
5. Design patterns identified
6. Scalability considerations
7. Potential improvements

Use markdown formatting with clear sections."""
        }
    ]

    return await groq_provider.chat(
        messages=messages,
        max_tokens=2000,
        temperature=0.3
    )


async def generate_api_docs(
    db: AsyncSession,
    repo_id: str
) -> str:
    files_result = await db.execute(
        select(File)
        .where(File.repository_id == repo_id)
    )
    files = files_result.scalars().all()

    # Find API-related files
    api_files = [
        f for f in files
        if any(
            keyword in f.path.lower()
            for keyword in ['route', 'api', 'endpoint', 'view', 'handler', 'controller']
        )
    ]

    if not api_files:
        api_files = [f for f in files if f.importance_level == "HIGH"]

    all_symbols = []
    for file in api_files:
        sym_result = await db.execute(
            select(Symbol).where(Symbol.file_id == file.id)
        )
        syms = sym_result.scalars().all()
        for sym in syms:
            all_symbols.append({
                "file": file.path,
                "name": sym.name,
                "type": sym.type,
                "signature": sym.signature,
                "docstring": sym.docstring,
                "start_line": sym.start_line
            })

    symbols_text = "\n".join([
        f"File: {s['file']}\n"
        f"  {s['type']}: {s['name']}\n"
        f"  Signature: {s['signature']}\n"
        f"  Docs: {s['docstring'][:100] if s['docstring'] else 'None'}\n"
        for s in all_symbols[:25]
    ])

    messages = [
        {
            "role": "system",
            "content": "You are a technical writer. Generate clear API documentation."
        },
        {
            "role": "user",
            "content": f"""Generate API documentation for these components.

Components found:
{symbols_text}

Generate documentation with:
1. Overview of available functions/endpoints
2. For each function:
   - Purpose
   - Parameters
   - Return value
   - Example usage
3. Common patterns
4. Error handling

Use markdown formatting."""
        }
    ]

    return await groq_provider.chat(
        messages=messages,
        max_tokens=2000,
        temperature=0.2
    )