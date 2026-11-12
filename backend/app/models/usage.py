from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.sql import func
from app.database.base import Base


class AccountUsage(Base):
    __tablename__ = 'account_usage'
    owner_id = Column(String, primary_key=True)


class AnalysisAdmission(Base):
    __tablename__ = 'analysis_admissions'
    # Deliberately not a foreign key: deleting a repo must not erase usage.
    repository_id = Column(String, primary_key=True)
    owner_id = Column(String, nullable=False, index=True)
    source_key = Column(String, nullable=False)
    revision = Column(String, nullable=False)
    status = Column(String, nullable=False)  # RESERVED, COMPLETED, FAILED
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (Index('ix_admission_cache', 'owner_id', 'source_key', 'revision'),)
