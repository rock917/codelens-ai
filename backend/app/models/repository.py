from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base
import enum

class RepositoryStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    PARSING = "PARSING"
    INDEXING = "INDEXING"
    ANALYZING = "ANALYZING"
    READY = "READY"
    FAILED = "FAILED"

class ImportanceLevel(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # zip or github
    source_url = Column(String, nullable=True)
    status = Column(String, default=RepositoryStatus.UPLOADING)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    total_loc = Column(Integer, default=0)
    languages = Column(Text, default="")  # JSON string
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    files = relationship("File", back_populates="repository", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="repository", cascade="all, delete-orphan")
    issues = relationship("AnalysisIssue", back_populates="repository", cascade="all, delete-orphan")
    jobs = relationship("RepositoryJob", back_populates="repository", cascade="all, delete-orphan")

class File(Base):
    __tablename__ = "files"

    id = Column(String, primary_key=True)
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    path = Column(String, nullable=False)
    language = Column(String, nullable=True)
    extension = Column(String, nullable=True)
    size = Column(Integer, default=0)
    loc = Column(Integer, default=0)
    hash = Column(String, nullable=True)
    num_classes = Column(Integer, default=0)
    num_functions = Column(Integer, default=0)
    imports = Column(Text, default="")
    complexity_score = Column(Float, default=0.0)
    importance_score = Column(Float, default=0.0)
    importance_level = Column(String, default=ImportanceLevel.LOW)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    repository = relationship("Repository", back_populates="files")
    symbols = relationship("Symbol", back_populates="file", cascade="all, delete-orphan")
    chunks = relationship("CodeChunk", back_populates="file", cascade="all, delete-orphan")
    issues = relationship("AnalysisIssue", back_populates="file")

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(String, primary_key=True)
    file_id = Column(String, ForeignKey("files.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # function, class, method
    start_line = Column(Integer, default=0)
    end_line = Column(Integer, default=0)
    parent_name = Column(String, nullable=True)
    signature = Column(Text, nullable=True)
    docstring = Column(Text, nullable=True)
    complexity = Column(Float, default=0.0)

    file = relationship("File", back_populates="symbols")

class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(String, primary_key=True)
    file_id = Column(String, ForeignKey("files.id"), nullable=False)
    repository_id = Column(String, nullable=False)
    symbol_name = Column(String, nullable=True)
    symbol_type = Column(String, nullable=True)
    language = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    start_line = Column(Integer, default=0)
    end_line = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0)
    chroma_id = Column(String, nullable=True)

    file = relationship("File", back_populates="chunks")

class AnalysisIssue(Base):
    __tablename__ = "analysis_issues"

    id = Column(String, primary_key=True)
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    file_id = Column(String, ForeignKey("files.id"), nullable=True)
    issue_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    message = Column(Text, nullable=False)
    line = Column(Integer, nullable=True)
    suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    repository = relationship("Repository", back_populates="issues")
    file = relationship("File", back_populates="issues")

class RepositoryJob(Base):
    __tablename__ = "repository_jobs"

    id = Column(String, primary_key=True)
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    job_type = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    progress = Column(Float, default=0.0)
    message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    repository = relationship("Repository", back_populates="jobs")