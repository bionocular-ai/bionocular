"""LangChain-based chunking service for clinical abstracts.

This module provides a sophisticated chunking service that combines LangChain's
MarkdownHeaderTextSplitter with custom clinical metadata extraction capabilities.
It maintains the clean architecture principles while leveraging LangChain's
powerful text splitting capabilities.
"""

import logging
import re
from typing import Any, Optional
from uuid import uuid4

from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain_core.documents import Document

from ...domain.interfaces import ChunkingStrategyInterface
from ...domain.models import (
    Chunk,
    ChunkingConfiguration,
    ChunkingStrategy,
    ChunkType,
)

logger = logging.getLogger(__name__)


class ClinicalMetadataExtractor:
    """Extracts clinical metadata from abstract content.

    This class encapsulates all the complex regex patterns and logic for
    extracting clinical metadata from oncology abstracts. It's separated
    from the chunking logic to maintain single responsibility principle.
    """

    # Clinical trial ID patterns
    CLINICAL_TRIAL_PATTERNS = [
        r"NCT\d+",  # NCT format
        r"EORTC-\d+",  # EORTC format
        r"ECOG-\d+",  # ECOG format
    ]

    # Abstract ID patterns for different conferences
    ABSTRACT_ID_PATTERNS = [
        r"### Abstract ID: ([0-9]+[A-Z]*)",  # ESMO format like 1076O, 1077MO
        r"### Abstract ID: (\d+)",  # ASCO format like 10000
        r"Abstract ID: ([0-9]+[A-Z]*)",  # Alternative format
    ]

    # Year extraction patterns
    YEAR_PATTERNS = [
        r"ASCO_(\d{4})",
        r"ESMO_(\d{4})",
        r"(\d{4})",  # Generic year pattern
    ]

    # Sponsor extraction patterns
    SPONSOR_PATTERNS = [
        # ASCO patterns
        r"\*\*Research Sponsor:\*\* (.+)",
        r"Research Sponsor:\s*(.+)",
        # ESMO patterns
        r"\*\*Legal entity responsible for the study:\*\* (.+)",
        r"\*\*Funding:\*\* (.+)",
        r"Legal entity responsible for the study:\s*(.+)",
        r"Funding:\s*(.+)",
        # Generic patterns
        r"\*\*Sponsor:\*\* (.+)",
        r"Sponsor:\s*(.+)",
    ]

    def extract_metadata(self, content: str, filename: str = "") -> dict[str, Any]:
        """Extract clinical metadata from content and filename.

        Args:
            content: The abstract content to extract metadata from
            filename: The filename for additional context

        Returns:
            Dictionary containing extracted metadata
        """
        metadata = {}

        # Extract year from filename
        metadata.update(self._extract_year_from_filename(filename))

        # Extract abstract ID
        metadata.update(self._extract_abstract_id(content))

        # Extract clinical trial ID
        metadata.update(self._extract_clinical_trial_id(content))

        # Extract sponsor information
        metadata.update(self._extract_sponsor_info(content))

        # Extract title
        metadata.update(self._extract_title(content))

        # Check for table content
        metadata["has_table"] = self._has_table_content(content)

        return metadata

    def _extract_year_from_filename(self, filename: str) -> dict[str, Any]:
        """Extract year from filename patterns."""
        for pattern in self.YEAR_PATTERNS:
            year_match = re.search(pattern, filename)
            if year_match:
                return {"year": int(year_match.group(1))}
        return {}

    def _extract_abstract_id(self, content: str) -> dict[str, Any]:
        """Extract abstract ID from content."""
        for pattern in self.ABSTRACT_ID_PATTERNS:
            abstract_id_match = re.search(pattern, content)
            if abstract_id_match:
                return {"abstract_id": abstract_id_match.group(1)}
        return {}

    def _extract_clinical_trial_id(self, content: str) -> dict[str, Any]:
        """Extract clinical trial ID from content."""
        for pattern in self.CLINICAL_TRIAL_PATTERNS:
            trial_match = re.search(pattern, content)
            if trial_match:
                return {"clinical_trial_id": trial_match.group(0)}
        return {}

    def _extract_sponsor_info(self, content: str) -> dict[str, Any]:
        """Extract sponsor information from content."""
        for pattern in self.SPONSOR_PATTERNS:
            sponsor_match = re.search(pattern, content, re.IGNORECASE)
            if sponsor_match:
                sponsor = sponsor_match.group(1).strip()
                # Clean up common suffixes and artifacts
                sponsor = re.sub(r"\.$", "", sponsor)  # Remove trailing period
                sponsor = re.sub(
                    r"\s*##.*$", "", sponsor
                )  # Remove ## and anything after
                if sponsor and sponsor != "##":  # Skip empty or artifact sponsors
                    return {"sponsor": sponsor}
        return {}

    def _extract_title(self, content: str) -> dict[str, Any]:
        """Extract title from content.

        New format: Title is a separate section with '#### Title:' header.
        """
        # New format: #### Title:\nTitle text here
        title_match = re.search(
            r"#### Title:\s*\n(.+?)(?:\n####|\n\n|$)", content, re.DOTALL
        )
        if title_match:
            return {"title": title_match.group(1).strip()}

        # Legacy format fallback: **Title:** title text
        legacy_match = re.search(r"\*\*Title:\*\* (.+)", content)
        if legacy_match:
            return {"title": legacy_match.group(1).strip()}

        return {}

    def _has_table_content(self, content: str) -> bool:
        """Check if content contains table formatting."""
        return "|" in content and "---" in content


