#!/usr/bin/env python3
"""Command-line interface for document ingestion."""

import argparse
import asyncio
import json
import logging
import os
import sys

from ..domain.models import DocumentType, IngestionRequest
from ..infrastructure.database import create_storage_directories, init_database
from ..infrastructure.pdf_processor import PyPDF2Processor
from ..infrastructure.storage import LocalFileStorage
from .ingestion_service import IngestionService


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("ingest_cli.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def ingest_single_file(
    file_path: str,
    document_type: DocumentType,
    metadata: dict,
    ingestion_service: IngestionService,
) -> None:
    """Ingest a single PDF file."""
    try:
        # Read file
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Create request
        request = IngestionRequest(type=document_type, metadata=metadata)

        # Process document
        response = await ingestion_service.ingest_single_document(
            file_content, os.path.basename(file_path), request
        )

        if response.status.value == "ingested":
            print(f"✅ Successfully ingested: {file_path}")
            print(f"   Document ID: {response.document_id}")
            print(f"   Storage Path: {response.storage_path}")
        elif response.is_duplicate:
            print(f"⚠️  Duplicate document: {file_path}")
            print(f"   Existing Document ID: {response.document_id}")
        else:
            print(f"❌ Failed to ingest: {file_path}")
            print(f"   Error: {response.message}")

    except Exception as e:
        print(f"❌ Error processing {file_path}: {str(e)}")


async def ingest_batch_file(
    file_path: str,
    document_type: DocumentType,
    metadata: dict,
    ingestion_service: IngestionService,
) -> None:
    """Ingest a batch PDF file."""
    try:
        # Read file
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Create request
        request = IngestionRequest(type=document_type, metadata=metadata)

        # Process batch documents
        responses = await ingestion_service.ingest_batch_documents(
            file_content, os.path.basename(file_path), request
        )

        # Print results
        total = len(responses)
        successful = len([r for r in responses if r.status.value == "ingested"])
        failed = len([r for r in responses if r.status.value == "processing_failed"])
        duplicates = len([r for r in responses if r.is_duplicate])

        print(f"📄 Batch processing complete for: {file_path}")
        print(f"   Total documents: {total}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Duplicates: {duplicates}")

        # Show details for failed documents
        if failed > 0:
            print("\n❌ Failed documents:")
            for response in responses:
                if response.status.value == "processing_failed":
                    print(f"   - {response.original_filename}: {response.message}")

        # Show details for duplicates
        if duplicates > 0:
            print("\n⚠️  Duplicate documents:")
            for response in responses:
                if response.is_duplicate:
                    print(f"   - {response.original_filename}")

    except Exception as e:
        print(f"❌ Error processing batch file {file_path}: {str(e)}")


async def main() -> None:
    """Main function for CLI ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest PDF documents into the Bionocular system"
    )

    parser.add_argument(
        "--file", "-f", required=True, help="Path to PDF file to ingest"
    )

    parser.add_argument(
        "--type",
        "-t",
        choices=["abstract", "publication"],
        required=True,
        help="Type of document being ingested",
    )

    parser.add_argument(
        "--metadata",
        "-m",
        default="{}",
        help="Additional metadata as JSON string (default: {})",
    )

    parser.add_argument(
        "--batch",
        "-b",
        action="store_true",
        help="Treat the PDF as a batch file containing multiple documents",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Validate file exists
    if not os.path.exists(args.file):
        print(f"❌ File not found: {args.file}")
        sys.exit(1)

    # Validate file is PDF
    if not args.file.lower().endswith(".pdf"):
        print(f"❌ Only PDF files are supported: {args.file}")
        sys.exit(1)

    # Parse metadata
    try:
        metadata = json.loads(args.metadata) if args.metadata else {}
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON metadata: {e}")
        sys.exit(1)

    try:
        # Initialize system
        logger.info("Initializing ingestion system...")
        init_database()
        create_storage_directories()

        # Create services
        storage = LocalFileStorage()
        pdf_processor = PyPDF2Processor()

        # Note: For CLI, we'll use a mock repository since we don't have a DB session
        # In a real implementation, you'd want to create a proper DB connection
        from unittest.mock import Mock

        mock_repository = Mock()
        mock_repository.find_by_hash.return_value = None
        mock_repository.save_document.return_value = None

        ingestion_service = IngestionService(storage, mock_repository, pdf_processor)

        # Process document
        document_type = DocumentType(args.type)

        if args.batch:
            await ingest_batch_file(
                args.file, document_type, metadata, ingestion_service
            )
        else:
            await ingest_single_file(
                args.file, document_type, metadata, ingestion_service
            )

        print("\n🎉 Ingestion process completed!")

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
