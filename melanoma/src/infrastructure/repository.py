"""SQLAlchemy-based document repository implementation."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..domain.interfaces import DocumentRepositoryInterface
from ..domain.models import Document, DocumentStatus
from .database import DocumentModel


class SQLAlchemyDocumentRepository(DocumentRepositoryInterface):
    """SQLAlchemy implementation of document repository."""

    def __init__(self, db_session: Session):
        """Initialize repository with database session."""
        self.db = db_session

    async def save_document(self, document: Document) -> Document:
        """Save a document to the database."""
        # Convert domain model to SQLAlchemy model
        db_document = DocumentModel(
            id=document.id,
            original_filename=document.original_filename,
            storage_path=document.storage_path,
            type=document.type,
            upload_date=document.upload_date,
            hash=document.hash,
            status=document.status,
            metadata=document.metadata,
        )

        self.db.add(db_document)
        self.db.commit()
        self.db.refresh(db_document)

        # Convert back to domain model
        return Document(
            id=db_document.id,  # type: ignore
            original_filename=db_document.original_filename,  # type: ignore
            storage_path=db_document.storage_path,  # type: ignore
            type=db_document.doc_type,  # type: ignore
            upload_date=db_document.upload_date,  # type: ignore
            hash=db_document.hash,  # type: ignore
            status=db_document.doc_status,  # type: ignore
            metadata=db_document.metadata or {},  # type: ignore
        )

    async def find_by_hash(self, content_hash: str) -> Optional[Document]:
        """Find a document by its content hash."""
        db_document = (
            self.db.query(DocumentModel)
            .filter(DocumentModel.hash == content_hash)
            .first()
        )

        if not db_document:
            return None

        return Document(
            id=db_document.id,  # type: ignore
            original_filename=db_document.original_filename,  # type: ignore
            storage_path=db_document.storage_path,  # type: ignore
            type=db_document.doc_type,  # type: ignore
            upload_date=db_document.upload_date,  # type: ignore
            hash=db_document.hash,  # type: ignore
            status=db_document.doc_status,  # type: ignore
            metadata=db_document.metadata or {},  # type: ignore
        )

    async def find_by_id(self, document_id: str) -> Optional[Document]:
        """Find a document by its ID."""
        try:
            uuid_id = UUID(document_id)
        except ValueError:
            return None

        db_document = (
            self.db.query(DocumentModel).filter(DocumentModel.id == uuid_id).first()
        )

        if not db_document:
            return None

        return Document(
            id=db_document.id,  # type: ignore
            original_filename=db_document.original_filename,  # type: ignore
            storage_path=db_document.storage_path,  # type: ignore
            type=db_document.doc_type,  # type: ignore
            upload_date=db_document.upload_date,  # type: ignore
            hash=db_document.hash,  # type: ignore
            status=db_document.doc_status,  # type: ignore
            metadata=db_document.metadata or {},  # type: ignore
        )

    async def update_status(self, document_id: UUID, status: DocumentStatus) -> bool:
        """Update document status."""
        try:
            db_document = (
                self.db.query(DocumentModel)
                .filter(DocumentModel.id == document_id)
                .first()
            )

            if not db_document:
                return False

            db_document.doc_status = status  # type: ignore
            self.db.commit()
            return True

        except Exception:
            self.db.rollback()
            return False

    async def get_all_documents(
        self, limit: int = 100, offset: int = 0
    ) -> list[Document]:
        """Get all documents with pagination."""
        db_documents = self.db.query(DocumentModel).limit(limit).offset(offset).all()

        return [
            Document(
                id=doc.id,  # type: ignore
                original_filename=doc.original_filename,  # type: ignore
                storage_path=doc.storage_path,  # type: ignore
                type=doc.doc_type,  # type: ignore
                upload_date=doc.upload_date,  # type: ignore
                hash=doc.hash,  # type: ignore
                status=doc.doc_status,  # type: ignore
                metadata=doc.metadata or {},  # type: ignore
            )
            for doc in db_documents
        ]
