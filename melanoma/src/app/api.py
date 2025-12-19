"""FastAPI application for the ingestion system."""

import json
import logging
import os
import re
import time
from typing import Any

import psutil
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..domain.models import BatchIngestionResponse, DocumentType, IngestionRequest
from ..infrastructure.database import (
    DocumentModel,
    create_storage_directories,
    get_db_session,
    init_database,
)
from ..infrastructure.repository import SQLAlchemyDocumentRepository
from ..infrastructure.storage import LocalFileStorage
from .clinical_api import router as clinical_router
from .ingestion_service import IngestionService
from .json_trials_service import JSONTrialsService
from .langchain_api import router as langchain_router
from .sqlite_trials_service import SQLiteTrialsService
from .trials_api import (
    TrialResponse,
    TrialsListResponse,
    extract_trial_data,
    get_trials_data_source,
)

# Singleton pattern for JSONTrialsService with stats tracking
_json_service_instance: JSONTrialsService | None = None
_sqlite_service_instance: SQLiteTrialsService | None = None
_service_stats = {
    "instance_creations": 0,
    "instance_reuses": 0,
}


def get_json_trials_service() -> JSONTrialsService:
    """Get or create singleton instance of JSONTrialsService."""
    global _json_service_instance, _service_stats
    if _json_service_instance is None:
        _json_service_instance = JSONTrialsService()
        _service_stats["instance_creations"] += 1
    else:
        _service_stats["instance_reuses"] += 1
    return _json_service_instance


def get_sqlite_trials_service() -> SQLiteTrialsService:
    """Get or create singleton instance of SQLiteTrialsService."""
    global _sqlite_service_instance
    if _sqlite_service_instance is None:
        _sqlite_service_instance = SQLiteTrialsService()
    return _sqlite_service_instance


def get_trials_service():
    """Get the appropriate trials service based on data source configuration.

    Returns:
        JSONTrialsService or SQLiteTrialsService instance
    """
    data_source = get_trials_data_source()
    if data_source == "sqlite":
        return get_sqlite_trials_service()
    else:
        return get_json_trials_service()


def get_optional_db_session() -> Session | None:
    """Get database session only if data source is 'database', otherwise return None.

    This allows endpoints to work without PostgreSQL when using SQLite/JSON.

    Note: The session must be closed by the caller. Consider using a context manager.
    """
    data_source = get_trials_data_source()
    if data_source != "database":
        return None

    try:
        db_gen = get_db_session()
        db = next(db_gen)
        # Store the generator to close it later - but for now, we'll let it be garbage collected
        # In production, you might want to use a context manager pattern
        return db
    except Exception as e:
        logger.warning(f"Failed to get database session: {e}")
        return None


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ingest.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Bionocular Melanoma Research API",
    description="API for ingesting and querying scientific PDFs about melanoma treatments with RAG capabilities",
    version="0.2.0",
)