class ChunkTypeClassifier:
    """Classifies chunks based on content and headers.

    This class encapsulates the logic for determining chunk types based on
    content analysis and header information. It's separated to maintain
    single responsibility and make the classification logic testable.
    """

    # Section header patterns for classification
    SECTION_PATTERNS = {
        ChunkType.BACKGROUND: ["background", "#### background:"],
        ChunkType.METHODS: ["method", "#### methods:"],
        ChunkType.TRIAL_DESIGN: ["trial design", "#### trial design:"],
        ChunkType.RESULTS: ["result", "#### results:"],
        ChunkType.CONCLUSIONS: ["conclusion", "#### conclusions:"],
        ChunkType.TABLE: ["table", "#### table:"],
        ChunkType.CLINICAL_TRIAL: [
            "clinical trial",
            "#### clinical trial",
            "#### clinical trial information:",
            "#### clinical trial identification:",
        ],
        ChunkType.SPONSOR: ["sponsor", "#### research sponsor:"],
        ChunkType.FUNDING: ["funding", "#### funding:"],
        ChunkType.DOI: ["doi", "#### doi:"],
        ChunkType.FULL_TEXT_REFERENCE: ["full text", "#### full text reference:"],
    }

    def classify_chunk_type(self, content: str, headers: dict[str, str]) -> ChunkType:
        """Classify the chunk type based on content and headers.

        Args:
            content: The chunk content
            headers: Dictionary of header information

        Returns:
            The classified chunk type
        """
        content_lower = content.lower()
        section = headers.get("Section", "").lower()

        # Abstract ID detection (separate from title)
        if self._is_abstract_id(content_lower):
            return ChunkType.ABSTRACT_ID

        # Title detection (separate from abstract ID)
        if self._is_title(content_lower):
            return ChunkType.TITLE

        # Section-based detection
        for chunk_type, patterns in self.SECTION_PATTERNS.items():
            if self._matches_section_patterns(section, content_lower, patterns):
                return chunk_type

        # Table content detection
        if self._is_table_content(content):
            return ChunkType.TABLE

        # Default to full abstract
        return ChunkType.FULL_ABSTRACT

    def _is_abstract_id(self, content_lower: str) -> bool:
        """Check if content is specifically the abstract ID section."""
        return (
            "### abstract id:" in content_lower or "abstract id:" in content_lower
        ) and "title" not in content_lower

    def _is_title(self, content_lower: str) -> bool:
        """Check if content is specifically the title section."""
        return "#### title:" in content_lower

    def _matches_section_patterns(
        self, section: str, content_lower: str, patterns: list[str]
    ) -> bool:
        """Check if content matches section patterns."""
        return any(
            pattern in section or pattern in content_lower for pattern in patterns
        )

    def _is_table_content(self, content: str) -> bool:
        """Check if content is primarily table content."""
        lines = content.strip().split("\n")
        table_lines = sum(1 for line in lines if "|" in line)
        return table_lines > len(lines) * 0.3  # 30% threshold


