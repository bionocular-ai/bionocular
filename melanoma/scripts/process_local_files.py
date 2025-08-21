#!/usr/bin/env python3
"""Script to process local PDF files using the ingestion system."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from main.binocular.python.app.ingestion_service import IngestionService
from main.binocular.python.domain.models import DocumentType, IngestionRequest
from main.binocular.python.infrastructure.database import init_database, create_storage_directories
from main.binocular.python.infrastructure.repository import SQLAlchemyDocumentRepository
from main.binocular.python.infrastructure.storage import LocalFileStorage
from main.binocular.python.infrastructure.pdf_processor import PyPDF2Processor


async def process_single_file(file_path: str, document_type: DocumentType, metadata: dict = None):
    """Process a single PDF file."""
    try:
        # Initialize services
        storage = LocalFileStorage()
        pdf_processor = PyPDF2Processor()
        
        # For CLI processing, we'll use a mock repository
        from unittest.mock import Mock
        mock_repository = Mock()
        mock_repository.find_by_hash.return_value = None
        mock_repository.save_document.return_value = None
        
        ingestion_service = IngestionService(storage, mock_repository, pdf_processor)
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Create request
        request = IngestionRequest(
            type=document_type,
            metadata=metadata or {}
        )
        
        # Process document
        response = await ingestion_service.ingest_single_document(
            file_content,
            os.path.basename(file_path),
            request
        )
        
        print(f"✅ Processed: {file_path}")
        print(f"   Status: {response.status.value}")
        print(f"   Message: {response.message}")
        
        return response
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {str(e)}")
        return None


async def process_directory(directory_path: str, document_type: DocumentType, recursive: bool = False):
    """Process all PDF files in a directory."""
    print(f"📁 Processing directory: {directory_path}")
    
    # Find all PDF files
    pdf_files = []
    if recursive:
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(directory_path):
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(directory_path, file))
    
    if not pdf_files:
        print("   No PDF files found")
        return []
    
    print(f"   Found {len(pdf_files)} PDF files")
    
    # Process each file
    results = []
    for pdf_file in pdf_files:
        result = await process_single_file(pdf_file, document_type)
        results.append(result)
    
    return results


async def main():
    """Main function."""
    print("🚀 Bionocular Local File Processor")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not (Path.cwd() / "src").exists():
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Initialize system
    print("📋 Initializing system...")
    try:
        init_database()
        create_storage_directories()
        print("✅ System initialized")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize database: {e}")
        print("   Continuing with file processing only...")
    
    # Example usage
    print("\n📖 Example Usage:")
    print("1. Place PDFs in data/abstracts or data/publications")
    print("2. Use the API endpoints to process them:")
    print("   - POST /ingest/local - Single file")
    print("   - POST /ingest/local/batch - Batch file")
    print("   - POST /ingest/directory - Entire directory")
    print("3. Or use this script directly")
    
    # Check for files in data directories
    print("\n🔍 Checking data directories...")
    data_dirs = {
        "Abstracts": "./data/abstracts",
        "Publications": "./data/publications"
    }
    
    for name, path in data_dirs.items():
        if os.path.exists(path):
            pdf_files = [f for f in os.listdir(path) if f.lower().endswith('.pdf')]
            print(f"   {name}: {len(pdf_files)} PDF files")
            
            if pdf_files:
                print(f"      Files: {', '.join(pdf_files[:3])}{'...' if len(pdf_files) > 3 else ''}")
        else:
            print(f"   {name}: Directory not found")
    
    # Interactive processing
    print("\n🔄 Interactive Processing:")
    print("Enter 'q' to quit, or provide a file path to process:")
    
    while True:
        user_input = input("\nFile path (or 'q' to quit): ").strip()
        
        if user_input.lower() == 'q':
            break
        
        if not user_input:
            continue
        
        if not os.path.exists(user_input):
            print(f"❌ File not found: {user_input}")
            continue
        
        if not user_input.lower().endswith('.pdf'):
            print("❌ Only PDF files are supported")
            continue
        
        # Determine document type
        print("Document type:")
        print("1. Abstract")
        print("2. Publication")
        
        type_choice = input("Choice (1 or 2): ").strip()
        
        if type_choice == "1":
            doc_type = DocumentType.ABSTRACT
        elif type_choice == "2":
            doc_type = DocumentType.PUBLICATION
        else:
            print("Invalid choice, defaulting to Abstract")
            doc_type = DocumentType.ABSTRACT
        
        # Process the file
        print(f"\n🔄 Processing {user_input} as {doc_type.value}...")
        await process_single_file(user_input, doc_type)
    
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
