import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import AsyncSessionLocal
from app.services.repository_service import (
    process_zip_upload,
    process_github_url
)

# Avoid loading/embedding multiple repositories at once on a small CPU host.
ingestion_lock = asyncio.Lock()

async def run_zip_ingestion(repo_id: str, zip_path: str):
    async with ingestion_lock, AsyncSessionLocal() as db:
        await process_zip_upload(db, repo_id, zip_path)

async def run_github_ingestion(repo_id: str, github_url: str, revision: str = None):
    async with ingestion_lock, AsyncSessionLocal() as db:
        await process_github_url(db, repo_id, github_url, revision)

def start_zip_ingestion(repo_id: str, zip_path: str):
    asyncio.create_task(run_zip_ingestion(repo_id, zip_path))

def start_github_ingestion(repo_id: str, github_url: str, revision: str = None):
    asyncio.create_task(run_github_ingestion(repo_id, github_url))
