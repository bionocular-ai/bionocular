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

try:
    from langchain.text_splitter import (
        MarkdownHeaderTextSplitter,
        RecursiveCharacterTextSplitter,
    )
    from langchain_core.documents import Document
except ImportError as e:
    raise ImportError(
        "langchain dependencies are required for LangChainChunkingService. "
        "Install with: poetry install --with processing"
    ) from e

from ...domain.document_section_patterns import (
    PUBLICATION_SECTION_KEYWORDS,
    SECTION_PATTERNS,
)
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

    # Section header patterns — defined in domain.document_section_patterns
    SECTION_PATTERNS = SECTION_PATTERNS

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
        main_section = headers.get("Main Section", "").lower()
        subsection = headers.get("Subsection", "").lower()

        # Abstract ID detection (separate from title)
        if self._is_abstract_id(content_lower):
            return ChunkType.ABSTRACT_ID

        # Title detection (separate from abstract ID)
        if self._is_title(content_lower):
            return ChunkType.TITLE

        # Check publication-style headers (Main Section, Subsection)
        # Keywords defined in domain.document_section_patterns.PUBLICATION_SECTION_KEYWORDS
        if main_section or subsection:
            for chunk_type, keywords in PUBLICATION_SECTION_KEYWORDS:
                if any(
                    keyword in main_section or keyword in subsection
                    for keyword in keywords
                ):
                    return chunk_type

        # Section-based detection (for abstract-style headers)
        for chunk_type, patterns in self.SECTION_PATTERNS.items():
            if self._matches_section_patterns(section, content_lower, patterns):
                return chunk_type

        # Table content detection
        if self._is_table_content(content):
            return ChunkType.TABLE

        # Default to full abstract (for abstracts) or try to infer from content
        # For publications, try to infer from content structure
        if any(
            keyword in content_lower[:500]  # Check first 500 chars
            for keyword in [
                "# introduction",
                "## introduction",
                "# methods",
                "## methods",
            ]
        ):
            # Likely a publication section, try to classify
            if "result" in content_lower[:200]:
                return ChunkType.RESULTS
            if "method" in content_lower[:200]:
                return ChunkType.METHODS
            if (
                "background" in content_lower[:200]
                or "introduction" in content_lower[:200]
            ):
                return ChunkType.BACKGROUND
            if (
                "conclusion" in content_lower[:200]
                or "discussion" in content_lower[:200]
            ):
                return ChunkType.CONCLUSIONS

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
        📄 Publication-aware: Detects publications and uses specialized chunking strategy

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
            # Detect if this is a publication (not an abstract)
            is_publication = self._is_publication(content, filename)

            if is_publication:
                logger.info(
                    f"Detected publication document: {filename}, using publication-specific chunking"
                )
                return await self._chunk_publication(
                    content, configuration, document_id, filename
                )

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

        chunk_types: dict[str, int] = {}
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

    def _is_publication(self, content: str, filename: str) -> bool:
        """Detect if content is a full publication (not an abstract).

        Publications typically:
        - Have filename patterns like "Batch-*_*.md" in Publications folder
        - Have main sections like "# Introduction", "# Methods", "# Results"
        - Are longer than abstracts (typically > 5000 chars)
        - Don't have "Abstract ID:" headers

        Args:
            content: Document content
            filename: Filename for pattern matching

        Returns:
            True if this appears to be a publication
        """
        # Check filename pattern (Publications folder)
        if "Publications" in filename or "publication" in filename.lower():
            return True

        # Check for publication structure (main sections with #)
        has_main_sections = (
            re.search(
                r"^#\s+(Introduction|Methods|Results|Discussion|Conclusion)",
                content,
                re.MULTILINE | re.IGNORECASE,
            )
            is not None
        )

        # Check for absence of abstract-specific markers
        has_abstract_id = "### Abstract ID:" in content or "Abstract ID:" in content

        # Check length (publications are typically much longer)
        is_long = len(content) > 5000

        # Publication if it has main sections, no abstract ID, and is long
        return has_main_sections and not has_abstract_id and is_long

    async def _chunk_publication(
        self,
        content: str,
        configuration: ChunkingConfiguration,
        document_id: Optional[str] = None,
        filename: str = "",
    ) -> list[Chunk]:
        """Chunk publication content with focus on Results section and tables.

        Strategy:
        1. Extract all tables separately
        2. Identify and prioritize Results section
        3. Chunk Results section with finer granularity
        4. Chunk other sections normally

        Args:
            content: Publication content
            configuration: Chunking configuration
            document_id: Document ID
            filename: Filename for metadata

        Returns:
            List of chunks with Results and tables prioritized
        """
        logger.info("Using publication-specific chunking strategy")

        # Step 1: Extract all tables separately with context
        table_data_list, content_without_tables = self._extract_tables_from_publication(
            content
        )

        # Step 2: Use publication-specific header splitter
        # Publications use #, ##, ### for main sections
        publication_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Main Section"),
                ("##", "Subsection"),
                ("###", "Subsubsection"),
            ],
            strip_headers=False,
        )

        # Step 3: Split content into sections
        langchain_documents = publication_splitter.split_text(content_without_tables)

        # Step 4: Process sections with special handling for Results
        chunks = []
        sequence_number = 0

        # First, add all tables as separate chunks (high priority)
        # Handle large tables by splitting them
        # For publications, use smaller max_chunk_size to minimize token consumption
        # Tables are often dense with information, so we split more aggressively
        max_chunk_size = (
            configuration.max_chunk_size or 2000
        )  # Reduced from 4000 for token efficiency
        for table_index, table_data in enumerate(table_data_list):
            # Split large tables if needed
            split_tables = self._split_large_table(table_data, max_chunk_size)

            for split_table in split_tables:
                table_chunk = self._create_table_chunk(
                    table_data=split_table,
                    document_id=document_id,
                    filename=filename,
                    sequence_number=sequence_number,
                    table_index=table_index,
                    total_tables=len(table_data_list),
                )
                chunks.append(table_chunk)
                sequence_number += 1

        # Then process sections, prioritizing Results (especially Efficacy)
        for document in langchain_documents:
            section_header = document.metadata.get("Main Section", "").lower()
            subsection_header = document.metadata.get("Subsection", "").lower()

            # Check if this is the Results section
            is_results_section = self._is_results_section(
                section_header, subsection_header
            )

            if is_results_section:
                # Special handling for Results/Findings section - chunk more finely
                # Efficacy/Findings subsections get the finest chunking
                is_efficacy = (
                    "efficacy" in subsection_header
                    or "efficacy" in section_header
                    or "finding" in subsection_header
                    or "finding" in section_header
                )
                section_name = subsection_header or section_header or "Results"
                logger.debug(
                    f"Processing Results/Findings section: {section_name} "
                    f"(Efficacy/Findings/Major Results: {is_efficacy})"
                )
                results_chunks = self._chunk_results_section(
                    document=document,
                    document_id=document_id,
                    filename=filename,
                    sequence_number=sequence_number,
                )
                chunks.extend(results_chunks)
                sequence_number += len(results_chunks)
            else:
                # Smart chunking for other sections (Introduction, Methods, Background, etc.)
                # Apply fine-grained chunking to minimize token consumption while preserving context
                # Information is usually in 2-4 lines, so we chunk all sections intelligently
                other_chunks = self._chunk_other_section(
                    document=document,
                    document_id=document_id,
                    filename=filename,
                    sequence_number=sequence_number,
                )
                chunks.extend(other_chunks)
                sequence_number += len(other_chunks)

        table_chunks = [c for c in chunks if c.chunk_type == ChunkType.TABLE]
        efficacy_chunks = sum(
            1
            for c in chunks
            if c.chunk_type == ChunkType.RESULTS
            and c.metadata.get("is_efficacy_subsection", False)
        )
        logger.info(
            f"Publication chunking complete: {len(chunks)} chunks created "
            f"({len(table_chunks)} table chunks, {sum(1 for c in chunks if c.chunk_type == ChunkType.RESULTS)} Results chunks, "
            f"{efficacy_chunks} Efficacy/Major Results chunks)"
        )
        return chunks

    def _chunk_other_section(
        self,
        document: Document,
        document_id: Optional[str],
        filename: str,
        sequence_number: int,
    ) -> list[Chunk]:
        """Chunk non-Results sections with smart, token-efficient chunking.

        Applies fine-grained chunking to all sections to minimize LLM token consumption
        while preserving context. Information is usually in 2-4 lines, so we use
        smaller chunks (300-400 chars) with good overlap.

        Args:
            document: LangChain Document containing section content
            document_id: Document ID
            filename: Filename
            sequence_number: Starting sequence number

        Returns:
            List of chunks from the section
        """
        content = document.page_content
        metadata = document.metadata.copy()

        # Determine section type for metadata
        section_type = metadata.get("Main Section", "").lower()
        subsection_type = metadata.get("Subsection", "").lower()

        # Use smart chunking for all sections
        # 350 chars ≈ 3-5 lines ≈ 85 tokens (good balance for non-Results sections)
        section_splitter = RecursiveCharacterTextSplitter(
            chunk_size=350,  # Optimized for token efficiency
            chunk_overlap=70,  # Preserve context (1-2 lines overlap)
            separators=["\n\n", "\n", ". ", ", ", " "],  # Respect boundaries
            length_function=len,
        )

        sub_texts = section_splitter.split_text(content)
        chunks = []

        for sub_index, sub_text in enumerate(sub_texts):
            sub_metadata = metadata.copy()
            sub_metadata["is_subchunk"] = True
            sub_metadata["subchunk_index"] = sub_index
            sub_metadata["total_subchunks"] = len(sub_texts)
            sub_metadata["section_type"] = section_type
            if subsection_type:
                sub_metadata["subsection_type"] = subsection_type

            chunk = self._create_chunk_from_text(
                content=sub_text,
                metadata=sub_metadata,
                document_id=document_id,
                filename=filename,
                sequence_number=sequence_number + sub_index,
            )
            chunks.append(chunk)

        return chunks

    def _extract_tables_from_publication(
        self, content: str
    ) -> tuple[list[dict[str, Any]], str]:
        """Extract all markdown tables from publication content with context.

        Tables are identified by markdown table syntax (| characters and --- separators).
        Each table is extracted with surrounding context, headers, and footnotes.

        Args:
            content: Publication content

        Returns:
            Tuple of (list of table data dicts, content with tables removed)
        """
        table_data_list = []
        lines = content.split("\n")
        content_lines = []
        current_table = []
        in_table = False
        table_start_line = -1

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Check if this line starts a table (has | and looks like table header)
            if "|" in stripped and not in_table:
                # Check if next line is a separator (---) or if this looks like a table
                # Some tables don't have separators, so check if line has multiple |
                pipe_count = stripped.count("|")
                if pipe_count >= 2:  # At least 2 pipes suggests a table row
                    # Check next line for separator or another table row
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if "---" in next_line or (
                            "|" in next_line and next_line.count("|") >= 2
                        ):
                            in_table = True
                            current_table = [line]
                            table_start_line = i
                            # If next line is separator, include it
                            if "---" in next_line:
                                current_table.append(lines[i + 1])
                                i += 1
                            i += 1
                            continue

            if in_table:
                current_table.append(line)
                # Table ends when we hit a line without | (and it's not just whitespace/formatting)
                if "|" not in stripped:
                    # Check if this is just a continuation (empty line, short line, or formatting)
                    if stripped == "" or len(stripped) < 20:
                        # Might be table continuation, check next few lines
                        found_continuation = False
                        for j in range(1, min(3, len(lines) - i)):  # Check next 2 lines
                            if i + j < len(lines) and "|" in lines[i + j].strip():
                                found_continuation = True
                                break

                        if found_continuation:
                            i += 1
                            continue

                    # Table has ended
                    table_content = "\n".join(current_table).strip()
                    if (
                        table_content and len(current_table) >= 2
                    ):  # At least header + 1 row
                        # Extract table with context
                        table_data = self._extract_table_with_context(
                            lines, table_start_line, i - 1
                        )
                        table_data_list.append(table_data)
                    current_table = []
                    in_table = False
                    table_start_line = -1
                    # Don't add empty/separator lines to content
                    if stripped != "" and not stripped.startswith("---"):
                        content_lines.append(line)
            else:
                content_lines.append(line)

            i += 1

        # Handle table that extends to end of document
        if in_table and current_table:
            table_content = "\n".join(current_table).strip()
            if table_content and len(current_table) >= 2:
                table_data = self._extract_table_with_context(
                    lines, table_start_line, len(lines) - 1
                )
                table_data_list.append(table_data)

        content_without_tables = "\n".join(content_lines)
        return table_data_list, content_without_tables

    def _is_results_section(self, main_section: str, subsection: str) -> bool:
        """Check if a section is the Results or Findings section.

        Results/Findings sections can be:
        - Main section: "# Results", "# Findings"
        - Subsection: "## Results", "## **Results:**", "## **Findings**"
        - Or subsections within Results: "## Efficacy", "## Adverse events", etc.

        Args:
            main_section: Main section header (lowercase)
            subsection: Subsection header (lowercase)

        Returns:
            True if this is a Results/Findings-related section
        """
        results_keywords = [
            "result",
            "finding",  # "Findings" sections often contain major results
            "clinical activity",  # "Clinical Activity" sections contain results data
            "summary",  # "Summary" sections may contain Results subsections (e.g., "Summary - Results")
            "efficacy",
            "safety",
            "adverse",
            "demographic",
            "response",
            "survival",
            "outcome",
        ]

        # Check main section
        if any(keyword in main_section for keyword in results_keywords):
            return True

        # Check subsection
        if any(keyword in subsection for keyword in results_keywords):
            return True

        return False

    def _chunk_results_section(
        self,
        document: Document,
        document_id: Optional[str],
        filename: str,
        sequence_number: int,
    ) -> list[Chunk]:
        """Chunk Results section with finer granularity, prioritizing Efficacy subsections.

        Results sections are chunked more finely to improve retrieval precision
        for numeric attributes and key findings. The Efficacy subsection (Major Results)
        gets the finest chunking for maximum precision.

        Args:
            document: LangChain Document containing Results section
            document_id: Document ID
            filename: Filename
            sequence_number: Starting sequence number

        Returns:
            List of chunks from Results section
        """
        content = document.page_content
        metadata = document.metadata.copy()
        main_section = metadata.get("Main Section", "").lower()
        subsection = metadata.get("Subsection", "").lower()

        # Check if this is the Efficacy/Findings subsection (Major Results)
        # Efficacy/Findings can appear as:
        # - Subsection header: "## **Efficacy**", "## **Findings**", "## Efficacy ORR and DOR"
        # - Within Results section content (embedded, no separate subsection)
        # - As part of the section name
        content_lower = content.lower()

        # Check for Efficacy/Findings in headers
        # "Findings" sections often contain the major results in condensed form
        has_efficacy_header = (
            "efficacy" in subsection
            or "efficacy" in main_section
            or "finding" in subsection
            or "finding"  # "Findings" is equivalent to Efficacy for prioritization
            in main_section
        )

        # Check for Efficacy/Findings content patterns in the text
        # Look for common efficacy indicators: ORR, overall survival, response rate, etc.
        has_efficacy_content = False
        if not has_efficacy_header:
            # Check if this Results/Findings section contains efficacy-related content
            efficacy_indicators = [
                "orr",
                "objective response rate",
                "overall survival",
                "progression-free survival",
                "response rate",
                "median overall survival",
                "hazard ratio",
                "complete response",
                "partial response",
            ]
            # Check first 1000 chars for efficacy indicators (key findings usually appear early)
            content_preview = content_lower[:1000]
            has_efficacy_content = any(
                indicator in content_preview for indicator in efficacy_indicators
            ) and (
                "median" in content_preview
                or "rate" in content_preview
                or "%" in content[:1000]
            )

        is_efficacy_subsection = (
            has_efficacy_header
            or (
                "##" in content
                and (
                    "**efficacy**" in content_lower[:300]
                    or "efficacy" in content_lower[:300]
                    or "**finding**" in content_lower[:300]
                    or "finding" in content_lower[:300]
                )
            )
            or (
                subsection == ""
                and (
                    "results" in main_section
                    or "finding" in main_section
                    or main_section == ""
                )
                and has_efficacy_content
            )
            or
            # Also check if this is a Results/Findings section with efficacy content but no explicit subsection
            (
                (
                    main_section == "results"
                    or main_section == "finding"
                    or "finding" in main_section
                )
                and subsection == ""
                and len(content) > 500
                and has_efficacy_content
            )
        )

        metadata["is_results_section"] = True
        metadata["is_prioritized"] = True
        if is_efficacy_subsection:
            metadata["is_efficacy_subsection"] = True
            metadata["is_major_results"] = True
            # Mark if this is a Findings section
            if "finding" in subsection or "finding" in main_section:
                metadata["is_findings_section"] = True

        # Use different chunk sizes based on whether this is Efficacy/Findings
        # Optimized for token efficiency: information is usually in 2-4 lines
        # Target: 200-300 chars (~50-75 tokens) to minimize LLM token consumption
        if is_efficacy_subsection:
            # Finest chunking for Efficacy/Findings (Major Results) - maximum precision
            # Both Efficacy and Findings sections contain key results and should be prioritized
            # 250 chars ≈ 2-4 lines of typical clinical text ≈ 60 tokens
            results_splitter = RecursiveCharacterTextSplitter(
                chunk_size=250,  # Optimized for 2-4 lines of information
                chunk_overlap=50,  # Preserve context across chunks (1-2 lines overlap)
                separators=[
                    "\n\n",
                    "\n",
                    ". ",
                    ", ",
                    " ",
                ],  # Respect paragraph/sentence boundaries
                length_function=len,
            )
        else:
            # Standard fine chunking for other Results subsections
            # 300 chars ≈ 3-5 lines ≈ 75 tokens
            results_splitter = RecursiveCharacterTextSplitter(
                chunk_size=300,  # Slightly larger for other Results sections
                chunk_overlap=60,  # Preserve context (1-2 lines overlap)
                separators=["\n\n", "\n", ". ", ", ", " "],
                length_function=len,
            )

        sub_texts = results_splitter.split_text(content)
        chunks = []

        for sub_index, sub_text in enumerate(sub_texts):
            sub_metadata = metadata.copy()
            sub_metadata["is_subchunk"] = True
            sub_metadata["parent_section"] = metadata.get(
                "Main Section"
            ) or metadata.get("Subsection", "")
            sub_metadata["subchunk_index"] = sub_index
            sub_metadata["total_subchunks"] = len(sub_texts)

            chunk = self._create_chunk_from_text(
                content=sub_text,
                metadata=sub_metadata,
                document_id=document_id,
                filename=filename,
                sequence_number=sequence_number + sub_index,
            )
            # Ensure chunk type is RESULTS
            chunk.chunk_type = ChunkType.RESULTS
            chunks.append(chunk)

        return chunks

    def _extract_table_with_context(
        self, lines: list[str], table_start: int, table_end: int
    ) -> dict[str, Any]:
        """Extract table with surrounding context, header, and footnotes.

        Args:
            lines: All lines of the document
            table_start: Starting line index of the table
            table_end: Ending line index of the table

        Returns:
            Dictionary containing table data with context
        """
        # Extract table content
        table_content = "\n".join(lines[table_start : table_end + 1]).strip()

        # Extract preceding context (2-5 lines before table)
        # Skip section headers (lines starting with #) and table-like content
        preceding_lines = []
        for i in range(max(0, table_start - 5), table_start):
            line = lines[i].strip()
            # Skip section headers, empty lines, and table-like content
            if (
                line
                and not line.startswith("#")
                and "|" not in line  # Skip table rows
                and not line.startswith("---")  # Skip separators
            ):
                preceding_lines.append(line)
        preceding_context = "\n".join(preceding_lines)

        # Extract following context (1-3 lines after table)
        # Skip section headers (lines starting with #) and table-like content
        following_lines = []
        for i in range(table_end + 1, min(len(lines), table_end + 4)):
            line = lines[i].strip()
            # Skip section headers, empty lines, and table-like content
            if (
                line
                and not line.startswith("#")
                and "|" not in line  # Skip table rows
                and not line.startswith("---")  # Skip separators
            ):
                following_lines.append(line)
        following_context = "\n".join(following_lines)

        # Detect table header/caption
        header = self._detect_table_header(lines, table_start, table_end)

        # Extract footnotes
        footnotes = self._extract_table_footnotes(lines, table_end)

        return {
            "table_content": table_content,
            "preceding_context": preceding_context,
            "following_context": following_context,
            "header": header,
            "footnotes": footnotes,
            "table_start": table_start,
            "table_end": table_end,
        }

    def _detect_table_header(
        self, lines: list[str], table_start: int, table_end: int
    ) -> str:
        """Detect table header/caption above or below table.

        Looks specifically for "Table X" patterns, not section headers.

        Args:
            lines: All lines of the document
            table_start: Starting line index of the table
            table_end: Ending line index of the table

        Returns:
            Table header/caption string, empty if not found
        """
        header = ""

        # Check above table (2-10 lines before)
        for i in range(max(0, table_start - 10), table_start):
            line = lines[i].strip()
            # Look specifically for "Table X" or "**Table X**" patterns
            # Must contain "Table" followed by a number
            if re.search(r"(?:\*\*)?Table\s+\d+", line, re.IGNORECASE):
                # Collect header lines until we hit the table
                # Stop if we encounter another "Table X" or section header
                header_lines = []
                for j in range(i, table_start):
                    line_j = lines[j].strip()
                    if line_j:
                        # Stop if we hit a section header or another table reference
                        if line_j.startswith("#") or (
                            j > i
                            and re.search(
                                r"(?:\*\*)?Table\s+\d+", line_j, re.IGNORECASE
                            )
                        ):
                            break
                        header_lines.append(line_j)
                if header_lines:
                    header = "\n".join(header_lines)
                break

        # If no header above, check below (within 3 lines)
        if not header:
            for i in range(table_end + 1, min(len(lines), table_end + 4)):
                line = lines[i].strip()
                if re.search(r"(?:\*\*)?Table\s+\d+", line, re.IGNORECASE):
                    header = line
                    break

        return header

    def _extract_table_footnotes(self, lines: list[str], table_end: int) -> str:
        """Extract footnotes associated with a table.

        Footnotes typically appear after the table and start with:
        - *, †, ‡, §, ¶
        - a., b., c.
        - <sup>*</sup>, <sup>†</sup>

        Args:
            lines: All lines of the document
            table_end: Ending line index of the table

        Returns:
            Footnotes string, empty if not found
        """
        footnotes = []
        footnote_patterns = [
            r"^[\*\†\‡\§\¶]",
            r"^[a-z]\.\s",
            r"<sup>[\*\†\‡\§\¶a-z]</sup>",
            r"^\*\*",
        ]

        # Check up to 10 lines after table
        for i in range(table_end + 1, min(len(lines), table_end + 11)):
            line = lines[i].strip()
            if not line:
                continue

            # Check if line matches footnote pattern
            is_footnote = False
            for pattern in footnote_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    footnotes.append(line)
                    is_footnote = True
                    break

            # If we hit a non-footnote line, stop (footnotes are usually consecutive)
            if not is_footnote and footnotes:
                break

        return "\n".join(footnotes)

    def _classify_table_type(self, table_data: dict[str, Any]) -> str:
        """Classify table type based on context and content.

        Checks table types sequentially and returns the first match.
        With strict keyword filters, no priority is needed between AE, TRAE, and TEAE.

        Args:
            table_data: Table data dictionary with context and header

        Returns:
            Table type string (e.g., "immune_related_ae", "treatment_related_ae", etc.)
        """
        # Focus on header and preceding context (most reliable)
        blob = (
            table_data.get("header", "") + " " + table_data.get("preceding_context", "")
        ).lower()

        # Check for Immune-Related (irAE)
        if any(
            x in blob
            for x in ["immune-related", "irae", "immune-mediated", "ir ae", "ir-ae"]
        ):
            return "immune_related_ae"

        # Check for Treatment-Related (TRAE)
        if any(
            x in blob
            for x in [
                "treatment-related",
                "trae",
                "drug-related",
                "related to study drug",
                "study-drug-related",
            ]
        ):
            return "treatment_related_ae"

        # Check for Treatment-Emergent (TEAE)
        if any(
            x in blob for x in ["treatment-emergent", "teae", "regardless of causality"]
        ):
            return "treatment_emergent_ae"

        # Generic AE Fallback (only if none of the above match)
        if "adverse event" in blob or "safety profile" in blob:
            return "adverse_events"

        # Check for other table types
        if any(
            term in blob
            for term in [
                "demographic",
                "baseline characteristic",
                "patient characteristic",
            ]
        ):
            return "baseline_characteristics"

        if any(
            term in blob
            for term in ["response", "orr", "overall survival", "pfs", "efficacy"]
        ):
            return "efficacy"

        return "other"

    def _split_large_table(
        self, table_data: dict[str, Any], max_chunk_size: int = 4000
    ) -> list[dict[str, Any]]:
        """Split large table into multiple chunks while preserving headers.

        When a table exceeds max_chunk_size, it's split into multiple chunks
        with headers and footnotes repeated in each chunk.

        Args:
            table_data: Table data dictionary
            max_chunk_size: Maximum chunk size in characters

        Returns:
            List of table data dicts, one per chunk
        """
        table_content = table_data["table_content"]

        # If table fits in one chunk, return as-is
        if len(table_content) <= max_chunk_size:
            return [table_data]

        lines = table_content.split("\n")

        # Extract column headers (first line with |)
        header_line = None
        separator_line = None
        data_rows = []

        for i, line in enumerate(lines):
            if "|" in line and header_line is None:
                header_line = line
                # Next line should be separator
                if i + 1 < len(lines) and "---" in lines[i + 1]:
                    separator_line = lines[i + 1]
                    data_start = i + 2
                else:
                    data_start = i + 1
                break

        # Extract data rows
        for i in range(data_start, len(lines)):
            if "|" in lines[i]:
                data_rows.append(lines[i])

        # Extract footnotes
        footnotes = table_data.get("footnotes", "")

        # Split data rows into chunks (e.g., 20 rows per chunk)
        rows_per_chunk = 20
        chunks = []

        for chunk_idx in range(0, len(data_rows), rows_per_chunk):
            chunk_rows = data_rows[chunk_idx : chunk_idx + rows_per_chunk]

            # Build chunk content
            chunk_content_lines = []

            # Add header with continuation marker if not first chunk
            header_text = table_data.get("header", "")
            if chunk_idx > 0 and header_text:
                header_text += " (continued)"
            if header_text:
                chunk_content_lines.append(header_text)
                chunk_content_lines.append("")

            # Add column headers (REPEATED in every chunk)
            if header_line:
                chunk_content_lines.append(header_line)
            if separator_line:
                chunk_content_lines.append(separator_line)

            # Add data rows for this chunk
            chunk_content_lines.extend(chunk_rows)

            # Add footnotes (REPEATED in every chunk)
            if footnotes:
                chunk_content_lines.append("")
                chunk_content_lines.append(footnotes)

            chunk_content = "\n".join(chunk_content_lines)

            # Create chunk data
            chunk_data = table_data.copy()
            chunk_data["table_content"] = chunk_content
            chunk_data["is_split_chunk"] = True
            chunk_data["chunk_index"] = chunk_idx // rows_per_chunk
            chunk_data["total_chunks"] = (
                len(data_rows) + rows_per_chunk - 1
            ) // rows_per_chunk

            chunks.append(chunk_data)

        return chunks

    @staticmethod
    def _normalize_html_in_table_text(text: str) -> str:
        """Replace HTML artifacts from PDF→Markdown conversion in table content."""
        text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<sup>.*?</sup>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<sub>.*?</sub>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def _create_table_chunk(
        self,
        table_data: dict[str, Any],
        document_id: Optional[str],
        filename: str,
        sequence_number: int,
        table_index: int,
        total_tables: int,
    ) -> Chunk:
        """Create a chunk for a table with enhanced metadata.

        Args:
            table_data: Table data dictionary with content, context, header, footnotes
            document_id: Document ID
            filename: Filename
            sequence_number: Sequence number
            table_index: Index of this table (0-based)
            total_tables: Total number of tables in document

        Returns:
            Chunk containing the table
        """
        # Classify table type
        table_type = self._classify_table_type(table_data)

        # Build chunk content with context
        content_parts = []

        def _norm(s: str) -> str:
            return self._normalize_html_in_table_text(s) if s else s

        # Add header if present
        if table_data.get("header"):
            content_parts.append(_norm(table_data["header"]))
            content_parts.append("")

        # Add preceding context
        if table_data.get("preceding_context"):
            content_parts.append(_norm(table_data["preceding_context"]))
            content_parts.append("")

        # Add table content
        content_parts.append(_norm(table_data["table_content"]))

        # Add footnotes (if not already in table_content from split)
        if table_data.get("footnotes") and not table_data.get("is_split_chunk"):
            content_parts.append("")
            content_parts.append(_norm(table_data["footnotes"]))

        # Add following context (if not footnotes)
        if table_data.get("following_context") and not table_data.get("footnotes"):
            content_parts.append("")
            content_parts.append(_norm(table_data["following_context"]))

        content = "\n".join(content_parts)

        # Build metadata
        metadata = {
            "is_table": True,
            "is_prioritized": True,
            "table_index": table_index,
            "total_tables": total_tables,
            "table_type": table_type,
            "has_header": bool(table_data.get("header")),
            "has_footnotes": bool(table_data.get("footnotes")),
        }

        # Add split chunk metadata if applicable
        if table_data.get("is_split_chunk"):
            metadata["is_split_chunk"] = True
            metadata["chunk_index"] = table_data.get("chunk_index", 0)
            metadata["total_chunks"] = table_data.get("total_chunks", 1)

        chunk = self._create_chunk_from_text(
            content=content,
            metadata=metadata,
            document_id=document_id,
            filename=filename,
            sequence_number=sequence_number,
        )
        # Ensure chunk type is TABLE
        chunk.chunk_type = ChunkType.TABLE
        return chunk