class LangChainChunkingService(ChunkingStrategyInterface):
    """LangChain-based chunking service for clinical abstracts.

    This service combines LangChain's MarkdownHeaderTextSplitter with custom
    clinical metadata extraction to provide sophisticated chunking capabilities
    for oncology abstracts while maintaining clean architecture principles.

    🎯 TIER 2: Implements hierarchical sub-chunking for large Results sections
    """

    def __init__(self, configuration: ChunkingConfiguration):
        """Initialize the LangChain chunking service.

        Args:
            configuration: Chunking configuration
        """
        self.configuration = configuration
        self.supported_strategies = [
            ChunkingStrategy.HEADER_BASED,
            ChunkingStrategy.HYBRID,
        ]

        # Initialize LangChain's MarkdownHeaderTextSplitter
        self.text_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("###", "Abstract ID"),
                ("####", "Section"),
            ],
            strip_headers=False,  # Keep headers for context
        )

        # 🎯 TIER 2: Initialize secondary splitter for large Results sections
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        self.results_splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,  # ~2-3 paragraphs for better numeric attribute precision
            chunk_overlap=50,  # Small overlap to maintain context across chunks
            separators=["\n\n", "\n", ". ", ", ", " "],  # Paragraph > Sentence > Word
            length_function=len,
        )

        # Threshold for sub-chunking (character count)
        self.subchunk_threshold = 600  # Only sub-chunk if section is larger than this

        # Initialize helper services
        self.metadata_extractor = ClinicalMetadataExtractor()
        self.chunk_classifier = ChunkTypeClassifier()

        logger.info(
            f"LangChain chunking service initialized with strategy: {configuration.strategy} "
            f"and TIER 2 sub-chunking (threshold: {self.subchunk_threshold} chars)"
        )

    def supports_configuration(self, configuration: ChunkingConfiguration) -> bool:
        """Check if this strategy supports the given configuration.

        Args:
            configuration: Chunking configuration to check

        Returns:
            True if the configuration is supported
        """
        return configuration.strategy in self.supported_strategies

    async def chunk_content(
        self,
        content: str,
        configuration: ChunkingConfiguration,
        document_id: Optional[str] = None,
        filename: str = "",
    ) -> list[Chunk]:
        """Chunk content using LangChain's MarkdownHeaderTextSplitter.

        🎯 TIER 2: Implements hierarchical sub-chunking for large Results/Table sections

        Args:
            content: Content to chunk
            configuration: Chunking configuration
            document_id: Document ID
            filename: Filename for metadata extraction

        Returns:
            List of chunks (with Results sections potentially sub-chunked)

        Raises:
            ValueError: If content is empty or invalid
            RuntimeError: If chunking fails
        """
        if not content.strip():
            raise ValueError("Content cannot be empty")

        try:
            logger.info(f"Starting TIER 2 chunking process for document: {filename}")

            # Step 1: Use LangChain's splitter for section-level chunking
            langchain_documents = self.text_splitter.split_text(content)

            # Step 1.5: Post-process to separate Abstract ID and Title
            # (LangChain combines them since Title is a subsection of Abstract ID)
            langchain_documents = self._separate_abstract_id_and_title(
                langchain_documents
            )

            # Step 2: Convert to domain chunks with hierarchical sub-chunking
            chunks = []
            sequence_number = 0
            subchunked_count = 0

            for document in langchain_documents:
                # Check if this is a Results/Table section that needs sub-chunking
                section_header = document.metadata.get("Section", "").lower()
                is_results_section = self._is_results_or_table_section(section_header)
                content_length = len(document.page_content)

                if is_results_section and content_length > self.subchunk_threshold:
                    # 🎯 TIER 2: Sub-chunk large Results/Table sections
                    logger.debug(
                        f"Sub-chunking large {section_header} section ({content_length} chars)"
                    )

                    # Split into smaller chunks for better retrieval precision
                    sub_texts = self.results_splitter.split_text(document.page_content)

                    for sub_index, sub_text in enumerate(sub_texts):
                        # Create sub-chunk with parent metadata
                        metadata = document.metadata.copy()
                        metadata["is_subchunk"] = True
                        metadata["parent_chunk_size"] = content_length
                        metadata["subchunk_index"] = sub_index
                        metadata["total_subchunks"] = len(sub_texts)

                        chunk = self._create_chunk_from_text(
                            content=sub_text,
                            metadata=metadata,
                            document_id=document_id,
                            filename=filename,
                            sequence_number=sequence_number,
                        )
                        chunks.append(chunk)
                        sequence_number += 1

                    subchunked_count += 1
                else:
                    # Keep as single chunk for non-Results sections or small sections
                    chunk = self._convert_langchain_document_to_chunk(
                        document, document_id, filename, sequence_number
                    )
                    chunks.append(chunk)
                    sequence_number += 1

            logger.info(
                f"Successfully created {len(chunks)} chunks using LangChain "
                f"(TIER 2: {subchunked_count} Results sections sub-chunked)"
            )
            return chunks

        except Exception as e:
            logger.error(f"LangChain chunking failed: {e}")
            raise RuntimeError(f"Chunking failed: {e}") from e

    def _convert_langchain_document_to_chunk(
        self,
        document: Document,
        document_id: Optional[str],
        filename: str,
        sequence_number: int,
    ) -> Chunk:
        """Convert LangChain Document to domain Chunk.

        Args:
            document: LangChain Document
            document_id: Document ID
            filename: Filename for metadata
            sequence_number: Sequence number

        Returns:
            Domain Chunk
        """
        # Extract metadata from LangChain document
        metadata = document.metadata.copy()

        # Add clinical metadata extraction
        clinical_metadata = self.metadata_extractor.extract_metadata(
            document.page_content, filename
        )
        metadata.update(clinical_metadata)

        # Add abstract_id to metadata if document_id is provided
        if document_id:
            metadata["abstract_id"] = document_id

        # Determine chunk type
        chunk_type = self.chunk_classifier.classify_chunk_type(
            document.page_content, metadata
        )

        # Create domain chunk
        # Use the original document_id as string, don't convert to UUID
        chunk_document_id = document_id if document_id else str(uuid4())

        return Chunk(
            id=uuid4(),
            document_id=chunk_document_id,
            content=document.page_content,
            chunk_type=chunk_type,
            metadata=metadata,
            sequence_number=sequence_number,
            token_count=len(document.page_content.split()),
        )

    def get_chunking_statistics(self, chunks: list[Chunk]) -> dict[str, Any]:
        """Get statistics about the chunking process.

        Args:
            chunks: List of chunks to analyze

        Returns:
            Dictionary containing chunking statistics
        """
        if not chunks:
            return {"total_chunks": 0}

        chunk_types = {}
        for chunk in chunks:
            chunk_type = chunk.chunk_type.value
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

        return {
            "total_chunks": len(chunks),
            "chunk_types": chunk_types,
            "average_token_count": sum(chunk.token_count or 0 for chunk in chunks)
            / len(chunks),
            "total_tokens": sum(chunk.token_count or 0 for chunk in chunks),
        }

    def get_service_statistics(self) -> dict[str, Any]:
        """Get statistics about the chunking service.

        Returns:
            Dictionary containing service statistics
        """
        return {
            "strategy": self.configuration.strategy.value,
            "chunks_created": len(self.metadata_extractor.CLINICAL_TRIAL_PATTERNS),
            "available_strategies": [strategy.value for strategy in ChunkingStrategy],
            "subchunk_threshold": self.subchunk_threshold,
            "tier2_enabled": True,
        }

    def _separate_abstract_id_and_title(
        self, documents: list[Document]
    ) -> list[Document]:
        """Separate Abstract ID and Title if they're combined in one chunk.

        LangChain's MarkdownHeaderTextSplitter treats Title (####) as a subsection
        of Abstract ID (###), combining them into one document. This method splits
        them into two separate documents for more precise retrieval.

        Args:
            documents: List of LangChain Documents

        Returns:
            List of Documents with Abstract ID and Title separated
        """
        separated_docs = []

        for doc in documents:
            content_lower = doc.page_content.lower()

            # Check if this chunk contains both Abstract ID and Title
            if "abstract id:" in content_lower and "#### title:" in content_lower:
                # Split into two documents
                lines = doc.page_content.split("\n")
                abstract_id_lines = []
                title_lines = []
                in_title_section = False

                for line in lines:
                    if "#### title:" in line.lower():
                        in_title_section = True

                    if in_title_section:
                        title_lines.append(line)
                    else:
                        abstract_id_lines.append(line)

                # Create Abstract ID document
                if abstract_id_lines:
                    abstract_id_content = "\n".join(abstract_id_lines).strip()
                    abstract_id_doc = Document(
                        page_content=abstract_id_content, metadata=doc.metadata.copy()
                    )
                    separated_docs.append(abstract_id_doc)

                # Create Title document
                if title_lines:
                    title_content = "\n".join(title_lines).strip()
                    title_doc = Document(
                        page_content=title_content, metadata=doc.metadata.copy()
                    )
                    separated_docs.append(title_doc)
            else:
                # No split needed, keep as is
                separated_docs.append(doc)

        return separated_docs

    def _is_results_or_table_section(self, section_header: str) -> bool:
        """Check if a section header indicates Results, Table, or related sections.

        🎯 TIER 2: Used to identify sections that should be sub-chunked

        Args:
            section_header: The section header (lowercase)

        Returns:
            True if this is a Results/Table/Conclusions section
        """
        results_keywords = [
            "result",
            "table",
            "conclusion",
            "efficacy",
            "safety",
            "table",
        ]

        return any(keyword in section_header for keyword in results_keywords)

    def _create_chunk_from_text(
        self,
        content: str,
        metadata: dict[str, Any],
        document_id: Optional[str],
        filename: str,
        sequence_number: int,
    ) -> Chunk:
        """Create a domain Chunk from text and metadata.

        🎯 TIER 2: Used to create sub-chunks with inherited metadata

        Args:
            content: The chunk content
            metadata: Metadata dictionary (already includes section info)
            document_id: Document ID
            filename: Filename for additional metadata
            sequence_number: Sequence number

        Returns:
            Domain Chunk with all metadata
        """
        # Add clinical metadata extraction
        clinical_metadata = self.metadata_extractor.extract_metadata(content, filename)
        metadata.update(clinical_metadata)

        # Add abstract_id to metadata if document_id is provided
        if document_id:
            metadata["abstract_id"] = document_id

        # Determine chunk type
        chunk_type = self.chunk_classifier.classify_chunk_type(content, metadata)

        # Create domain chunk
        chunk_document_id = document_id if document_id else str(uuid4())

        return Chunk(
            id=uuid4(),
            document_id=chunk_document_id,
            content=content,
            chunk_type=chunk_type,
            metadata=metadata,
            sequence_number=sequence_number,
            token_count=len(content.split()),
        )
