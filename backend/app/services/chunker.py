from dataclasses import dataclass, field
from typing import List, Optional
from app.services.parser.base_parser import ParsedFile, ParsedSymbol

MAX_CHUNK_SIZE = 150  # lines
MIN_CHUNK_SIZE = 3    # lines

@dataclass
class CodeChunk:
    repository_id: str
    file_id: str
    file_path: str
    language: str
    content: str
    start_line: int
    end_line: int
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    parent_name: Optional[str] = None
    chunk_index: int = 0


def _group_consecutive(indexed_lines):
    if not indexed_lines:
        return []
    groups = []
    current_group = [indexed_lines[0]]
    for i in range(1, len(indexed_lines)):
        if indexed_lines[i][0] == indexed_lines[i-1][0] + 1:
            current_group.append(indexed_lines[i])
        else:
            if len(current_group) >= MIN_CHUNK_SIZE:
                groups.append(current_group)
            current_group = [indexed_lines[i]]
    if len(current_group) >= MIN_CHUNK_SIZE:
        groups.append(current_group)
    return groups


def _chunk_by_lines(
    lines: List[str],
    repository_id: str,
    file_id: str,
    file_path: str,
    language: str,
    chunk_index_start: int
) -> List[CodeChunk]:
    chunks = []
    chunk_index = chunk_index_start

    for i in range(0, len(lines), MAX_CHUNK_SIZE):
        chunk_lines = lines[i:i + MAX_CHUNK_SIZE]
        content = '\n'.join(chunk_lines)
        if not content.strip():
            continue
        chunks.append(CodeChunk(
            repository_id=repository_id,
            file_id=file_id,
            file_path=file_path,
            language=language,
            content=content,
            start_line=i + 1,
            end_line=i + len(chunk_lines),
            symbol_name=None,
            symbol_type="file_chunk",
            chunk_index=chunk_index
        ))
        chunk_index += 1
    return chunks


def _split_large_symbol(
    lines: List[str],
    symbol: ParsedSymbol,
    repository_id: str,
    file_id: str,
    file_path: str,
    language: str,
    chunk_index_start: int
) -> List[CodeChunk]:
    chunks = []
    chunk_index = chunk_index_start
    for i in range(0, len(lines), MAX_CHUNK_SIZE):
        chunk_lines = lines[i:i + MAX_CHUNK_SIZE]
        content = '\n'.join(chunk_lines)
        if not content.strip():
            continue
        actual_start = symbol.start_line + i
        actual_end = actual_start + len(chunk_lines) - 1
        chunks.append(CodeChunk(
            repository_id=repository_id,
            file_id=file_id,
            file_path=file_path,
            language=language,
            content=content,
            start_line=actual_start,
            end_line=actual_end,
            symbol_name=symbol.name,
            symbol_type=symbol.type,
            parent_name=symbol.parent_name,
            chunk_index=chunk_index
        ))
        chunk_index += 1
    return chunks


def chunk_parsed_file(
    parsed_file: ParsedFile,
    file_content: str,
    repository_id: str,
    file_id: str,
    chunk_index_start: int = 0
) -> List[CodeChunk]:
    chunks = []
    lines = file_content.splitlines()
    chunk_index = chunk_index_start

    if parsed_file.sections:
        # Cell/JSON Pointer boundaries are preserved; long values are split to fit
        # embedding input limits. Line numbers refer to the safe formatted view.
        lines = (parsed_file.display_content or '').splitlines()
        for section in parsed_file.sections:
            buffer, start, end = '', section['start_line'], section['start_line']
            for number in range(section['start_line'], section['end_line'] + 1):
                line = lines[number - 1]
                for offset in range(0, max(1, len(line)), 1400):
                    fragment = line[offset:offset + 1400]
                    if buffer and len(buffer) + len(fragment) > 1600:
                        chunks.append(CodeChunk(repository_id, file_id, parsed_file.path, section['language'],
                            buffer, start, end, section['name'], section['type'], parent_name=section.get('parent_name'), chunk_index=chunk_index))
                        chunk_index += 1
                        buffer = ''
                    if not buffer:
                        start = number
                    buffer += fragment + '\n'
                    end = number
            if buffer.strip():
                chunks.append(CodeChunk(repository_id, file_id, parsed_file.path, section['language'],
                    buffer.rstrip(), start, end, section['name'], section['type'], parent_name=section.get('parent_name'), chunk_index=chunk_index))
                chunk_index += 1
        return chunks

    if not parsed_file.symbols:
        chunks.extend(_chunk_by_lines(
            lines=lines,
            repository_id=repository_id,
            file_id=file_id,
            file_path=parsed_file.path,
            language=parsed_file.language,
            chunk_index_start=chunk_index
        ))
        return chunks

    sorted_symbols = sorted(parsed_file.symbols, key=lambda s: s.start_line)
    covered_lines = set()

    for symbol in sorted_symbols:
        start = symbol.start_line - 1
        end = symbol.end_line
        symbol_lines = lines[start:end]
        if not symbol_lines:
            continue

        for i in range(start, end):
            covered_lines.add(i)

        if len(symbol_lines) > MAX_CHUNK_SIZE:
            sub_chunks = _split_large_symbol(
                lines=symbol_lines,
                symbol=symbol,
                repository_id=repository_id,
                file_id=file_id,
                file_path=parsed_file.path,
                language=parsed_file.language,
                chunk_index_start=chunk_index
            )
            chunks.extend(sub_chunks)
            chunk_index += len(sub_chunks)
        else:
            content = '\n'.join(symbol_lines)
            if len(content.strip()) >= MIN_CHUNK_SIZE:
                chunks.append(CodeChunk(
                    repository_id=repository_id,
                    file_id=file_id,
                    file_path=parsed_file.path,
                    language=parsed_file.language,
                    content=content,
                    start_line=symbol.start_line,
                    end_line=symbol.end_line,
                    symbol_name=symbol.name,
                    symbol_type=symbol.type,
                    parent_name=symbol.parent_name,
                    chunk_index=chunk_index
                ))
                chunk_index += 1

    # Handle uncovered lines
    uncovered = []
    for i, line in enumerate(lines):
        if i not in covered_lines:
            uncovered.append((i, line))

    if uncovered:
        groups = _group_consecutive(uncovered)
        for group in groups:
            line_indices = [g[0] for g in group]
            content = '\n'.join([g[1] for g in group])
            if len(content.strip()) < MIN_CHUNK_SIZE:
                continue
            chunks.append(CodeChunk(
                repository_id=repository_id,
                file_id=file_id,
                file_path=parsed_file.path,
                language=parsed_file.language,
                content=content,
                start_line=line_indices[0] + 1,
                end_line=line_indices[-1] + 1,
                symbol_name=None,
                symbol_type="module_level",
                chunk_index=chunk_index
            ))
            chunk_index += 1

    return chunks
