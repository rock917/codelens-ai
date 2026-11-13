"""Versioned parsing and embedding reuse, confined to one repository."""
from dataclasses import asdict
import math
import sys
from app.config.settings import settings
from app.services import result_cache as cache
from app.services.parser.base_parser import ParsedFile, ParsedSymbol, ParsedImport
from app.services.parser.parser_factory import ParserFactory
from app.services.embedding_service import embedding_service


def pipeline_version():
    return cache.fingerprint(settings.EMBEDDING_MODEL, settings.USE_GPU, sys.version_info[:2], cache.code_version(
        'parser/base_parser.py', 'parser/python_parser.py', 'parser/js_parser.py',
        'parser/parser_factory.py', 'chunker.py', 'embedding_service.py',
        'file_filter.py', 'importance_scorer.py', 'cached_processing.py',
        'repository_service.py', 'incremental_indexer.py', 'vector_indexing.py', 'documents.py', '../../requirements.txt'))


def parse(repo_id, path, content, language):
    key = cache.fingerprint('parse', pipeline_version(), path, content, language)
    value = cache.read(repo_id, key)
    if isinstance(value, dict):
        try:
            return ParsedFile(**{**value, 'symbols': [ParsedSymbol(**s) for s in value['symbols']],
                                 'imports': [ParsedImport(**i) for i in value['imports']]})
        except (KeyError, TypeError):
            pass
    parsed = ParserFactory.parse_file(path, content, language)
    if not parsed.error:
        cache.write(repo_id, key, asdict(parsed))
    return parsed


def embed(repo_id, texts):
    version = cache.fingerprint('embedding', settings.EMBEDDING_MODEL, settings.USE_GPU,
                               cache.code_version('embedding_service.py', 'cached_processing.py'))
    keys = [cache.fingerprint(version, text) for text in texts]
    values = {key: cache.read(repo_id, key) for key in set(keys)}
    def valid(vector):
        return isinstance(vector, list) and bool(vector) and all(type(v) in (float, int) and math.isfinite(v) for v in vector)
    missing = {key: text for key, text in zip(keys, texts) if not valid(values[key])}
    if missing:
        vectors = embedding_service.embed_batch(list(missing.values()))
        if len(vectors) != len(missing) or not all(valid(v) for v in vectors):
            raise ValueError('Invalid embedding response')
        for key, vector in zip(missing, vectors):
            values[key] = vector
            cache.write(repo_id, key, vector)
    return [values[key] for key in keys]
