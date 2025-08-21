"""Database models and configuration for the ingestion system."""

import os

from sqlalchemy import Column, DateTime, Enum, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

from ..domain.models import DocumentStatus, DocumentType

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:pass@localhost:5432/bionocular"
)
STORAGE_DIR = os.getenv("STORAGE_DIR", "./storage")

# Create database engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()  # type: ignore


class DocumentModel(Base):
    """SQLAlchemy model for documents table."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    type = Column(Enum(DocumentType), nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    hash = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.INGESTED)
    metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


def get_db_session() -> None:
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def create_storage_directories() -> None:
    """Create necessary storage directories if they don't exist."""
    os.makedirs(os.path.join(STORAGE_DIR, "originals"), exist_ok=True)
    os.makedirs(os.path.join(STORAGE_DIR, "abstracts"), exist_ok=True)
    os.makedirs(os.path.join(STORAGE_DIR, "publications"), exist_ok=True)
