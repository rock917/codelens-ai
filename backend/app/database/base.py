from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config.settings import settings
from sqlalchemy import update, inspect, text

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
        columns = await conn.run_sync(lambda sync: inspect(sync).get_columns('repositories'))
        if 'owner_id' not in {column['name'] for column in columns}:
            raise RuntimeError('Apply backend/migrations/001_private_accounts.sql before starting this release')
        if conn.dialect.name == 'postgresql':
            # Refuse to serve if Supabase clients could bypass API ownership checks.
            for table_name in Base.metadata.tables:
                safe = await conn.scalar(text("""
                    SELECT c.relrowsecurity
                      AND NOT has_table_privilege('anon', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                      AND NOT has_table_privilege('authenticated', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = :name
                """), {'name': table_name})
                if not safe:
                    raise RuntimeError('Apply backend/migrations/001_private_accounts.sql: app tables must be private')
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
