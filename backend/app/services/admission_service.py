"""Lifetime ingestion credits and private, exact-revision cache admission."""
import asyncio
import os
import re
import subprocess
import uuid
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models.repository import Repository
from app.models.usage import AccountUsage, AnalysisAdmission

LIMIT = 10


def normalize_url(value):
    try:
        url = urlsplit(value.strip())
        path = url.path.rstrip('/').removesuffix('.git')
        parts = path.strip('/').split('/')
        if (url.scheme != 'https' or url.hostname not in ('github.com', 'gitlab.com')
                or url.username or url.password or url.port not in (None, 443)
                or url.query or url.fragment or len(parts) < 2
                or (url.hostname == 'github.com' and len(parts) != 2)
                or any(not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', part) or part in ('.', '..') for part in parts)):
            raise ValueError()
        # GitHub paths are case insensitive; GitLab namespaces can be case sensitive.
        path = '/'.join(parts)
        if url.hostname == 'github.com':
            path = path.lower()
        return f'https://{url.hostname}/{path}'
    except ValueError:
        raise HTTPException(400, 'Enter an HTTPS GitHub or GitLab repository root URL.')


async def resolve_revision(url):
    def lookup():
        return subprocess.run(['git', '-c', 'credential.helper=', 'ls-remote', '--', url, 'HEAD'],
                              capture_output=True, text=True, timeout=25, check=True,
                              env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    try:
        result = await asyncio.to_thread(lookup)
        revision = result.stdout.split()[0]
        if not re.fullmatch(r'[0-9a-f]{40,64}', revision):
            raise ValueError()
        return revision
    except (subprocess.SubprocessError, OSError, IndexError, ValueError):
        raise HTTPException(400, 'Cannot read this public repository. Check its URL and try again. No credit was used.')


async def usage(db, owner_id):
    counts = dict((await db.execute(select(AnalysisAdmission.status, func.count()).where(
        AnalysisAdmission.owner_id == owner_id).group_by(AnalysisAdmission.status))).all())
    used, reserved = counts.get('COMPLETED', 0), counts.get('RESERVED', 0)
    return dict(limit=LIMIT, used=used, reserved=reserved, remaining=max(0, LIMIT-used-reserved))


async def admit(db, owner_id, name, source_type, source_key, revision, confirmed_revision=None):
    # INSERT + UPDATE serialize all admissions for this account on PostgreSQL and SQLite.
    # The lock lives until the repository and reservation commit together.
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    await db.execute(insert(AccountUsage).values(owner_id=owner_id).on_conflict_do_nothing())
    await db.execute(update(AccountUsage).where(AccountUsage.owner_id == owner_id).values(owner_id=owner_id))
    cached = await db.scalar(select(Repository).join(
        AnalysisAdmission, AnalysisAdmission.repository_id == Repository.id).where(
        Repository.owner_id == owner_id, AnalysisAdmission.owner_id == owner_id,
        AnalysisAdmission.source_key == source_key, AnalysisAdmission.revision == revision,
        AnalysisAdmission.status.in_(['RESERVED', 'COMPLETED']), Repository.status != 'FAILED',
    ).order_by(AnalysisAdmission.created_at.desc()).limit(1))
    if cached:
        await db.commit()
        return cached, True
    previous = await db.scalar(select(AnalysisAdmission.repository_id).where(
        AnalysisAdmission.owner_id == owner_id, AnalysisAdmission.source_key == source_key,
        AnalysisAdmission.status == 'COMPLETED', AnalysisAdmission.revision != revision,
    ).limit(1))
    if previous and source_type == 'github' and confirmed_revision != revision:
        await db.rollback()
        raise HTTPException(409, dict(code='revision_confirmation', revision=revision,
            message='This repository has a different revision. Analyze it as a new repository using one credit? Existing results and chats will remain.'))
    allowance = await usage(db, owner_id)
    if allowance['remaining'] == 0:
        await db.rollback()
        raise HTTPException(409, dict(code='analysis_limit', message='All 10 lifetime analysis slots are used or reserved. You can still open saved repositories and reuse unchanged results. Failed imports release their slot.', usage=allowance))
    repo = Repository(id=str(uuid.uuid4()), owner_id=owner_id, name=name,
                      source_type=source_type, source_url=source_key if source_type == 'github' else None,
                      status='UPLOADING', languages='{}')
    db.add(repo)
    db.add(AnalysisAdmission(repository_id=repo.id, owner_id=owner_id, source_key=source_key,
                             revision=revision, status='RESERVED'))
    await db.commit()
    return repo, False


async def settle(db, repo_id, status):
    if status in ('READY', 'FAILED'):
        await db.execute(update(AnalysisAdmission).where(
            AnalysisAdmission.repository_id == repo_id, AnalysisAdmission.status == 'RESERVED',
        ).values(status='COMPLETED' if status == 'READY' else 'FAILED'))
