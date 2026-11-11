from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config.settings import settings
from sqlalchemy import update

def get_engine():
    database_url = settings.DATABASE_URL

    # Convert postgres:// to postgresql+asyncpg://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+asyncpg://", 1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )

    # SQLite config
    if "sqlite" in database_url:
        return create_async_engine(
            database_url,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False}
        )

    # PostgreSQL config
    return create_async_engine(
        database_url,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )

engine = get_engine()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    async with engine.begin() as conn:
        from app.models import repository, conversation, summary
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database initialized")


async def recover_interrupted_jobs():
    """Called before serving requests, on a single-worker/single-instance host."""
    from app.models.repository import Repository, RepositoryStatus
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Repository)
            .where(Repository.status.in_([
                RepositoryStatus.UPLOADING, RepositoryStatus.PARSING,
                RepositoryStatus.INDEXING, RepositoryStatus.ANALYZING,
            ]))
            .values(
                status=RepositoryStatus.FAILED,
                error_message='Processing was interrupted by a server restart. Please upload or clone the repository again.',
            )
        )
        await db.commit()
