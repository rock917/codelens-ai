import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import AsyncSessionLocal
from app.services.repository_service import (
    process_zip_upload,
    process_github_url
)

async def run_zip_ingestion(repo_id: str, zip_path: str):
    async with AsyncSessionLocal() as db:
        await process_zip_upload(db, repo_id, zip_path)

async def run_github_ingestion(repo_id: str, github_url: str):
    async with AsyncSessionLocal() as db:
        await process_github_url(db, repo_id, github_url)

def start_zip_ingestion(repo_id: str, zip_path: str):
    asyncio.create_task(run_zip_ingestion(repo_id, zip_path))

def start_github_ingestion(repo_id: str, github_url: str):
    asyncio.create_task(run_github_ingestion(repo_id, github_url))