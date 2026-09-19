from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.database.base import Base

class RepositorySummary(Base):
    __tablename__ = "repository_summaries"

    id = Column(String, primary_key=True)
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    summary_type = Column(String, nullable=False)  # repository, module, file
    target_path = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())