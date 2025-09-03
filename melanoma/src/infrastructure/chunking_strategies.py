"""Implementation of various chunking strategies for oncology abstracts."""

import re
from typing import Any
from uuid import UUID, uuid4

from domain.interfaces import ChunkingStrategyInterface
from domain.models import Chunk, ChunkingConfiguration, ChunkingStrategy, ChunkType


class BaseChunkingStrategy(ChunkingStrategyInterface):
    """Base class for chunking strategies."""

    def __init__(self):
        self.supported_strategies = []

    def supports_configuration(self, configuration: ChunkingConfiguration) -> bool:
        """Check if this strategy supports the given configuration."""
        return configuration.strategy in self.supported_strategies

    def _extract_metadata_from_content(
        self, content: str, filename: str = ""
    ) -> dict[str, Any]:
        """Extract metadata from abstract content."""
        metadata = {}

        # Extract year from filename (ASCO and ESMO formats)
        year_patterns = [
            r"ASCO_(\d{4})",
            r"ESMO_(\d{4})",
            r"(\d{4})",  # Generic year pattern
        ]

        for pattern in year_patterns:
            year_match = re.search(pattern, filename)
            if year_match:
                metadata["year"] = int(year_match.group(1))
                break

        # Extract abstract ID (handle both ASCO numeric and ESMO alphanumeric)
        abstract_id_patterns = [
            r"### Abstract ID: ([0-9]+[A-Z]*)",  # ESMO format like 1076O, 1077MO
            r"### Abstract ID: (\d+)",  # ASCO format like 10000
            r"Abstract ID: ([0-9]+[A-Z]*)",  # Alternative format
        ]

        for pattern in abstract_id_patterns:
            abstract_id_match = re.search(pattern, content)
            if abstract_id_match:
                # Preserve the original abstract ID format (including ESMO letter suffixes)
                metadata["abstract_id"] = abstract_id_match.group(1)
                break

        # Extract clinical trial ID
        trial_match = re.search(r"NCT\d+", content)
        if trial_match:
            metadata["clinical_trial_id"] = trial_match.group(0)

        # Extract sponsor (ASCO and ESMO formats)
        sponsor_patterns = [
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

        for pattern in sponsor_patterns:
            sponsor_match = re.search(pattern, content, re.IGNORECASE)
            if sponsor_match:
                sponsor = sponsor_match.group(1).strip()
                # Clean up common suffixes and artifacts
                sponsor = re.sub(r"\.$", "", sponsor)  # Remove trailing period
                sponsor = re.sub(
                    r"\s*##.*$", "", sponsor
                )  # Remove ## and anything after
                if sponsor and sponsor != "##":  # Skip empty or artifact sponsors
                    metadata["sponsor"] = sponsor
                    break

        # Extract title
        title_match = re.search(r"\*\*Title:\*\* (.+)", content)
        if title_match:
            metadata["title"] = title_match.group(1).strip()

        # Check if content contains tables
        metadata["has_table"] = "|" in content and "---" in content

        return metadata

    def _determine_chunk_type(self, content: str, headers: dict[str, str]) -> ChunkType:
        """Determine the type of chunk based on content and headers."""
        section = headers.get("Section", "").lower()
        content_lower = content.lower()

        # Abstract header detection
        if "abstract id" in content_lower and "**title:**" in content_lower:
            return ChunkType.ABSTRACT_HEADER

        # Section-based detection (ASCO & ESMO) - prioritize over table detection
        if "background" in section or "#### background:" in content_lower:
            return ChunkType.BACKGROUND
        elif (
            "method" in section
            or "trial design" in section
            or "#### methods:" in content_lower
            or "#### trial design:" in content_lower
        ):
            # Check if it's specifically Trial Design (ESMO)
            if "trial design" in section or "#### trial design:" in content_lower:
                return ChunkType.TRIAL_DESIGN
            else:
                return ChunkType.METHODS
        # Study Results sections (tables) - check first to avoid confusion with "results"
        elif "#### study results:" in content_lower or "study results" in section:
            return ChunkType.TABLE
        elif "result" in section or "#### results:" in content_lower:
            return ChunkType.RESULTS
        elif "conclusion" in section or "#### conclusions:" in content_lower:
            return ChunkType.CONCLUSIONS

        # Specific metadata section detection (enhanced postprocessing)
        elif (
            "#### clinical trial information:" in content_lower
            or "#### clinical trial identification:" in content_lower
        ):
            return ChunkType.CLINICAL_TRIAL
        elif "#### research sponsor:" in content_lower:
            return ChunkType.SPONSOR
        elif "#### legal entity responsible for study:" in content_lower:
            return ChunkType.LEGAL_ENTITY
        elif "#### funding:" in content_lower:
            return ChunkType.FUNDING
        elif "#### doi:" in content_lower:
            return ChunkType.DOI
        elif "#### full text reference:" in content_lower:
            return ChunkType.FULL_TEXT_REFERENCE

        # Legacy metadata detection (backward compatibility)
        elif self._is_metadata_section(content):
            return ChunkType.FULL_ABSTRACT

        # Only check for pure table content if no section headers are detected
        elif self._is_table_content(content) and not any(
            header in content_lower
            for header in [
                "#### background:",
                "#### methods:",
                "#### results:",
                "#### conclusions:",
                "#### trial design:",
            ]
        ):
            return ChunkType.TABLE
        else:
            return ChunkType.FULL_ABSTRACT

    def _is_metadata_section(self, content: str) -> bool:
        """Check if content is primarily metadata (Clinical trial info, sponsors, etc.)."""
        # Check for enhanced header-based metadata sections
        enhanced_metadata_headers = [
            "#### Clinical Trial Information:",
            "#### Research Sponsor:",
            "#### Clinical Trial Identification:",
            "#### Legal Entity Responsible for Study:",
            "#### Funding:",
            "#### DOI:",
            "#### Full Text Reference:",
            "#### Study Results:",
        ]

        # Also check for legacy inline metadata (backward compatibility)
        legacy_metadata_indicators = [
            "**Clinical trial information:**",
            "**Research Sponsor:**",
            "**Clinical trial identification:**",
            "**Legal entity responsible for the study:**",
            "**Funding:**",
            "**DOI:**",
        ]

        return any(header in content for header in enhanced_metadata_headers) or any(
            indicator in content for indicator in legacy_metadata_indicators
        )

    def _is_table_content(self, content: str) -> bool:
        """Check if content is primarily a table."""
        lines = content.strip().split("\n")
        table_lines = sum(1 for line in lines if "|" in line)
        return table_lines > len(lines) * 0.3  # 30% threshold


class HeaderBasedChunkingStrategy(BaseChunkingStrategy):
    """Chunking strategy based on markdown headers."""

    def __init__(self):
        super().__init__()
        self.supported_strategies = [ChunkingStrategy.HEADER_BASED]

    async def chunk_content(
        self,
        content: str,
        configuration: ChunkingConfiguration,
        document_id: str | None = None,
        filename: str = "",
    ) -> list[Chunk]:
        """Chunk content based on markdown headers."""
        chunks: list[Chunk] = []

        # Split content by main headers (### Abstract ID)
        abstracts = re.split(r"\n### Abstract ID: ", content)

        for i, abstract_content in enumerate(abstracts):
            if i == 0 and not abstract_content.strip():
                continue

            # Add back the header if it was removed by split
            if not abstract_content.startswith("### Abstract ID:"):
                abstract_content = "### Abstract ID: " + abstract_content

            # Extract base metadata
            base_metadata = self._extract_metadata_from_content(
                abstract_content, filename
            )

            # Split by section headers (#### Background, #### Methods, etc.)
            sections = re.split(r"\n#### ", abstract_content)

            for j, section in enumerate(sections):
                if not section.strip():
                    continue

                # Add back the header if it was removed by split
                if j > 0 and not section.startswith("####"):
                    section = "#### " + section

                # Create chunk metadata
                chunk_metadata = base_metadata.copy()

                # Determine chunk type
                headers = {
                    "Section": section.split("\n")[0]
                    if section.startswith("####")
                    else ""
                }
                chunk_type = self._determine_chunk_type(section, headers)

                # Add section-specific metadata
                chunk_metadata["section_header"] = headers["Section"]

                # Only override to TABLE if it's primarily a table (not a section with embedded tables)
                if (
                    configuration.preserve_tables
                    and self._is_table_content(section)
                    and chunk_type == ChunkType.FULL_ABSTRACT
                ):  # Only for unclassified content
                    chunk_type = ChunkType.TABLE

                # Create the chunk
                chunk = Chunk(
                    document_id=UUID(document_id)
                    if isinstance(document_id, str)
                    else (document_id if document_id else uuid4()),
                    content=section.strip(),
                    chunk_type=chunk_type,
                    metadata=chunk_metadata,
                    sequence_number=len(chunks),
                    token_count=len(section.split()),  # Rough token count
                )

                chunks.append(chunk)

        return chunks


class RecursiveChunkingStrategy(BaseChunkingStrategy):
    """Recursive chunking strategy for large content."""

    def __init__(self):
        super().__init__()
        self.supported_strategies = [ChunkingStrategy.RECURSIVE]

    async def chunk_content(
        self,
        content: str,
        configuration: ChunkingConfiguration,
        document_id: str | None = None,
        filename: str = "",
    ) -> list[Chunk]:
        """Chunk content recursively based on size limits."""
        chunks: list[Chunk] = []
        base_metadata = self._extract_metadata_from_content(content, filename)

        # Define separators in order of preference
        separators = ["\n\n", "\n", ". ", " ", ""]

        def _split_text(text: str, max_size: int, overlap: int) -> list[str]:
            """Recursively split text."""
            if len(text) <= max_size:
                return [text]

            # Try each separator
            for separator in separators:
                if separator in text:
                    # Split by separator
                    parts = text.split(separator)

                    # Recombine parts that are too small
                    result = []
                    current_chunk = ""

                    for part in parts:
                        test_chunk = (
                            current_chunk + separator + part if current_chunk else part
                        )

                        if len(test_chunk) <= max_size:
                            current_chunk = test_chunk
                        else:
                            if current_chunk:
                                result.append(current_chunk)
                                # Add overlap
                                overlap_text = (
                                    current_chunk[-overlap:] if overlap > 0 else ""
                                )
                                current_chunk = (
                                    overlap_text + separator + part
                                    if overlap_text
                                    else part
                                )
                            else:
                                current_chunk = part

                    if current_chunk:
                        result.append(current_chunk)

                    return result

            # If no separator works, split by character count
            result = []
            for i in range(0, len(text), max_size - overlap):
                chunk = text[i : i + max_size]
                result.append(chunk)

            return result

        # Split the content
        text_chunks = _split_text(
            content, configuration.max_chunk_size, configuration.chunk_overlap
        )

        for i, text_chunk in enumerate(text_chunks):
            chunk_metadata = base_metadata.copy()
            chunk_metadata["chunk_method"] = "recursive"

            # Determine chunk type
            chunk_type = self._determine_chunk_type(text_chunk, {})

            chunk = Chunk(
                document_id=UUID(document_id)
                if isinstance(document_id, str)
                else (document_id if document_id else uuid4()),
                content=text_chunk.strip(),
                chunk_type=chunk_type,
                metadata=chunk_metadata,
                sequence_number=i,
                token_count=len(text_chunk.split()),
            )

            chunks.append(chunk)

        return chunks


class HybridChunkingStrategy(BaseChunkingStrategy):
    """Hybrid strategy combining header-based and recursive chunking."""

    def __init__(self):
        super().__init__()
        self.supported_strategies = [ChunkingStrategy.HYBRID]
        self.header_strategy = HeaderBasedChunkingStrategy()
        self.recursive_strategy = RecursiveChunkingStrategy()

    async def chunk_content(
        self,
        content: str,
        configuration: ChunkingConfiguration,
        document_id: str | None = None,
        filename: str = "",
    ) -> list[Chunk]:
        """Use header-based chunking first, then recursive for large chunks."""
        # First, use header-based chunking
        header_chunks = await self.header_strategy.chunk_content(
            content, configuration, document_id, filename
        )

        final_chunks: list[Chunk] = []

        for chunk in header_chunks:
            # If chunk is too large, apply recursive chunking
            if len(chunk.content) > configuration.max_chunk_size:
                recursive_chunks = await self.recursive_strategy.chunk_content(
                    chunk.content, configuration, document_id, filename
                )

                # Preserve original chunk metadata and type
                for i, recursive_chunk in enumerate(recursive_chunks):
                    recursive_chunk.chunk_type = chunk.chunk_type
                    recursive_chunk.metadata.update(chunk.metadata)
                    recursive_chunk.metadata["sub_chunk_index"] = i
                    recursive_chunk.sequence_number = len(final_chunks)
                    final_chunks.append(recursive_chunk)
            else:
                chunk.sequence_number = len(final_chunks)
                final_chunks.append(chunk)

        return final_chunks


class ChunkingStrategyFactory:
    """Factory for creating chunking strategies."""

    _strategies = {
        ChunkingStrategy.HEADER_BASED: HeaderBasedChunkingStrategy,
        ChunkingStrategy.RECURSIVE: RecursiveChunkingStrategy,
        ChunkingStrategy.HYBRID: HybridChunkingStrategy,
    }

    @classmethod
    def create_strategy(
        cls, strategy_type: ChunkingStrategy
    ) -> ChunkingStrategyInterface:
        """Create a chunking strategy instance."""
        if strategy_type not in cls._strategies:
            raise ValueError(f"Unsupported chunking strategy: {strategy_type}")

        return cls._strategies[strategy_type]()

    @classmethod
    def get_available_strategies(cls) -> list[ChunkingStrategy]:
        """Get list of available strategies."""
        return list(cls._strategies.keys())