# Configure CORS
# Build allowed origins from environment variable and defaults
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
# Add production origins from environment variable
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins.extend(
        [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Include routers
app.include_router(langchain_router)
app.include_router(clinical_router)


def get_ingestion_service(db: Session = Depends(get_db_session)) -> IngestionService:
    """Dependency to get the ingestion service."""
    storage = LocalFileStorage()
    repository = SQLAlchemyDocumentRepository(db)

    # Check if PDF processing is disabled (for free tier deployments)
    disable_pdf_processing = (
        os.getenv("DISABLE_PDF_PROCESSING", "false").lower() == "true"
    )

    if disable_pdf_processing:
        # Use null processor when PDF processing is disabled
        from ..infrastructure.null_processor import NullPDFProcessor

        logger.info("PDF processing disabled - using NullPDFProcessor")
        pdf_processor = NullPDFProcessor()
    else:
        # Use Marker processor for superior accuracy (requires heavy dependencies)
        # Import lazily to avoid import errors if marker-pdf is not installed
        use_llm = os.getenv("MARKER_USE_LLM", "false").lower() == "true"
        extract_images = os.getenv("MARKER_EXTRACT_IMAGES", "true").lower() == "true"

        try:
            from ..infrastructure.marker_processor import MarkerPDFProcessor

            pdf_processor = MarkerPDFProcessor(
                use_llm=use_llm, extract_images=extract_images
            )
        except ImportError as e:
            logger.warning(
                f"MarkerPDFProcessor not available ({e}). "
                "Falling back to NullPDFProcessor. "
                "Set DISABLE_PDF_PROCESSING=true to suppress this warning."
            )
            from ..infrastructure.null_processor import NullPDFProcessor

            pdf_processor = NullPDFProcessor()

    return IngestionService(storage, repository, pdf_processor)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize the application on startup."""
    try:
        # Only initialize database if we're using it
        data_source = get_trials_data_source()
        if data_source == "database":
            # Initialize database
            init_database()
            logger.info("Database initialized successfully")
        else:
            logger.info(
                f"Using {data_source} data source - skipping database initialization"
            )

        # Create storage directories
        create_storage_directories()
        logger.info("Storage directories created successfully")

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        # Don't raise if we're using JSON files - database errors are not critical
        if get_trials_data_source() == "database":
            raise
        else:
            logger.warning(
                f"Non-critical error during startup (using JSON files): {str(e)}"
            )


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Bionocular Melanoma Research API",
        "version": "0.2.0",
        "status": "running",
        "capabilities": [
            "Document Ingestion",
            "RAG Query Processing",
            "Clinical Data Extraction",
            "Semantic Search",
        ],
        "endpoints": {
            "ingestion": {
                "upload": "/ingest",
                "local_file": "/ingest/local",
                "batch_upload": "/ingest/batch",
                "local_batch": "/ingest/local/batch",
                "stats": "/stats",
                "documents": "/documents",
            },
            "rag": {
                "query": "/langchain/query",
                "clinical": "/langchain/clinical",
                "health": "/langchain/health",
                "info": "/langchain/info",
            },
            "clinical_extraction": {
                "extract": "/clinical/extract",
                "extract_batch": "/clinical/extract/batch",
                "validate": "/clinical/validate",
                "export": "/clinical/export",
                "process_document": "/clinical/process-document",
                "statistics": "/clinical/statistics",
                "health": "/clinical/health",
            },
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


@app.get("/api/trials", response_model=TrialsListResponse)
@app.get(
    "/trials", response_model=TrialsListResponse
)  # Keep both for backward compatibility
async def get_trials(
    skip: int = 0,
    limit: int = 100,
) -> TrialsListResponse:
    """Get all abstract documents (trials) with pagination.

    Returns a clean JSON list of trial objects suitable for frontend consumption.
    Each trial object includes id, nct_id, title, phase, sponsor, and status from metadata.

    Supports both JSON file and database sources. Use TRIALS_DATA_SOURCE environment
    variable to switch between "json" (default) and "database".

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session (used only if data source is "database")

    Returns:
        TrialsListResponse with paginated trial data

    Raises:
        HTTPException: If data source query fails
    """
    try:
        data_source = get_trials_data_source()

        if data_source in ("json", "sqlite"):
            # Use JSON file or SQLite database as data source
            trials_service = get_trials_service()
            trials_list, total = trials_service.get_all_trials(skip=skip, limit=limit)

            return TrialsListResponse(
                trials=[TrialResponse(**trial) for trial in trials_list],
                total=total,
                skip=skip,
                limit=limit,
            )
        else:
            # Use database as data source (original implementation)
            # Query for abstract documents only
            db = get_optional_db_session()
            if db is None:
                # Database not available, fall back to SQLite/JSON
                logger.warning("Database not available, falling back to SQLite/JSON")
                trials_service = get_trials_service()
                trials_list, total = trials_service.get_all_trials(
                    skip=skip, limit=limit
                )
                return TrialsListResponse(
                    trials=[TrialResponse(**trial) for trial in trials_list],
                    total=total,
                    skip=skip,
                    limit=limit,
                )

            try:
                query = (
                    db.query(DocumentModel)
                    .filter(DocumentModel.doc_type == DocumentType.ABSTRACT)
                    .order_by(DocumentModel.created_at.desc())
                )

                # Get total count before pagination
                total = query.count()

                # Apply pagination
                documents = query.offset(skip).limit(limit).all()

                # Format the output using utility function
                trials = [
                    extract_trial_data(
                        doc,
                        doc.doc_metadata if isinstance(doc.doc_metadata, dict) else {},
                    )
                    for doc in documents
                ]

                return TrialsListResponse(
                    trials=[TrialResponse(**trial) for trial in trials],
                    total=total,
                    skip=skip,
                    limit=limit,
                )
            except Exception as db_error:
                # If database connection fails, fall back to SQLite/JSON
                logger.warning(
                    f"Database query failed ({db_error}), falling back to SQLite/JSON"
                )
                trials_service = get_trials_service()
                trials_list, total = trials_service.get_all_trials(
                    skip=skip, limit=limit
                )
                return TrialsListResponse(
                    trials=[TrialResponse(**trial) for trial in trials_list],
                    total=total,
                    skip=skip,
                    limit=limit,
                )
    except Exception as e:
        logger.error(f"Error fetching trials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/api/trials/{trial_id}")
@app.get("/trials/{trial_id}")  # Keep both for backward compatibility
async def get_trial(trial_id: str) -> dict:
    """Get a specific trial by ID with full details."""
    try:
        data_source = get_trials_data_source()

        # If using SQLite/JSON, try to get by abstract_id/publication_id
        if data_source in ("json", "sqlite"):
            trials_service = get_trials_service()
            full_abstract = trials_service.get_full_abstract_by_id(trial_id)
            if full_abstract:
                return full_abstract
            # If not found, fall through to database lookup

        # Use database as data source
        db = get_optional_db_session()
        if db is None:
            # Database not available, already tried SQLite/JSON above
            raise HTTPException(
                status_code=404, detail=f"Trial with ID '{trial_id}' not found"
            )

        try:
            repository = SQLAlchemyDocumentRepository(db)
            document = await repository.find_by_id(trial_id)

            if not document:
                raise HTTPException(status_code=404, detail="Trial not found")

            if document.type != DocumentType.ABSTRACT:
                raise HTTPException(
                    status_code=404, detail="Document is not an abstract"
                )

            # Return full document with metadata
            return document.dict()
        except HTTPException:
            raise
        except Exception as db_error:
            # If database query fails, fall back to SQLite/JSON
            logger.warning(
                f"Database query failed ({db_error}), falling back to SQLite/JSON"
            )
            trials_service = get_trials_service()
            full_abstract = trials_service.get_full_abstract_by_id(trial_id)
            if full_abstract:
                return full_abstract
            raise HTTPException(
                status_code=404, detail=f"Trial with ID '{trial_id}' not found"
            ) from db_error
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trial {trial_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/api/trials/nct/{nct_id}", response_model=TrialsListResponse)
@app.get(
    "/trials/nct/{nct_id}", response_model=TrialsListResponse
)  # Keep both for backward compatibility
async def get_trials_by_nct(
    nct_id: str,
    skip: int = 0,
    limit: int = 100,
) -> TrialsListResponse:
    """Get all abstracts/publications associated with an NCT number.

    Args:
        nct_id: NCT number (e.g., "NCT02388906")
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session (used only if data source is "database")

    Returns:
        TrialsListResponse with paginated trial data

    Raises:
        HTTPException: If data source query fails
    """
    try:
        data_source = get_trials_data_source()

        if data_source in ("json", "sqlite"):
            # Use JSON file or SQLite database as data source
            trials_service = get_trials_service()
            trials_list, total = trials_service.get_trials_by_nct_id(
                nct_id, skip=skip, limit=limit
            )

            return TrialsListResponse(
                trials=[TrialResponse(**trial) for trial in trials_list],
                total=total,
                skip=skip,
                limit=limit,
            )
        else:
            # Use database as data source
            db = get_optional_db_session()
            if db is None:
                # Database not available, fall back to SQLite/JSON
                logger.warning("Database not available, falling back to SQLite/JSON")
                trials_service = get_trials_service()
                trials_list, total = trials_service.get_trials_by_nct_id(
                    nct_id, skip=skip, limit=limit
                )
                return TrialsListResponse(
                    trials=[TrialResponse(**trial) for trial in trials_list],
                    total=total,
                    skip=skip,
                    limit=limit,
                )

            try:
                # Query for abstract documents with matching NCT number in metadata
                # JSONB queries: check multiple possible keys in metadata
                query = (
                    db.query(DocumentModel)
                    .filter(DocumentModel.doc_type == DocumentType.ABSTRACT)
                    .filter(
                        or_(
                            DocumentModel.doc_metadata.contains({"nct_number": nct_id}),
                            DocumentModel.doc_metadata.contains({"nct_id": nct_id}),
                            DocumentModel.doc_metadata.contains({"trial_id": nct_id}),
                        )
                    )
                    .order_by(DocumentModel.created_at.desc())
                )

                # Get total count before pagination
                total = query.count()

                # Apply pagination
                documents = query.offset(skip).limit(limit).all()

                # Format the output using utility function
                trials = [
                    extract_trial_data(
                        doc,
                        doc.doc_metadata if isinstance(doc.doc_metadata, dict) else {},
                    )
                    for doc in documents
                ]

                return TrialsListResponse(
                    trials=[TrialResponse(**trial) for trial in trials],
                    total=total,
                    skip=skip,
                    limit=limit,
                )
            except Exception as db_error:
                # If database query fails, fall back to SQLite/JSON
                logger.warning(
                    f"Database query failed ({db_error}), falling back to SQLite/JSON"
                )
                trials_service = get_trials_service()
                trials_list, total = trials_service.get_trials_by_nct_id(
                    nct_id, skip=skip, limit=limit
                )
                return TrialsListResponse(
                    trials=[TrialResponse(**trial) for trial in trials_list],
                    total=total,
                    skip=skip,
                    limit=limit,
                )
    except Exception as e:
        logger.error(
            f"Error fetching trials by NCT ID {nct_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/api/trials/abstract/{abstract_id}")
@app.get("/trials/abstract/{abstract_id}")  # Keep both for backward compatibility
async def get_trial_by_abstract_id(
    abstract_id: str,
) -> dict:
    """Get full abstract/publication data by abstract ID.

    Args:
        abstract_id: Abstract ID (e.g., "ESMO_2020_1076O", "ASCO_2020_001", or "Batch-III_11")
        db: Database session (used only if data source is "database")

    Returns:
        Full abstract dictionary with all attributes and arm_results

    Raises:
        HTTPException: If abstract not found or data source query fails
    """
    try:
        data_source = get_trials_data_source()

        if data_source in ("json", "sqlite"):
            # Use JSON file or SQLite database as data source
            trials_service = get_trials_service()
            full_abstract = trials_service.get_full_abstract_by_id(abstract_id)

            if not full_abstract:
                raise HTTPException(
                    status_code=404,
                    detail=f"Abstract with ID '{abstract_id}' not found",
                )

            return full_abstract
        else:
            # Use database as data source
            db = get_optional_db_session()
            if db is None:
                # Database not available, fall back to SQLite/JSON
                logger.warning("Database not available, falling back to SQLite/JSON")
                trials_service = get_trials_service()
                full_abstract = trials_service.get_full_abstract_by_id(abstract_id)
                if not full_abstract:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Abstract with ID '{abstract_id}' not found",
                    )
                return full_abstract

            try:
                # Query for abstract documents with matching abstract_id in metadata
                query = (
                    db.query(DocumentModel)
                    .filter(
                        or_(
                            DocumentModel.doc_metadata.contains(
                                {"abstract_id": abstract_id}
                            ),
                            DocumentModel.doc_metadata.contains(
                                {"abstract_number": abstract_id}
                            ),
                            DocumentModel.doc_metadata.contains(
                                {"publication_id": abstract_id}
                            ),
                        )
                    )
                    .order_by(DocumentModel.created_at.desc())
                )

                document = query.first()

                if not document:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Abstract with ID '{abstract_id}' not found",
                    )

                # Return full document with metadata
                return document.dict()
            except HTTPException as http_exc:
                raise http_exc
            except Exception as db_error:
                # If database query fails, fall back to SQLite/JSON
                logger.warning(
                    f"Database query failed ({db_error}), falling back to SQLite/JSON"
                )
                trials_service = get_trials_service()
                full_abstract = trials_service.get_full_abstract_by_id(abstract_id)
                if not full_abstract:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Abstract with ID '{abstract_id}' not found",
                    ) from None
                return full_abstract

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching abstract by ID {abstract_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


def _extract_attribute_value(attributes: dict, attribute_key: str) -> str:
    """Extract attribute value from attributes dictionary.

    Args:
        attributes: Dictionary of attributes
        attribute_key: The attribute key to look for (e.g., "AttributeType.CANCER_TYPE" or "cancer_type")

    Returns:
        The attribute value as string, or empty string if not found
    """
    # Try the full attribute key first (for abstracts)
    attr = attributes.get(attribute_key)
    if attr is not None:
        if isinstance(attr, dict) and "value" in attr:
            value = attr.get("value", "")
            if value and str(value).lower() != "not found":
                return str(value)
        elif not isinstance(attr, dict):
            value = str(attr)
            if value.lower() != "not found":
                return value

    # For publications, try the simplified key format
    if attribute_key.startswith("AttributeType."):
        base_key = attribute_key.replace("AttributeType.", "").lower()
        attr = attributes.get(base_key)
        if attr is not None:
            if isinstance(attr, dict) and "value" in attr:
                value = attr.get("value", "")
                if value and str(value).lower() != "not found":
                    return str(value)
            elif not isinstance(attr, dict):
                value = str(attr)
                if value.lower() != "not found":
                    return value

    return ""


def _extract_numeric_value(attr: Any) -> float | None:
    """Extract numeric value from attribute.

    Args:
        attr: Attribute value (can be dict, string, number, etc.)

    Returns:
        Numeric value or None if not numeric
    """
    if attr is None:
        return None

    if isinstance(attr, bool):
        return None

    if isinstance(attr, (int, float)):
        return float(attr)

    if isinstance(attr, str):
        try:
            parsed = float(attr)
            return parsed if not (parsed != parsed) else None  # Check for NaN
        except (ValueError, TypeError):
            # Try to extract first number from string (e.g., "12.5-15.3" -> 12.5)
            match = re.search(r"[\d.]+", attr)
            if match:
                try:
                    return float(match.group())
                except (ValueError, TypeError):
                    pass
            return None

    if isinstance(attr, dict) and "value" in attr:
        value = attr.get("value")
        if value is None or value == "Not found" or value == "NR":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                parsed = float(value)
                return parsed if not (parsed != parsed) else None
            except (ValueError, TypeError):
                # Try to extract first number
                match = re.search(r"[\d.]+", value)
                if match:
                    try:
                        return float(match.group())
                    except (ValueError, TypeError):
                        pass
                return None

    return None


def _is_industry_funded(sponsors_value: Any) -> bool | None:
    """Determine if funding is industry or non-industry.

    Args:
        sponsors_value: Sponsors attribute value

    Returns:
        True if industry, False if non-industry, None if unknown
    """
    if not sponsors_value:
        return None

    sponsors_str = ""
    if isinstance(sponsors_value, dict) and "value" in sponsors_value:
        sponsors_str = str(sponsors_value.get("value", ""))
    else:
        sponsors_str = str(sponsors_value)

    if not sponsors_str or sponsors_str.lower() in ("not found", "none"):
        return None

    sponsors_lower = sponsors_str.lower()

    # Check for explicit non-industry indicators FIRST (these take precedence)
    # This handles cases like "Genentech, institutional funding from University"
    non_industry_indicators = [
        "non-industry",
        "non industry",
        "investigator sponsored",
        "investigator-initiated",
        "academic",
        "university",
        "institutional funding",
        "government",
        "nih",
        "national cancer institute",
        "nci",
    ]
    for indicator in non_industry_indicators:
        if indicator in sponsors_lower:
            return False

    # Check for industry sponsors (common pharmaceutical companies)
    # Only if no non-industry indicators were found
    industry_indicators = [
        "merck",
        "bristol-myers",
        "bms",
        "roche",
        "genentech",
        "novartis",
        "pfizer",
        "astrazeneca",
        "gsk",
        "glaxosmithkline",
        "sanofi",
        "lilly",
        "eli lilly",
        "amgen",
        "regeneron",
        "biogen",
        "gilead",
        "abbvie",
        "johnson & johnson",
        "janssen",
    ]
    for indicator in industry_indicators:
        if indicator in sponsors_lower:
            return True

    return None


def _filter_analytics_data(
    abstracts: list[dict],
    resource_type: str = "all",
    cancer_type: str | None = None,
    therapy_type: str = "all",
    funding_type: str = "all",
    has_metric: str | None = None,
) -> list[dict]:
    """Filter analytics data based on various criteria.

    Args:
        abstracts: List of abstract/publication dictionaries
        resource_type: 'all', 'conference', or 'publication'
        cancer_type: Optional cancer type to filter by
        therapy_type: Therapy type filter ('all' or specific type)
        funding_type: Funding type filter ('all', 'industry', 'non-industry')
        has_metric: Optional metric name to filter arms that have this metric

    Returns:
        Filtered list of abstracts with filtered arm_results
    """
    filtered = []

    for abstract in abstracts:
        arm_results = abstract.get("arm_results", {})
        if not arm_results:
            continue

        # Filter by resource type
        if resource_type == "conference":
            # Must have abstract_id (not publication_id)
            if not abstract.get("abstract_id") or abstract.get("publication_id"):
                continue
            # Check if conference is ASCO or ESMO
            has_asco_esmo = False
            for arm in arm_results.values():
                conference = _extract_attribute_value(
                    arm.get("attributes", {}), "AttributeType.CONFERENCE"
                )
                if conference.upper() in ("ASCO", "ESMO"):
                    has_asco_esmo = True
                    break
            if not has_asco_esmo:
                continue
        elif resource_type == "publication":
            # Must have publication_id (not abstract_id)
            if not abstract.get("publication_id") or abstract.get("abstract_id"):
                continue

        # Filter by cancer type
        if cancer_type:
            has_matching_cancer_type = False
            for arm in arm_results.values():
                cancer_type_attr = _extract_attribute_value(
                    arm.get("attributes", {}), "AttributeType.CANCER_TYPE"
                )
                if not cancer_type_attr:
                    cancer_type_attr = _extract_attribute_value(
                        arm.get("attributes", {}), "cancer_type"
                    )
                if cancer_type_attr and cancer_type_attr.lower() == cancer_type.lower():
                    has_matching_cancer_type = True
                    break
            if not has_matching_cancer_type:
                continue

        # Filter arms by therapy type, funding type, and has_metric
        filtered_arm_results = {}
        for arm_id, arm in arm_results.items():
            attributes = arm.get("attributes", {})

            # Filter by therapy type
            if therapy_type != "all":
                therapy_type_attr = _extract_attribute_value(
                    attributes, "AttributeType.TYPE_OF_THERAPY"
                )
                if (
                    not therapy_type_attr
                    or therapy_type_attr.lower().strip() != therapy_type.lower().strip()
                ):
                    continue

            # Filter by funding type
            if funding_type != "all":
                sponsors_attr = attributes.get(
                    "AttributeType.SPONSORS"
                ) or attributes.get("sponsors")
                is_industry = _is_industry_funded(sponsors_attr)
                if funding_type == "industry" and is_industry is not True:
                    continue
                if funding_type == "non-industry" and is_industry is not False:
                    continue

            # Filter by has_metric (arm must have this metric with a valid value)
            if has_metric:
                metric_key = f"AttributeType.{has_metric}"
                metric_attr = attributes.get(metric_key) or attributes.get(
                    has_metric.lower()
                )
                metric_value = _extract_numeric_value(metric_attr)
                if metric_value is None:
                    continue

            filtered_arm_results[arm_id] = arm

        # Only include abstract if it has at least one arm after filtering
        if filtered_arm_results:
            filtered_abstract = abstract.copy()
            filtered_abstract["arm_results"] = filtered_arm_results
            filtered.append(filtered_abstract)

    return filtered


@app.get("/api/analytics/data")
async def get_analytics_data(
    skip: int = 0,
    limit: int = 100,
    resource_type: str = "all",
    cancer_type: str | None = None,
    therapy_type: str = "all",
    funding_type: str = "all",
    has_metric: str | None = None,
    db: Session = Depends(get_db_session),
) -> dict:
    """Get all abstracts/publications with full arm data for analytics.

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        resource_type: Filter by resource type ('all', 'conference', 'publication')
        cancer_type: Optional cancer type to filter by
        therapy_type: Therapy type filter ('all' or specific type)
        funding_type: Funding type filter ('all', 'industry', 'non-industry')
        has_metric: Optional metric name to filter arms that have this metric

    Returns:
        Dictionary with abstracts array containing full arm_results for chart visualization

    Raises:
        HTTPException: If data source query fails
    """
    try:
        data_source = get_trials_data_source()

        if data_source in ("json", "sqlite"):
            # Use JSON file or SQLite database as data source
            trials_service = get_trials_service()
            all_abstracts = trials_service._load_json_files()

            # Apply filters before calculating stats and pagination
            filtered_abstracts = _filter_analytics_data(
                all_abstracts,
                resource_type=resource_type,
                cancer_type=cancer_type,
                therapy_type=therapy_type,
                funding_type=funding_type,
                has_metric=has_metric,
            )

            # Calculate summary stats from filtered dataset
            total_arms = sum(len(a.get("arm_results", {})) for a in filtered_abstracts)
            total_attributes = sum(
                a.get("total_attributes_extracted", 0) for a in filtered_abstracts
            )
            confidences = [
                a.get("overall_confidence", 0)
                for a in filtered_abstracts
                if a.get("overall_confidence")
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Apply pagination to filtered results (ensure skip is non-negative)
            skip = max(0, skip)
            paginated_abstracts = filtered_abstracts[skip : skip + limit]
            has_more = (skip + limit) < len(filtered_abstracts)

            return {
                "total_abstracts": len(filtered_abstracts),
                "total_arms": total_arms,
                "total_attributes_extracted": total_attributes,
                "average_confidence": avg_confidence,
                "abstracts": paginated_abstracts,
                "skip": skip,
                "limit": limit,
                "has_more": has_more,
            }
        else:
            # Use database as data source
            # For database, we'd need to implement a similar data structure
            # For now, return empty structure
            return {
                "total_abstracts": 0,
                "total_arms": 0,
                "total_attributes_extracted": 0,
                "average_confidence": 0,
                "abstracts": [],
                "skip": skip,
                "limit": limit,
                "has_more": False,
            }

    except Exception as e:
        logger.error(f"Error fetching analytics data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/api/analytics/chart-data")
async def get_analytics_chart_data(
    target_metric: str = "MEDIAN_OS",
    resource_type: str = "all",
    cancer_type: str | None = None,
    therapy_type: str = "all",
    funding_type: str = "all",
    has_metric: str | None = None,
    db: Session = Depends(get_db_session),
) -> dict:
    """Get pre-aggregated chart data for analytics visualization.

    This endpoint returns data in a chart-ready format, reducing payload size
    significantly compared to the full analytics data endpoint.

    Args:
        target_metric: Metric to aggregate (e.g., "MEDIAN_OS", "OBJECTIVE_RESPONSE_RATE")
        resource_type: Filter by resource type ('all', 'conference', 'publication')
        cancer_type: Optional cancer type to filter by
        therapy_type: Therapy type filter ('all' or specific type)
        funding_type: Funding type filter ('all', 'industry', 'non-industry')
        has_metric: Optional metric name to filter arms that have this metric

    Returns:
        Dictionary with pre-aggregated chart data
    """
    try:
        data_source = get_trials_data_source()

        if data_source not in ("json", "sqlite"):
            return {
                "treatmentGroups": [],
                "summary": {
                    "totalAbstracts": 0,
                    "totalArms": 0,
                    "totalAttributesExtracted": 0,
                    "averageConfidence": 0.0,
                },
            }

        # Get filtered data
        trials_service = get_trials_service()
        all_abstracts = trials_service._load_json_files()

        # Apply filters
        filtered_abstracts = _filter_analytics_data(
            all_abstracts,
            resource_type=resource_type,
            cancer_type=cancer_type,
            therapy_type=therapy_type,
            funding_type=funding_type,
            has_metric=has_metric,
        )

        # Aggregate by treatment name
        treatment_groups: dict[str, dict] = {}
        approved_treatments = {
            "pembrolizumab",
            "nivolumab",
            "ipilimumab",
            "dabrafenib",
            "trametinib",
            "vemurafenib",
            "cobimetinib",
            "encorafenib",
            "binimetinib",
            "atezolizumab",
            "talimogene laherparepvec",
            "t-vec",
            "lifileucel",
        }

        for abstract in filtered_abstracts:
            for arm in abstract.get("arm_results", {}).values():
                arm_name = arm.get("arm_name", "")
                if not arm_name:
                    continue

                # Normalize treatment name (sort combination components)
                treatment_parts = sorted(
                    [p.strip() for p in arm_name.replace("+", "/").split("/")],
                    key=str.lower,
                )
                treatment_name = " + ".join(treatment_parts)

                # Get metric value
                attributes = arm.get("attributes", {})
                metric_key = f"AttributeType.{target_metric}"
                metric_attr = attributes.get(metric_key) or attributes.get(
                    target_metric.lower()
                )
                metric_value = _extract_numeric_value(metric_attr)

                if metric_value is None:
                    continue

                # Initialize group if needed
                if treatment_name not in treatment_groups:
                    # Determine approval status
                    normalized_name = treatment_name.lower()
                    is_approved = any(
                        approved in normalized_name for approved in approved_treatments
                    )

                    treatment_groups[treatment_name] = {
                        "treatmentName": treatment_name,
                        "approvalStatus": "Approved"
                        if is_approved
                        else "Investigational",
                        "values": [],
                        "patients": [],
                        "trials": [],
                    }

                group = treatment_groups[treatment_name]
                group["values"].append(metric_value)

                # Extract patient count
                patient_attr = attributes.get(
                    "AttributeType.NUMBER_OF_PATIENTS"
                ) or attributes.get("number_of_patients")
                patient_count = _extract_numeric_value(patient_attr)
                if patient_count is not None:
                    group["patients"].append(patient_count)

                # Add minimal trial metadata
                group["trials"].append(
                    {
                        "abstractId": abstract.get("abstract_id")
                        or abstract.get("publication_id")
                        or "",
                        "value": metric_value,
                        "nctNumber": _extract_attribute_value(
                            attributes, "AttributeType.NCT_NUMBER"
                        )
                        or "",
                    }
                )

        # Calculate aggregates
        result_groups = []
        for treatment_name, group in treatment_groups.items():
            values = group["values"]
            if not values:
                continue

            patients = group["patients"]
            total_patients = sum(patients) if patients else 0

            # Calculate statistics
            sorted_values = sorted(values)
            n = len(sorted_values)
            median = (
                sorted_values[n // 2]
                if n % 2 == 1
                else (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
            )

            result_groups.append(
                {
                    "treatmentName": treatment_name,
                    "approvalStatus": group["approvalStatus"],
                    "averageValue": sum(values) / len(values),
                    "medianValue": median,
                    "minValue": min(values),
                    "maxValue": max(values),
                    "trialCount": len(group["trials"]),
                    "totalPatients": total_patients,
                    "trials": group["trials"][
                        :10
                    ],  # Limit trial details to reduce payload
                }
            )

        # Sort by average value (descending)
        result_groups.sort(key=lambda x: x["averageValue"], reverse=True)

        # Calculate summary stats
        total_arms = sum(len(a.get("arm_results", {})) for a in filtered_abstracts)
        total_attributes = sum(
            a.get("total_attributes_extracted", 0) for a in filtered_abstracts
        )
        confidences = [
            a.get("overall_confidence", 0)
            for a in filtered_abstracts
            if a.get("overall_confidence")
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "treatmentGroups": result_groups,
            "summary": {
                "totalAbstracts": len(filtered_abstracts),
                "totalArms": total_arms,
                "totalAttributesExtracted": total_attributes,
                "averageConfidence": avg_confidence,
            },
        }

    except Exception as e:
        logger.error(f"Error fetching chart data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/api/resources")
async def get_resources() -> dict:
    """Get resource usage information for monitoring."""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        children = process.children(recursive=True)

        # Calculate total memory including children
        total_rss = memory_info.rss
        for child in children:
            try:
                total_rss += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Get system stats
        system_memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Calculate reuse rate
        total_requests = (
            _service_stats["instance_creations"] + _service_stats["instance_reuses"]
        )
        reuse_rate = (
            (_service_stats["instance_reuses"] / total_requests * 100)
            if total_requests > 0
            else 0
        )

        # Get JSON cache info
        json_cache = {}
        if _json_service_instance and _json_service_instance._cache:
            json_cache = {
                "cached": True,
                "abstract_count": len(_json_service_instance._cache),
            }
        else:
            json_cache = {"cached": False, "abstract_count": 0}

        return {
            "process": {
                "memory_mb": total_rss / (1024 * 1024),
                "cpu_percent": cpu_percent,
                "num_children": len(children),
            },
            "system": {
                "total_memory_gb": system_memory.total / (1024**3),
                "available_memory_gb": system_memory.available / (1024**3),
                "memory_percent": system_memory.percent,
                "cpu_percent": cpu_percent,
            },
            "service": {
                "instance_creations": _service_stats["instance_creations"],
                "instance_reuses": _service_stats["instance_reuses"],
                "reuse_rate_percent": reuse_rate,
                "total_requests": total_requests,
            },
            "json_cache": json_cache,
        }
    except Exception as e:
        logger.error(f"Error getting resources: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/api/analytics/arms/{abstract_id}")
async def get_analytics_arms(abstract_id: str) -> dict:
    """Get arm results for a specific abstract ID (lazy loading)."""
    try:
        data_source = get_trials_data_source()

        if data_source == "json":
            json_service = get_json_trials_service()
            all_abstracts = json_service._load_json_files()

            # Find the abstract by ID
            for abstract in all_abstracts:
                if (
                    abstract.get("abstract_id") == abstract_id
                    or abstract.get("publication_id") == abstract_id
                ):
                    return {
                        "abstract_id": abstract_id,
                        "arm_results": abstract.get("arm_results", {}),
                    }

            # Not found
            raise HTTPException(
                status_code=404, detail=f"Abstract with ID '{abstract_id}' not found"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="Database data source not supported for this endpoint",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching arms for {abstract_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/api/analytics/data/stream")
async def stream_analytics_data():
    """Stream analytics data as NDJSON (newline-delimited JSON)."""

    async def generate():
        try:
            data_source = get_trials_data_source()

            if data_source == "json":
                json_service = get_json_trials_service()
                all_abstracts = json_service._load_json_files()

                # Calculate summary stats
                total_arms = sum(len(a.get("arm_results", {})) for a in all_abstracts)
                total_attributes = sum(
                    a.get("total_attributes_extracted", 0) for a in all_abstracts
                )
                confidences = [
                    a.get("overall_confidence", 0)
                    for a in all_abstracts
                    if a.get("overall_confidence")
                ]
                avg_confidence = (
                    sum(confidences) / len(confidences) if confidences else 0
                )

                # Create summary line
                summary = {
                    "type": "summary",
                    "total_abstracts": len(all_abstracts),
                    "total_arms": total_arms,
                    "total_attributes_extracted": total_attributes,
                    "average_confidence": avg_confidence,
                }

                # Yield summary first
                yield json.dumps(summary) + "\n"
                # Then yield each abstract
                for abstract in all_abstracts:
                    yield json.dumps(abstract) + "\n"
            else:
                # Return empty stream for database source
                summary = {
                    "type": "summary",
                    "total_abstracts": 0,
                    "total_arms": 0,
                    "total_attributes_extracted": 0,
                    "average_confidence": 0,
                }
                yield json.dumps(summary) + "\n"

        except Exception as e:
            logger.error(f"Error streaming analytics data: {str(e)}", exc_info=True)
            error_msg = json.dumps({"error": str(e)}) + "\n"
            yield error_msg.encode()

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="analytics_data.ndjson"'},
    )


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
