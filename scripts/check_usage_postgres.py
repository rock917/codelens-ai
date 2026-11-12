"""Run only in the isolated codelens-backup-check container network.

Uses a disposable codelens_usage_check database, never a production URL.
Mount backend/migrations read-only at /migrations.
"""
import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0, '/app')
os.environ.update(DATABASE_URL='postgresql+asyncpg://postgres@127.0.0.1/codelens_usage_check',
                  SUPABASE_URL='https://auth.test', SUPABASE_PUBLISHABLE_KEY='test',
                  GROQ_API_KEY='test', DEBUG='false')
from fastapi import HTTPException
from sqlalchemy import select, func, delete
from app.database.base import engine, Base, AsyncSessionLocal, init_db
from app.models import repository, conversation, summary, usage
from app.models.repository import Repository
from app.models.usage import AnalysisAdmission
from app.services.admission_service import admit, usage as allowance
from app.services.repository_service import update_repository_status


async def migration(name):
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute(Path('/migrations', name).read_text())


async def request(key):
    async with AsyncSessionLocal() as db:
        try:
            repo, reused = await admit(db, 'concurrency-test', key, 'zip', key, key)
            return repo.id, reused
        except HTTPException as exc:
            assert exc.status_code == 409
            return None, False


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Repository)) == 0, 'Use a fresh disposable database'
        for state in ('READY', 'FAILED', 'UPLOADING'):
            db.add(Repository(id='fixture-' + state, name='fixture', owner_id='migration-test',
                              source_type='zip', status=state))
        await db.commit()
    await migration('001_private_accounts.sql')
    await migration('002_analysis_usage.sql')
    await migration('002_analysis_usage.sql')
    await init_db()  # Checks RLS and anonymous/authenticated grants on every table.
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(AnalysisAdmission)) == 3
        assert await allowance(db, 'migration-test') == dict(limit=10, used=1, reserved=1, remaining=8)
    duplicates = await asyncio.gather(*(request('same') for _ in range(8)))
    assert len({row[0] for row in duplicates}) == 1
    assert sum(not row[1] for row in duplicates) == 1
    results = await asyncio.gather(*(request(str(n)) for n in range(15)))
    assert sum(row[0] is None for row in results) == 6
    completed_id = duplicates[0][0]
    async with AsyncSessionLocal() as db:
        await update_repository_status(db, completed_id, 'READY')
        assert await allowance(db, 'concurrency-test') == dict(limit=10, used=1, reserved=9, remaining=0)
    assert (await request('same')) == (completed_id, True)  # Cache works at the cap.
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Repository).where(Repository.id == completed_id))
        await db.commit()
    assert (await request('same'))[0] is None  # Deletion does not refund.
    failure_id = next(row[0] for row in results if row[0])
    async with AsyncSessionLocal() as db:
        await update_repository_status(db, failure_id, 'FAILED')
    await engine.dispose()
    assert (await request('replacement'))[0] is not None
    async with AsyncSessionLocal() as db:
        assert (await allowance(db, 'concurrency-test'))['remaining'] == 0
        other, reused = await admit(db, 'other-test', 'same', 'zip', 'same', 'same')
        assert other.id != completed_id and not reused
    await engine.dispose()
    print('PostgreSQL passed: migration idempotency, private grants, backfill, concurrent cap, duplicate cache, failures, deletion, account isolation.')


asyncio.run(main())
