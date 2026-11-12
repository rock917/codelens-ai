"""Run inside the deployed backend container after migration 002.

Reads only Git metadata from existing checkouts, never dotenv files or source files.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, '/app')
import git
from fastapi import HTTPException
from sqlalchemy import select
from app.database.base import AsyncSessionLocal, engine
from app.config.settings import settings
from app.models.repository import Repository
from app.models import conversation, summary
from app.models.usage import AnalysisAdmission
from app.services.admission_service import normalize_url


async def main():
    updated = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Repository, AnalysisAdmission).join(
            AnalysisAdmission, AnalysisAdmission.repository_id == Repository.id).where(
            Repository.source_type == 'github', Repository.status == 'READY',
            AnalysisAdmission.revision.startswith('legacy:'),
        ))).all()
        for repo, admission in rows:
            directory = Path(settings.UPLOAD_DIR) / repo.id
            if not directory.resolve().is_relative_to(Path(settings.UPLOAD_DIR).resolve()):
                continue
            try:
                checkout = git.Repo(directory)
                admission.source_key = normalize_url(repo.source_url)
                admission.revision = checkout.head.commit.hexsha
                updated += 1
            except (git.InvalidGitRepositoryError, git.NoSuchPathError, ValueError, HTTPException):
                continue
        await db.commit()
    await engine.dispose()
    print(f'Existing Git revision cache populated: {updated} repositories.')


if __name__ == '__main__':
    asyncio.run(main())
