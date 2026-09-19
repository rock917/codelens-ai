from typing import List, Dict, Any
import re

def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 8
) -> List[Dict[str, Any]]:
    query_lower = query.lower()
    query_terms = set(re.findall(r'\b\w+\b', query_lower))

    # Remove stopwords
    stopwords = {
        'the', 'a', 'an', 'is', 'it', 'in', 'on', 'at',
        'to', 'for', 'of', 'and', 'or', 'how', 'does',
        'what', 'where', 'which', 'who', 'why', 'when',
        'do', 'did', 'this', 'that', 'with', 'from', 'are'
    }
    query_terms -= stopwords

    scored = []
    for chunk in chunks:
        score = chunk.get('score', 0.0)
        content_lower = chunk.get('content', '').lower()
        file_path_lower = chunk.get('file_path', '').lower()
        symbol_name_lower = chunk.get('symbol_name', '').lower()

        # Keyword match bonus
        matched_terms = sum(
            1 for term in query_terms
            if term in content_lower
        )
        keyword_bonus = matched_terms * 0.05

        # Symbol name match bonus
        symbol_bonus = 0.0
        for term in query_terms:
            if term in symbol_name_lower:
                symbol_bonus += 0.1

        # File path match bonus
        path_bonus = 0.0
        for term in query_terms:
            if term in file_path_lower:
                path_bonus += 0.08

        # Prefer functions/methods over module_level for specific queries
        type_bonus = 0.0
        symbol_type = chunk.get('symbol_type', '')
        if symbol_type in ('function', 'method', 'class'):
            type_bonus = 0.03

        final_score = score + keyword_bonus + symbol_bonus + path_bonus + type_bonus

        scored.append({**chunk, 'final_score': final_score})

    scored.sort(key=lambda x: x['final_score'], reverse=True)
    return scored[:top_k]