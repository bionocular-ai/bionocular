"""Tests for the ingestion domain models."""

from datetime import datetime
from uuid import uuid4

from src.domain.models import (
    BatchIngestionResponse,
    Document,
    DocumentStatus,
    DocumentType,
    IngestionRequest,
    IngestionResponse,
)


class TestDocumentType:
    """Test DocumentType enum."""

    def test_document_type_values(self):
        """Test that DocumentType has correct values."""
        assert DocumentType.ABSTRACT == "abstract"
        assert DocumentType.PUBLICATION == "publication"

    def test_document_type_choices(self):
        """Test that DocumentType choices are valid."""
        choices = [choice.value for choice in DocumentType]
        assert "abstract" in choices
        assert "publication" in choices


class TestDocumentStatus:
    """Test DocumentStatus enum."""

    def test_document_status_values(self):
        """Test that DocumentStatus has correct values."""
        assert DocumentStatus.INGESTED == "ingested"
        assert DocumentStatus.PROCESSING_FAILED == "processing_failed"

    def test_document_status_choices(self):
        """Test that DocumentStatus choices are valid."""
        choices = [choice.value for choice in DocumentStatus]
        assert "ingested" in choices
        assert "processing_failed" in choices


class TestDocument:
    """Test Document model."""

    def test_document_creation(self):
        """Test creating a Document instance."""
        doc = Document(
            original_filename="test.pdf",
            storage_path="/storage/test.pdf",
            type=DocumentType.ABSTRACT,
            hash="abc123",
        )

        assert doc.original_filename == "test.pdf"
        assert doc.storage_path == "/storage/test.pdf"
        assert doc.type == DocumentType.ABSTRACT
        assert doc.hash == "abc123"
        assert doc.status == DocumentStatus.INGESTED
        assert isinstance(doc.id, uuid4().__class__)
        assert isinstance(doc.upload_date, datetime)
        assert doc.metadata == {}

    def test_document_with_custom_values(self):
        """Test creating a Document with custom values."""
        custom_id = uuid4()
        custom_date = datetime(2024, 1, 1)
        custom_metadata = {"source": "test", "version": "1.0"}

        doc = Document(
            id=custom_id,
            original_filename="custom.pdf",
            storage_path="/storage/custom.pdf",
            type=DocumentType.PUBLICATION,
            upload_date=custom_date,
            hash="def456",
            status=DocumentStatus.PROCESSING_FAILED,
            metadata=custom_metadata,
        )

        assert doc.id == custom_id
        assert doc.upload_date == custom_date
        assert doc.metadata == custom_metadata
        assert doc.status == DocumentStatus.PROCESSING_FAILED

    def test_document_serialization(self):
        """Test Document serialization to dict."""
        doc = Document(
            original_filename="test.pdf",
            storage_path="/storage/test.pdf",
            type=DocumentType.ABSTRACT,
            hash="abc123",
        )

        doc_dict = doc.model_dump()

        assert "id" in doc_dict
        assert "original_filename" in doc_dict
        assert "storage_path" in doc_dict
        assert "type" in doc_dict
        assert "hash" in doc_dict
        assert "status" in doc_dict
        assert "metadata" in doc_dict


class TestIngestionRequest:
    """Test IngestionRequest model."""

    def test_ingestion_request_creation(self):
        """Test creating an IngestionRequest instance."""
        request = IngestionRequest(
            type=DocumentType.ABSTRACT, metadata={"source": "test"}
        )

        assert request.type == DocumentType.ABSTRACT
        assert request.metadata == {"source": "test"}

    def test_ingestion_request_defaults(self):
        """Test IngestionRequest default values."""
        request = IngestionRequest(type=DocumentType.PUBLICATION)

        assert request.type == DocumentType.PUBLICATION
        assert request.metadata == {}


class TestIngestionResponse:
    """Test IngestionResponse model."""

    def test_ingestion_response_creation(self):
        """Test creating an IngestionResponse instance."""
        doc_id = uuid4()
        response = IngestionResponse(
            document_id=doc_id,
            original_filename="test.pdf",
            storage_path="/storage/test.pdf",
            type=DocumentType.ABSTRACT,
            status=DocumentStatus.INGESTED,
            message="Success",
            is_duplicate=False,
        )

        assert response.document_id == doc_id
        assert response.original_filename == "test.pdf"
        assert response.storage_path == "/storage/test.pdf"
        assert response.type == DocumentType.ABSTRACT
        assert response.status == DocumentStatus.INGESTED
        assert response.message == "Success"
        assert response.is_duplicate is False

    def test_ingestion_response_defaults(self):
        """Test IngestionResponse default values."""
        doc_id = uuid4()
        response = IngestionResponse(
            document_id=doc_id,
            original_filename="test.pdf",
            storage_path="/storage/test.pdf",
            type=DocumentType.ABSTRACT,
            status=DocumentStatus.INGESTED,
            message="Success",
        )

        assert response.is_duplicate is False


class TestBatchIngestionResponse:
    """Test BatchIngestionResponse model."""

    def test_batch_ingestion_response_creation(self):
        """Test creating a BatchIngestionResponse instance."""
        responses = [
            IngestionResponse(
                document_id=uuid4(),
                original_filename="doc1.pdf",
                storage_path="/storage/doc1.pdf",
                type=DocumentType.ABSTRACT,
                status=DocumentStatus.INGESTED,
                message="Success",
            ),
            IngestionResponse(
                document_id=uuid4(),
                original_filename="doc2.pdf",
                storage_path="/storage/doc2.pdf",
                type=DocumentType.ABSTRACT,
                status=DocumentStatus.PROCESSING_FAILED,
                message="Failed",
            ),
        ]

        batch_response = BatchIngestionResponse(
            total_processed=2, successful=1, failed=1, duplicates=0, documents=responses
        )

        assert batch_response.total_processed == 2
        assert batch_response.successful == 1
        assert batch_response.failed == 1
        assert batch_response.duplicates == 0
        assert len(batch_response.documents) == 2
        assert batch_response.errors == []

    def test_batch_ingestion_response_with_errors(self):
        """Test BatchIngestionResponse with error messages."""
        batch_response = BatchIngestionResponse(
            total_processed=1,
            successful=0,
            failed=1,
            duplicates=0,
            documents=[],
            errors=["File corrupted", "Invalid format"],
        )

        assert len(batch_response.errors) == 2
        assert "File corrupted" in batch_response.errors
        assert "Invalid format" in batch_response.errors
