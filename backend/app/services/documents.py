"""Bounded, read-only views of JSON and nbformat 4 notebooks. Never executes code."""
import ast
import json
from app.services.parser.base_parser import ParsedFile, ParsedSymbol
from app.services.parser.python_parser import PythonParser

MAX_SOURCE = 1024 * 1024
MAX_CELLS = 1000
MAX_NODES = 20000
MAX_DEPTH = 64


def load_json(content):
    def constant(_):
        raise ValueError('Non-finite numbers are not valid JSON')
    def pairs(items):
        result = {}
        for key, value in items:
            if len(key) > 512:
                raise ValueError('JSON object keys exceed the 512-character limit')
            if key in result:
                raise ValueError('Duplicate JSON object keys are not supported')
            result[key] = value
        return result
    return json.loads(content, parse_constant=constant, object_pairs_hook=pairs)


def _json_view(value):
    lines, sections = [], []
    count = 0
    def emit(node, path, depth, prefix='', comma=False):
        nonlocal count
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('JSON is too large or deeply nested to index')
        indent = '  ' * depth
        start = len(lines) + 1
        if isinstance(node, (dict, list)) and node:
            is_object = isinstance(node, dict)
            lines.append(indent + prefix + ('{' if is_object else '['))
            items = list(node.items()) if is_object else list(enumerate(node))
            for index, (key, child) in enumerate(items):
                encoded = json.dumps(key, ensure_ascii=True)
                child_path = path + '/' + str(key).replace('~', '~0').replace('/', '~1')
                emit(child, child_path, depth + 1, encoded + ': ' if is_object else '', index < len(items) - 1)
            lines.append(indent + ('}' if is_object else ']') + (',' if comma else ''))
        else:
            lines.append(indent + prefix + json.dumps(node, ensure_ascii=True, allow_nan=False) + (',' if comma else ''))
        # Disjoint top-level sections retain full nested values and JSON Pointer labels.
        if depth == 1 or (depth == 0 and not isinstance(node, (dict, list))):
            sections.append(dict(name=path or '/', type='json_path', start_line=start, end_line=len(lines), language='json'))
    emit(value, '', 0)
    if not sections:
        sections.append(dict(name='/', type='json_path', start_line=1, end_line=len(lines), language='json'))
    text = '\n'.join(lines)
    if len(text.encode()) > 4 * MAX_SOURCE:
        raise ValueError('Formatted JSON exceeds the indexing limit')
    return text, sections


def document_view(content, language):
    view = dict(content='', cells=[], sections=[], warnings=[], valid=False,
                analysis_supported=False, analysis_label='Not scored', kernel=None)
    try:
        data = load_json(content)
        if language == 'json':
            if len(content.encode()) > MAX_SOURCE:
                raise ValueError('JSON exceeds the 1 MiB indexing limit')
            view['content'], view['sections'] = _json_view(data)
            view.update(valid=True, analysis_label='JSON validated; no code health score')
            return view
        if not isinstance(data, dict) or data.get('nbformat') != 4 or not isinstance(data.get('cells'), list):
            raise ValueError('Expected a Jupyter notebook in nbformat 4')
        if len(data['cells']) > MAX_CELLS:
            raise ValueError('Notebook exceeds the 1,000-cell limit')
        metadata = data.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ValueError('Invalid notebook metadata')
        info, spec = metadata.get('language_info', {}), metadata.get('kernelspec', {})
        if not isinstance(info, dict) or not isinstance(spec, dict):
            raise ValueError('Invalid notebook kernel metadata')
        kernel = info.get('name') or spec.get('language') or 'unknown'
        if not isinstance(kernel, str):
            raise ValueError('Invalid notebook kernel language')
        kernel = kernel.lower()
        view['kernel'] = kernel
        python = kernel in ('python', 'python3')
        lines, size = [], 0
        for number, cell in enumerate(data['cells'], 1):
            if not isinstance(cell, dict):
                raise ValueError(f'Invalid cell {number}')
            kind, source = cell.get('cell_type'), cell.get('source', '')
            if isinstance(source, list) and all(isinstance(line, str) for line in source):
                source = ''.join(source)
            if not isinstance(source, str) or kind not in ('code', 'markdown', 'raw'):
                raise ValueError(f'Unsupported cell structure at cell {number}')
            size += len(source.encode())
            if size > MAX_SOURCE:
                raise ValueError('Notebook source exceeds the 1 MiB indexing limit')
            header = len(lines) + 1
            lines.append(f'# Cell {number} [{kind}]')
            start = len(lines) + 1
            source_lines = source.splitlines() or ['']
            lines.extend(source_lines)
            end = len(lines)
            lines.append('')
            reason = None
            supported = False
            if kind == 'code' and source.strip():
                if not python:
                    reason = 'Only Python code cells support health analysis'
                else:
                    try:
                        ast.parse(source)
                        supported = True
                    except (SyntaxError, ValueError, RecursionError):
                        reason = 'Magic commands, shell commands or invalid Python: indexed, not health-scanned'
            entry = dict(number=number, cell_type=kind, source=source, start_line=start,
                         end_line=end, header_line=header, analysis_supported=supported, reason=reason)
            view['cells'].append(entry)
            if source.strip():
                view['sections'].append(dict(name=f'Cell {number} ({kind})', type='notebook_cell',
                    start_line=start, end_line=end, language='python' if kind == 'code' and python else 'markdown' if kind == 'markdown' else 'text'))
            if reason:
                view['warnings'].append(f'Cell {number}: {reason}')
        view['content'] = '\n'.join(lines)
        view['valid'] = True
        view['analysis_supported'] = any(c['analysis_supported'] for c in view['cells'])
        view['analysis_label'] = 'Python code cells scanned; other cells excluded' if view['analysis_supported'] else 'No scannable Python code cells'
        return view
    except (ValueError, TypeError, RecursionError) as exc:
        # Never return the raw notebook: it may contain outputs or embedded media.
        view.update(content='', cells=[], sections=[], warnings=[str(exc)], valid=False)
        return view


def parse_document(path, content, language):
    view = document_view(content, language)
    parsed = ParsedFile(path=path, language=language, error=None if view['valid'] else '; '.join(view['warnings']),
                        display_content=view['content'], sections=view['sections'], loc=len(view['content'].splitlines()))
    if not view['valid']:
        return parsed
    if language == 'json':
        parsed.symbols = [ParsedSymbol(name=s['name'], type='json_path', start_line=s['start_line'], end_line=s['end_line']) for s in view['sections']]
    else:
        for cell in view['cells']:
            if not cell['analysis_supported']:
                continue
            part = PythonParser().safe_parse(path, cell['source'])
            offset = cell['start_line'] - 1
            for symbol in part.symbols:
                symbol.start_line += offset
                symbol.end_line += offset
                symbol.signature = f"Cell {cell['number']} · {symbol.signature or symbol.name}"
                parsed.symbols.append(symbol)
            for imp in part.imports:
                imp.line += offset
                parsed.imports.append(imp)
            parsed.num_functions += part.num_functions
            parsed.num_classes += part.num_classes
            parsed.complexity_score += part.complexity_score
    return parsed
