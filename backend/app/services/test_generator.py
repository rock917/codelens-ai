import json
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.repository import File, Symbol, CodeChunk
from app.services.llm.groq_provider import groq_provider

async def generate_unit_tests(
    db: AsyncSession,
    file_id: str,
    symbol_name: str,
    repository_id: str
) -> dict:
    # Get file
    file_result = await db.execute(
        select(File).where(File.id == file_id)
    )
    file = file_result.scalar_one_or_none()
    if not file:
        return {"error": "File not found"}

    # Get symbol
    symbol_result = await db.execute(
        select(Symbol).where(
            Symbol.file_id == file_id,
            Symbol.name == symbol_name
        )
    )
    symbol = symbol_result.scalar_one_or_none()

    # Get relevant chunks for this symbol
    chunk_result = await db.execute(
        select(CodeChunk).where(
            CodeChunk.file_id == file_id,
            CodeChunk.symbol_name == symbol_name
        )
    )
    chunks = chunk_result.scalars().all()

    # Get related chunks (same file, parent class)
    related_result = await db.execute(
        select(CodeChunk).where(
            CodeChunk.file_id == file_id
        ).limit(5)
    )
    related_chunks = related_result.scalars().all()

    # Build code context
    function_code = ""
    if chunks:
        function_code = chunks[0].content
    
    related_code = "\n\n".join([
        c.content for c in related_chunks
        if c.symbol_name != symbol_name
    ][:3])

    # Build signature info
    signature = ""
    docstring = ""
    if symbol:
        signature = symbol.signature or ""
        docstring = symbol.docstring or ""

    messages = [
        {
            "role": "system",
            "content": """You are an expert Python test engineer.
Generate comprehensive unit tests using pytest.
Always include:
- Happy path tests
- Edge case tests  
- Error/exception tests
- Mock external dependencies
Be specific and practical."""
        },
        {
            "role": "user",
            "content": f"""Generate unit tests for this function/method.

File: {file.path}
Language: {file.language}
Symbol: {symbol_name}
Signature: {signature}
Docstring: {docstring}

Function code:
```{file.language}
{function_code}
```

Related context:
```{file.language}
{related_code}
```

Generate:
1. Complete pytest test file
2. At least 4-6 test cases
3. Proper mocking of dependencies
4. Clear test names describing what is tested
5. Brief comments explaining each test

Format your response as:
## Test File
```python
<complete test code>
```

## Test Cases Explained
<brief explanation of each test>

## Dependencies to Mock
<list of things that need mocking>

## Edge Cases Covered
<list of edge cases>"""
        }
    ]

    response = await groq_provider.chat(
        messages=messages,
        max_tokens=2000,
        temperature=0.2
    )

    return {
        "file_path": file.path,
        "symbol_name": symbol_name,
        "language": file.language,
        "signature": signature,
        "generated_tests": response
    }


async def generate_tests_for_file(
    db: AsyncSession,
    file_id: str,
    repository_id: str
) -> dict:
    # Get file
    file_result = await db.execute(
        select(File).where(File.id == file_id)
    )
    file = file_result.scalar_one_or_none()
    if not file:
        return {"error": "File not found"}

    # Get all symbols
    symbol_result = await db.execute(
        select(Symbol).where(Symbol.file_id == file_id)
        .order_by(Symbol.start_line)
    )
    symbols = symbol_result.scalars().all()

    # Get all chunks for context
    chunk_result = await db.execute(
        select(CodeChunk).where(CodeChunk.file_id == file_id)
    )
    chunks = chunk_result.scalars().all()

    full_code = "\n\n".join([c.content for c in chunks])

    symbol_list = "\n".join([
        f"- {s.type}: {s.name}" +
        (f"({s.signature})" if s.signature else "")
        for s in symbols
    ])

    messages = [
        {
            "role": "system",
            "content": """You are an expert Python test engineer.
Generate comprehensive unit tests using pytest."""
        },
        {
            "role": "user",
            "content": f"""Generate a complete test file for this module.

File: {file.path}
Language: {file.language}

Symbols defined:
{symbol_list}

Code:
```{file.language}
{full_code[:3000]}
```

Generate a complete pytest test file covering all major functions and methods.
Include proper imports, fixtures, and mocks."""
        }
    ]

    response = await groq_provider.chat(
        messages=messages,
        max_tokens=2000,
        temperature=0.2
    )

    return {
        "file_path": file.path,
        "language": file.language,
        "symbols_count": len(symbols),
        "generated_tests": response
    }