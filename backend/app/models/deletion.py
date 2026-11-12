from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.database.base import Base


class AccountDeletion(Base):
    __tablename__ = 'account_deletions'
    owner_id = Column(String, primary_key=True)
    repository_ids = Column(Text, nullable=False)
    phase = Column(String, nullable=False, default='DATA')
    created_at = Column(DateTime, server_default=func.now())
