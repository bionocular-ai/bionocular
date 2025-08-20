"""Local filesystem storage implementation for documents."""

import hashlib
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..domain.interfaces import StorageInterface
from ..domain.models import DocumentType


class LocalFileStorage(StorageInterface):
    """Local filesystem storage implementation."""

    def __init__(self, base_storage_dir: str = "./storage"):
        """Initialize local storage with base directory."""
        self.base_storage_dir = Path(base_storage_dir)
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure storage directories exist."""
        self.base_storage_dir.mkdir(parents=True, exist_ok=True)
        (self.base_storage_dir / "originals").mkdir(exist_ok=True)
        (self.base_storage_dir / "abstracts").mkdir(exist_ok=True)
        (self.base_storage_dir / "publications").mkdir(exist_ok=True)

    async def store_document(
        self, file_content: bytes, filename: str, document_type: DocumentType
    ) -> str:
        """Store a document and return the storage path."""
        # Generate unique filename to avoid conflicts
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid4()}_{filename}"

        # Determine storage subdirectory based on document type
        if document_type == DocumentType.ABSTRACT:
            storage_subdir = "abstracts"
        else:
            storage_subdir = "publications"

        # Create full storage path
        storage_path = self.base_storage_dir / storage_subdir / unique_filename

        # Store the file
        with open(storage_path, "wb") as f:
            f.write(file_content)

        return str(storage_path)

    async def document_exists(self, content_hash: str) -> bool:
        """Check if a document with the given hash already exists."""
        # This is a simplified check - in a real implementation,
        # you'd want to check the database for the hash
        return False

    async def get_document_path(self, content_hash: str) -> Optional[str]:
        """Get the storage path of an existing document."""
        # This would typically query the database
        # For now, return None as we're not implementing full duplicate detection
        return None

    def compute_hash(self, file_content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()

    def get_storage_info(self) -> dict:
        """Get information about storage usage."""
        total_size = 0
        file_count = 0

        for root, dirs, files in os.walk(self.base_storage_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1

        return {
            "total_files": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "base_directory": str(self.base_storage_dir),
        }
