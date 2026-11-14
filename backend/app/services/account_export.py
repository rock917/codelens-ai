"""Private, bounded data snapshots. No persistent exports or database writes."""
import asyncio
import json
import tempfile
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, text
from starlette.responses import StreamingResponse

from app.database.base import AsyncSessionLocal
from app.guards import WindowLimiter
from app.models.repository import Repository, File, Symbol, AnalysisIssue, RepositoryJob
from app.models.conversation import Conversation, Message
from app.models.summary import RepositorySummary
from app.models.usage import AnalysisAdmission
from app.services.admission_service import usage

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 200_000
active_exports: set[str] = set()
limiter = WindowLimiter()


class ExportResponse(StreamingResponse):
    """Own the spool and capacity lease, including interrupted downloads."""
    def __init__(self, spool, owner_id, filename):
        self.spool, self.owner_id = spool, owner_id
        size = spool.tell()
        spool.seek(0)

        async def chunks():
            while chunk := spool.read(64 * 1024):
                yield chunk
                await asyncio.sleep(0)

        super().__init__(chunks(), media_type='application/json', headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(size),
            'Cache-Control': 'private, no-store',
            'X-Content-Type-Options': 'nosniff',
        })

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.spool.close()
            active_exports.discard(self.owner_id)


def columns(model, names):
    # Explicit allowlists keep future model fields out of existing export schemas.
    return [getattr(model, name) for name in names.split()]


def queries(owner_id):
    repos = select(Repository.id).where(Repository.owner_id == owner_id)
    files = select(File.id).where(File.repository_id.in_(repos))
    conversations = select(Conversation.id).where(Conversation.repository_id.in_(repos))
    specs = [
        ('repositories', Repository, 'id name source_type source_url status total_files processed_files total_chunks total_loc languages created_at updated_at', Repository.id.in_(repos)),
        ('files', File, 'id repository_id path language extension size loc hash num_classes num_functions imports complexity_score importance_score importance_level summary created_at', File.repository_id.in_(repos)),
        ('symbols', Symbol, 'id file_id name type start_line end_line parent_name signature docstring complexity', Symbol.file_id.in_(files)),
        ('analysis_issues', AnalysisIssue, 'id repository_id file_id issue_type severity message line suggestion created_at', AnalysisIssue.repository_id.in_(repos)),
        ('analysis_runs', RepositoryJob, 'id repository_id status progress message created_at updated_at', RepositoryJob.repository_id.in_(repos) & (RepositoryJob.job_type == 'ANALYSIS')),
        ('summaries', RepositorySummary, 'id repository_id summary_type target_path content created_at updated_at', RepositorySummary.repository_id.in_(repos)),
        ('conversations', Conversation, 'id repository_id title created_at updated_at', Conversation.repository_id.in_(repos)),
        ('messages', Message, 'id conversation_id role content sources created_at', Message.conversation_id.in_(conversations)),
        ('usage_history', AnalysisAdmission, 'repository_id status created_at', AnalysisAdmission.owner_id == owner_id),
    ]
    for name, model, names, condition in specs:
        key = model.repository_id if model is AnalysisAdmission else model.id
        yield name, select(*columns(model, names)).where(condition).order_by(key)


def normalize(name, row):
    result = dict(row)
    for key in ('languages', 'imports', 'sources'):
        if key in result:
            try:
                result[key] = json.loads(result[key]) if result[key] else None
            except (ValueError, TypeError):
                pass  # Preserve older stored text verbatim rather than discard user data.
    if name == 'analysis_runs':
        raw = result.pop('message')
        try:
            coverage = json.loads(raw) if raw else None
        except (ValueError, TypeError):
            coverage = None
        # Analysis messages can contain internal progress/cache diagnostics.
        allowed = ('scanned_files', 'scanned_loc', 'excluded_files', 'exclusions',
                   'python_files_scanned', 'compiled_files_scanned', 'notebook_cells_scanned',
                   'notebook_cells_skipped', 'notebooks_scanned', 'json_files_validated', 'unsupported_files')
        result['coverage'] = {k: coverage[k] for k in allowed if k in coverage} if isinstance(coverage, dict) else None
    return result


def json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()  # Database timestamps retain their stored timezone.
    raise TypeError(f'Unsupported export value: {type(value).__name__}')


async def build_export(user):
    if user.id in active_exports or len(active_exports) >= 2:
        raise HTTPException(429, 'An export is already running or the server is busy. Try again shortly.', headers={'Retry-After': '10'})
    retry = limiter.check(user.id, 3, 600)
    if retry:
        raise HTTPException(429, 'Please wait before downloading another export.', headers={'Retry-After': str(retry)})
    active_exports.add(user.id)
    spool = None
    try:
        spool = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, default=json_default, separators=(',', ':'))

        def write(value):
            encoded = value.encode('utf-8')
            if spool.tell() + len(encoded) > MAX_BYTES:
                raise HTTPException(413, 'Your export exceeds the 25 MiB download limit. Contact support for a larger export; no partial export was created.')
            spool.write(encoded)

        def encode(value):
            for part in encoder.iterencode(value):
                write(part)

        now = datetime.now(timezone.utc)
        counts = {}
        async with asyncio.timeout(60), AsyncSessionLocal() as db:
            # One stable, read-only view across all tables, including concurrent chats.
            if db.bind.dialect.name == 'postgresql':
                await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            else:
                await db.execute(text('BEGIN'))
            write('{"schema_version":1,"exported_at":')
            encode(now)
            write(',"account":')
            encode({'id': user.id, 'email': user.email})
            write(',"usage":')
            encode(await usage(db, user.id))
            total = 0
            for name, query in queries(user.id):
                write(',' + json.dumps(name) + ':[')
                count = 0
                result = await db.stream(query.execution_options(yield_per=50))
                try:
                    async for row in result.mappings():
                        total += 1
                        if total > MAX_ROWS:
                            raise HTTPException(413, 'Your export exceeds the row limit. Contact support for a larger export; no partial export was created.')
                        if count:
                            write(',')
                        encode(normalize(name, row))
                        count += 1
                        if count % 50 == 0:
                            await asyncio.sleep(0)
                finally:
                    await result.close()
                counts[name] = count
                write(']')
            write(',"manifest":')
            encode({'row_counts': counts, 'included': list(counts),
                    'excluded': ['source_file_archives', 'code_chunks', 'vector_indexes', 'authentication_secrets', 'server_logs'],
                    'notes': 'Saved data snapshot, not a restorable backup. IDs link records across arrays. Chats, summaries, signatures and findings may contain source excerpts. In-progress work may not yet be saved. No AI generation or analysis credit used.'})
            write('}')
        return ExportResponse(spool, user.id, now.strftime('codelens-data-%Y%m%dT%H%M%SZ.json'))
    except BaseException as exc:
        if spool is not None:
            spool.close()
        active_exports.discard(user.id)
        if isinstance(exc, TimeoutError):
            raise HTTPException(503, 'Export preparation timed out. Please try again later.') from exc
        if isinstance(exc, (HTTPException, asyncio.CancelledError)):
            raise
        if not isinstance(exc, Exception):
            raise
        raise HTTPException(503, 'Unable to prepare your export. Please try again later.') from exc
