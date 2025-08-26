"""FastAPI application for the ingestion system."""

import json
import logging
import os

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..domain.models import BatchIngestionResponse, DocumentType, IngestionRequest
from ..infrastructure.database import (
    create_storage_directories,
    get_db_session,
    init_database,
)
from ..infrastructure.marker_processor import MarkerPDFProcessor
from ..infrastructure.repository import SQLAlchemyDocumentRepository
from ..infrastructure.storage import LocalFileStorage
from .ingestion_service import IngestionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ingest.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Bionocular Ingestion API",
    description="API for ingesting scientific PDFs about melanoma treatments",
    version="0.1.0",
)


def get_ingestion_service(db: Session = Depends(get_db_session)) -> IngestionService:
    """Dependency to get the ingestion service."""
    storage = LocalFileStorage()
    repository = SQLAlchemyDocumentRepository(db)

    # Use Marker processor for superior accuracy
    use_llm = os.getenv("MARKER_USE_LLM", "false").lower() == "true"
    extract_images = os.getenv("MARKER_EXTRACT_IMAGES", "true").lower() == "true"

    pdf_processor = MarkerPDFProcessor(use_llm=use_llm, extract_images=extract_images)

    return IngestionService(storage, repository, pdf_processor)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize the application on startup."""
    try:
        # Initialize database
        init_database()
        logger.info("Database initialized successfully")

        # Create storage directories
        create_storage_directories()
        logger.info("Storage directories created successfully")

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Bionocular Ingestion API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "upload": "/ingest",
            "local_file": "/ingest/local",
            "batch_upload": "/ingest/batch",
            "local_batch": "/ingest/local/batch",
            "stats": "/stats",
            "documents": "/documents",
        },
    }


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/ingest", response_model=dict)
async def ingest_document(
    file: UploadFile = File(..., description="PDF file to ingest"),
    document_type: DocumentType = Form(..., description="Type of document"),
    metadata: str = Form("{}", description="Additional metadata as JSON string"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    """Ingest a PDF document from file upload."""
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await file.read()

        # Parse metadata
        try:
            parsed_metadata = json.loads(metadata) if metadata else {}
        except json.JSONDecodeError:
            parsed_metadata = {}

        # Create ingestion request
        request = IngestionRequest(type=document_type, metadata=parsed_metadata)

        # Process document
        response = await ingestion_service.ingest_single_document(
            file_content, file.filename or "unknown.pdf", request
        )

        logger.info(f"Successfully ingested uploaded document: {file.filename}")

        return {
            "success": True,
            "document": response.dict(),
            "message": "Document ingested successfully",
            "source": "upload",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting uploaded document {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.post("/ingest/local", response_model=dict)
async def ingest_local_document(
    file_path: str = Form(..., description="Path to local PDF file"),
    document_type: DocumentType = Form(..., description="Type of document"),
    metadata: str = Form("{}", description="Additional metadata as JSON string"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    """Ingest a PDF document from local file path."""
    try:
        # Validate file path
        if not os.path.exists(file_path):
            raise HTTPException(status_code=400, detail=f"File not found: {file_path}")

        if not file_path.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Parse metadata
        try:
            parsed_metadata = json.loads(metadata) if metadata else {}
        except json.JSONDecodeError:
            parsed_metadata = {}

        # Add source information to metadata
        parsed_metadata.update({"source_path": file_path, "source_type": "local_file"})

        # Create ingestion request
        request = IngestionRequest(type=document_type, metadata=parsed_metadata)

        # Process document
        response = await ingestion_service.ingest_single_document(
            file_content, os.path.basename(file_path), request
        )

        logger.info(f"Successfully ingested local document: {file_path}")

        return {
            "success": True,
            "document": response.dict(),
            "message": "Local document ingested successfully",
            "source": "local_file",
            "file_path": file_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting local document {file_path}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.post("/ingest/batch", response_model=dict)
async def ingest_batch_documents(
    file: UploadFile = File(..., description="Batch PDF file to ingest"),
    document_type: DocumentType = Form(..., description="Type of documents"),
    metadata: str = Form("{}", description="Additional metadata as JSON string"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    """Ingest multiple documents from a batch PDF upload."""
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await file.read()

        # Parse metadata
        try:
            parsed_metadata = json.loads(metadata) if metadata else {}
        except json.JSONDecodeError:
            parsed_metadata = {}

        # Create ingestion request
        request = IngestionRequest(type=document_type, metadata=parsed_metadata)

        # Process batch documents
        responses = await ingestion_service.ingest_batch_documents(
            file_content, file.filename or "unknown.pdf", request
        )

        # Calculate statistics
        total_processed = len(responses)
        successful = len([r for r in responses if r.status.value == "ingested"])
        failed = len([r for r in responses if r.status.value == "processing_failed"])
        duplicates = len([r for r in responses if r.is_duplicate])

        logger.info(
            f"Successfully processed uploaded batch: {total_processed} documents, {successful} successful, {failed} failed"
        )

        return BatchIngestionResponse(
            total_processed=total_processed,
            successful=successful,
            failed=failed,
            duplicates=duplicates,
            documents=responses,
        ).dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error ingesting uploaded batch documents from {file.filename}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.post("/ingest/local/batch", response_model=dict)
async def ingest_local_batch_documents(
    file_path: str = Form(..., description="Path to local batch PDF file"),
    document_type: DocumentType = Form(..., description="Type of documents"),
    metadata: str = Form("{}", description="Additional metadata as JSON string"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    """Ingest multiple documents from a local batch PDF file."""
    try:
        # Validate file path
        if not os.path.exists(file_path):
            raise HTTPException(status_code=400, detail=f"File not found: {file_path}")

        if not file_path.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Parse metadata
        try:
            parsed_metadata = json.loads(metadata) if metadata else {}
        except json.JSONDecodeError:
            parsed_metadata = {}

        # Add source information to metadata
        parsed_metadata.update(
            {"source_path": file_path, "source_type": "local_batch_file"}
        )

        # Create ingestion request
        request = IngestionRequest(type=document_type, metadata=parsed_metadata)

        # Process batch documents
        responses = await ingestion_service.ingest_batch_documents(
            file_content, os.path.basename(file_path), request
        )

        # Calculate statistics
        total_processed = len(responses)
        successful = len([r for r in responses if r.status.value == "ingested"])
        failed = len([r for r in responses if r.status.value == "processing_failed"])
        duplicates = len([r for r in responses if r.is_duplicate])

        logger.info(
            f"Successfully processed local batch: {total_processed} documents, {successful} successful, {failed} failed"
        )

        return BatchIngestionResponse(
            total_processed=total_processed,
            successful=successful,
            failed=failed,
            duplicates=duplicates,
            documents=responses,
        ).dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error ingesting local batch documents from {file_path}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.post("/ingest/directory")
async def ingest_directory(
    directory_path: str = Form(..., description="Path to directory containing PDFs"),
    document_type: DocumentType = Form(..., description="Type of documents"),
    recursive: bool = Form(False, description="Process subdirectories recursively"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    """Ingest all PDF files from a directory."""
    try:
        # Validate directory path
        if not os.path.exists(directory_path):
            raise HTTPException(
                status_code=400, detail=f"Directory not found: {directory_path}"
            )

        if not os.path.isdir(directory_path):
            raise HTTPException(
                status_code=400, detail=f"Path is not a directory: {directory_path}"
            )

        # Find all PDF files
        pdf_files = []
        if recursive:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if file.lower().endswith(".pdf"):
                        pdf_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(directory_path):
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(directory_path, file))

        if not pdf_files:
            return {
                "message": "No PDF files found in directory",
                "directory": directory_path,
                "files_processed": 0,
            }

        # Process each PDF file
        results = []
        for pdf_file in pdf_files:
            try:
                # Read file content
                with open(pdf_file, "rb") as f:
                    file_content = f.read()

                # Create metadata
                metadata = {
                    "source_path": pdf_file,
                    "source_type": "directory_scan",
                    "directory": directory_path,
                }

                # Create ingestion request
                request = IngestionRequest(type=document_type, metadata=metadata)

                # Process document
                response = await ingestion_service.ingest_single_document(
                    file_content, os.path.basename(pdf_file), request
                )

                results.append(
                    {"file": pdf_file, "success": True, "response": response.dict()}
                )

            except Exception as e:
                results.append({"file": pdf_file, "success": False, "error": str(e)})

        successful = len([r for r in results if r["success"]])
        failed = len([r for r in results if not r["success"]])

        logger.info(
            f"Directory processing complete: {successful} successful, {failed} failed"
        )

        return {
            "message": "Directory processing complete",
            "directory": directory_path,
            "total_files": len(pdf_files),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing directory {directory_path}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/stats")
async def get_stats(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    """Get ingestion system statistics."""
    try:
        stats = await ingestion_service.get_ingestion_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/documents")
async def list_documents(
    limit: int = 100, offset: int = 0, db: Session = Depends(get_db_session)
) -> dict:
    """List ingested documents with pagination."""
    try:
        repository = SQLAlchemyDocumentRepository(db)
        documents = await repository.get_all_documents(limit=limit, offset=offset)

        return {
            "documents": [doc.dict() for doc in documents],
            "total": len(documents),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/documents/{document_id}")
async def get_document(document_id: str, db: Session = Depends(get_db_session)) -> dict:
    """Get a specific document by ID."""
    try:
        repository = SQLAlchemyDocumentRepository(db)
        document = await repository.find_by_id(document_id)

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        return document.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/filesystem")
async def get_filesystem_info() -> dict:
    """Get information about the filesystem structure."""
    try:
        data_dirs = {
            "abstracts": "./data/abstracts",
            "publications": "./data/publications",
            "processed": "./data/processed",
        }

        storage_dirs = {
            "storage": "./storage",
            "abstracts": "./storage/abstracts",
            "publications": "./storage/publications",
        }

        # Count files in each directory
        files_info = {}
        for name, path in {**data_dirs, **storage_dirs}.items():
            try:
                if os.path.exists(path):
                    file_count = len(
                        [f for f in os.listdir(path) if f.lower().endswith(".pdf")]
                    )
                    files_info[name] = {
                        "path": path,
                        "exists": True,
                        "pdf_count": file_count,
                    }
                else:
                    files_info[name] = {"path": path, "exists": False, "pdf_count": 0}
            except Exception as e:
                files_info[name] = {"path": path, "exists": False, "error": str(e)}

        return {
            "filesystem_info": files_info,
            "usage_instructions": {
                "place_pdfs_here": "Put PDFs in data/abstracts or data/publications",
                "processed_files": "Processed files are stored in storage/abstracts and storage/publications",
                "api_endpoints": {
                    "local_file": "/ingest/local",
                    "local_batch": "/ingest/local/batch",
                    "directory": "/ingest/directory",
                },
            },
        }

    except Exception as e:
        logger.error(f"Error getting filesystem info: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
