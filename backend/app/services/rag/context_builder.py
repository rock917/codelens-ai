from typing import List, Dict, Any, Tuple


# ============================================================
# CONTEXT CONFIGURATION
# ============================================================

MAX_CONTEXT_TOKENS = 6000
AVG_CHARS_PER_TOKEN = 4


# ============================================================
# TOKEN ESTIMATION
# ============================================================

def estimate_tokens(text: str) -> int:
    """
    Roughly estimate the number of tokens in a text.

    This is intentionally lightweight and is only used for
    deciding how much context can be sent to the LLM.
    """
    if not text:
        return 0

    return len(text) // AVG_CHARS_PER_TOKEN


# ============================================================
# BUILD RETRIEVAL CONTEXT
# ============================================================

def build_context(
    query: str,
    chunks: List[Dict[str, Any]],
    repo_summary: str = "",
    conversation_history: List[Dict] = None,
    max_tokens: int = MAX_CONTEXT_TOKENS
) -> Tuple[str, List[Dict]]:
    """
    Build the context sent to the LLM from retrieved code chunks.

    Returns:
        context:
            Formatted code context for the LLM.

        sources:
            Structured source metadata returned separately to the
            frontend. Source metadata is NOT embedded into the
            final answer.
    """

    used_tokens = 0
    selected_chunks = []
    sources = []

    # ==========================================================
    # RESERVE TOKENS FOR QUERY + SYSTEM PROMPT
    # ==========================================================

    used_tokens += estimate_tokens(query) + 500

    if repo_summary:
        used_tokens += estimate_tokens(repo_summary)

    # ==========================================================
    # ACCOUNT FOR CONVERSATION HISTORY
    # ==========================================================

    if conversation_history:
        for msg in conversation_history[-4:]:
            used_tokens += estimate_tokens(
                msg.get("content", "")
            )

    # ==========================================================
    # SELECT CHUNKS WITHIN TOKEN BUDGET
    # ==========================================================

    seen_content = set()

    for chunk in chunks:
        content = chunk.get("content", "")

        if not content:
            continue

        # ------------------------------------------------------
        # Skip duplicate chunks
        # ------------------------------------------------------

        content_key = content[:100]

        if content_key in seen_content:
            continue

        seen_content.add(content_key)

        # ------------------------------------------------------
        # Estimate chunk size
        # ------------------------------------------------------

        chunk_tokens = estimate_tokens(content)

        if used_tokens + chunk_tokens > max_tokens:
            break

        selected_chunks.append(chunk)
        used_tokens += chunk_tokens

        # ------------------------------------------------------
        # Build structured source metadata
        #
        # IMPORTANT:
        # These sources are returned separately from the LLM
        # context. The LLM should NOT generate this metadata.
        # ------------------------------------------------------

        source = {
            "file_path": chunk.get("file_path", ""),
            "symbol_name": chunk.get("symbol_name", ""),
            "symbol_type": chunk.get("symbol_type", ""),
            "start_line": chunk.get("start_line", 0),
            "end_line": chunk.get("end_line", 0),
            "score": chunk.get(
                "final_score",
                chunk.get("score", 0)
            )
        }

        if source not in sources:
            sources.append(source)

    # ==========================================================
    # BUILD CONTEXT STRING
    # ==========================================================

    context_parts = []

    # ----------------------------------------------------------
    # Repository summary
    # ----------------------------------------------------------

    if repo_summary:
        context_parts.append(
            f"## Repository Overview\n"
            f"{repo_summary}\n"
        )

    # ----------------------------------------------------------
    # Relevant code section
    # ----------------------------------------------------------

    context_parts.append(
        "## Relevant Code\n"
    )

    # ----------------------------------------------------------
    # Add selected code chunks
    # ----------------------------------------------------------

    for i, chunk in enumerate(selected_chunks, 1):

        file_path = chunk.get(
            "file_path",
            ""
        )

        symbol_name = chunk.get(
            "symbol_name",
            ""
        )

        symbol_type = chunk.get(
            "symbol_type",
            ""
        )

        start_line = chunk.get(
            "start_line",
            0
        )

        end_line = chunk.get(
            "end_line",
            0
        )

        content = chunk.get(
            "content",
            ""
        )

        language = chunk.get(
            "language",
            ""
        )

        # ------------------------------------------------------
        # Context header
        # ------------------------------------------------------

        header = (
            f"### [{i}] {file_path}"
        )

        if symbol_name:
            header += (
                f" → {symbol_name}"
                f" ({symbol_type})"
            )

        header += (
            f" [Lines {start_line}-{end_line}]"
        )

        # ------------------------------------------------------
        # Code block
        # ------------------------------------------------------

        context_parts.append(
            f"{header}\n"
            f"```{language}\n"
            f"{content}\n"
            f"```\n"
        )

    # ==========================================================
    # RETURN CONTEXT + SOURCES
    # ==========================================================

    return (
        "\n".join(context_parts),
        sources
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

def build_system_prompt(
    repo_name: str = ""
) -> str:
    """
    Build the system prompt for CodeLens AI.

    IMPORTANT:
    Source metadata is handled by the application separately.
    The LLM must NOT generate a Sources section or internal
    source identifiers.
    """

    repository_text = (
        f" the repository: {repo_name}"
        if repo_name
        else " a code repository"
    )

    return f"""You are CodeLens AI, an expert code analysis assistant.
You are analyzing{repository_text}.

INSTRUCTIONS:

- Answer questions based ONLY on the provided code context.
- Be accurate and grounded in the provided code.
- Do not invent files, functions, classes, APIs, or implementation details.
- If the answer is not available in the provided code context, say so clearly.
- Be concise but thorough.
- Explain important patterns, issues, dependencies, and relationships when relevant.
- For security questions, clearly identify the security issue and explain why it matters.
- When referencing code, mention the relevant file naturally in your explanation.
- Do not fabricate line numbers.

SOURCE HANDLING:

- Do NOT create a "Sources" section.
- Do NOT create a source list at the end of your response.
- Do NOT output source metadata.
- Do NOT output internal source IDs.
- Do NOT output internal citation markers.
- Do NOT reproduce source metadata such as file paths combined with internal line markers.
- Do NOT generate strings such as "svg..." or other internal source artifacts.
- The application automatically provides source references separately from your answer.

RESPONSE FORMAT:

- Use clean Markdown formatting.
- Use headings when useful.
- Use bullet points and numbered lists when appropriate.
- Use inline code for function names, variables, classes, and short code references.
- Use fenced code blocks for multi-line code.
- Use the correct language identifier for code blocks.
- Do not add unnecessary preambles.
- Do not add a separate Sources section.
"""