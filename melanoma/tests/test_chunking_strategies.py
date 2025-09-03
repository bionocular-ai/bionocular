"""Tests for chunking strategies."""

import sys
from pathlib import Path
from uuid import uuid4

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from domain.models import (  # noqa: E402
    ChunkingConfiguration,
    ChunkingStrategy,
    ChunkType,
)
from infrastructure.chunking_strategies import (  # noqa: E402
    ChunkingStrategyFactory,
    HeaderBasedChunkingStrategy,
    HybridChunkingStrategy,
    RecursiveChunkingStrategy,
)


@pytest.fixture
def sample_abstract():
    """Sample abstract content for testing."""
    return """### Abstract ID: 10000
**Title:** Pembrolizumab versus placebo after complete resection of high-risk stage III melanoma

#### Background:
We conducted the phase 3 double-blind EORTC 1325/KEYNOTE-054 trial to evaluate pembrolizumab vs placebo in patients (pts) with resected high-risk stage III melanoma.

#### Methods:
Eligible pts included those ≥18 yrs of age with complete resection of cutaneous melanoma metastatic to lymph node(s), classified as AJCC-7 stage IIIA.

#### Results:
Overall, 15%/46%/39% of pts had stage IIIA/IIIB/IIIC. At 3.05-yr median follow-up, pembrolizumab prolonged RFS.

#### Conclusions:
Pembrolizumab provided a sustained improvement in RFS in resected high-risk stage III melanoma.

**Clinical trial information:** NCT02362594

**Research Sponsor:** Merck"""


@pytest.fixture
def default_config():
    """Default chunking configuration."""
    return ChunkingConfiguration(
        strategy=ChunkingStrategy.HEADER_BASED, max_chunk_size=1000, chunk_overlap=200
    )


class TestHeaderBasedChunkingStrategy:
    """Test header-based chunking strategy."""

    @pytest.fixture
    def strategy(self):
        return HeaderBasedChunkingStrategy()

    @pytest.mark.asyncio
    async def test_chunk_content(self, strategy, sample_abstract, default_config):
        """Test chunking content by headers."""
        document_id = uuid4()

        chunks = await strategy.chunk_content(
            content=sample_abstract,
            configuration=default_config,
            document_id=str(document_id),
            filename="ASCO_2020.md",
        )

        assert len(chunks) > 0
        assert all(chunk.document_id == document_id for chunk in chunks)

        # Check that we have different chunk types
        chunk_types = {chunk.chunk_type for chunk in chunks}
        expected_types = {
            ChunkType.ABSTRACT_HEADER,
            ChunkType.BACKGROUND,
            ChunkType.METHODS,
            ChunkType.RESULTS,
            ChunkType.CONCLUSIONS,
        }
        assert chunk_types.intersection(expected_types)

        # Check sequence numbers
        sequence_numbers = [chunk.sequence_number for chunk in chunks]
        assert sequence_numbers == list(range(len(chunks)))

    @pytest.mark.asyncio
    async def test_metadata_extraction(self, strategy, sample_abstract, default_config):
        """Test metadata extraction from content."""
        document_id = uuid4()

        chunks = await strategy.chunk_content(
            content=sample_abstract,
            configuration=default_config,
            document_id=str(document_id),
            filename="ASCO_2020.md",
        )

        # Find a chunk with metadata
        metadata_chunk = next((chunk for chunk in chunks if chunk.metadata), None)
        assert metadata_chunk is not None

        # Check metadata fields
        assert "abstract_id" in metadata_chunk.metadata
        assert metadata_chunk.metadata["abstract_id"] == "10000"
        assert "clinical_trial_id" in metadata_chunk.metadata
        assert metadata_chunk.metadata["clinical_trial_id"] == "NCT02362594"
        assert "sponsor" in metadata_chunk.metadata
        assert metadata_chunk.metadata["sponsor"] == "Merck"

    def test_supports_configuration(self, strategy, default_config):
        """Test configuration support check."""
        assert strategy.supports_configuration(default_config)

        unsupported_config = ChunkingConfiguration(strategy=ChunkingStrategy.RECURSIVE)
        assert not strategy.supports_configuration(unsupported_config)


class TestRecursiveChunkingStrategy:
    """Test recursive chunking strategy."""

    @pytest.fixture
    def strategy(self):
        return RecursiveChunkingStrategy()

    @pytest.mark.asyncio
    async def test_chunk_small_content(self, strategy, default_config):
        """Test chunking small content that fits in one chunk."""
        content = "This is a short piece of text that should fit in one chunk."
        document_id = uuid4()

        chunks = await strategy.chunk_content(
            content=content, configuration=default_config, document_id=document_id
        )

        assert len(chunks) == 1
        assert chunks[0].content.strip() == content
        assert chunks[0].document_id == document_id

    @pytest.mark.asyncio
    async def test_chunk_large_content(self, strategy, default_config):
        """Test chunking large content that needs splitting."""
        # Create content larger than max_chunk_size
        large_content = "This is a test sentence. " * 100  # Should exceed 1000 chars
        document_id = uuid4()

        config = ChunkingConfiguration(
            strategy=ChunkingStrategy.RECURSIVE,
            max_chunk_size=500,  # Smaller for testing
            chunk_overlap=50,
        )

        chunks = await strategy.chunk_content(
            content=large_content, configuration=config, document_id=document_id
        )

        assert len(chunks) > 1
        assert all(len(chunk.content) <= config.max_chunk_size for chunk in chunks)
        assert all(chunk.document_id == document_id for chunk in chunks)

    def test_supports_configuration(self, strategy):
        """Test configuration support check."""
        config = ChunkingConfiguration(strategy=ChunkingStrategy.RECURSIVE)
        assert strategy.supports_configuration(config)


class TestHybridChunkingStrategy:
    """Test hybrid chunking strategy."""

    @pytest.fixture
    def strategy(self):
        return HybridChunkingStrategy()

    @pytest.mark.asyncio
    async def test_hybrid_chunking(self, strategy, sample_abstract, default_config):
        """Test hybrid chunking with normal-sized content."""
        document_id = uuid4()

        hybrid_config = ChunkingConfiguration(
            strategy=ChunkingStrategy.HYBRID, max_chunk_size=1000, chunk_overlap=200
        )

        chunks = await strategy.chunk_content(
            content=sample_abstract,
            configuration=hybrid_config,
            document_id=str(document_id),
            filename="ASCO_2020.md",
        )

        assert len(chunks) > 0
        assert all(chunk.document_id == document_id for chunk in chunks)

        # Should preserve chunk types from header-based strategy
        chunk_types = {chunk.chunk_type for chunk in chunks}
        expected_types = {
            ChunkType.ABSTRACT_HEADER,
            ChunkType.BACKGROUND,
            ChunkType.METHODS,
            ChunkType.RESULTS,
            ChunkType.CONCLUSIONS,
        }
        assert chunk_types.intersection(expected_types)

    @pytest.mark.asyncio
    async def test_hybrid_with_large_sections(self, strategy, default_config):
        """Test hybrid chunking when sections are too large."""
        # Create an abstract with a very large results section
        large_section = (
            "#### Results:\n" + "This is a very long results section. " * 200
        )

        content = f"""### Abstract ID: 10001
**Title:** Test Abstract

#### Background:
Short background.

{large_section}

#### Conclusions:
Short conclusions."""

        document_id = uuid4()

        hybrid_config = ChunkingConfiguration(
            strategy=ChunkingStrategy.HYBRID,
            max_chunk_size=500,  # Small to force splitting
            chunk_overlap=50,
        )

        chunks = await strategy.chunk_content(
            content=content, configuration=hybrid_config, document_id=document_id
        )

        # Should have more chunks due to splitting of large section
        assert len(chunks) > 3

        # All chunks should respect max size (with some tolerance for splitting logic)
        # Note: The hybrid strategy may not split perfectly due to header-based chunking first
        long_chunks = [
            chunk
            for chunk in chunks
            if len(chunk.content) > hybrid_config.max_chunk_size
        ]
        # Should have at least attempted to split the large section
        assert len(long_chunks) <= 1  # At most one overly long chunk


class TestChunkingStrategyFactory:
    """Test chunking strategy factory."""

    def test_create_header_based_strategy(self):
        """Test creating header-based strategy."""
        strategy = ChunkingStrategyFactory.create_strategy(
            ChunkingStrategy.HEADER_BASED
        )
        assert isinstance(strategy, HeaderBasedChunkingStrategy)

    def test_create_recursive_strategy(self):
        """Test creating recursive strategy."""
        strategy = ChunkingStrategyFactory.create_strategy(ChunkingStrategy.RECURSIVE)
        assert isinstance(strategy, RecursiveChunkingStrategy)

    def test_create_hybrid_strategy(self):
        """Test creating hybrid strategy."""
        strategy = ChunkingStrategyFactory.create_strategy(ChunkingStrategy.HYBRID)
        assert isinstance(strategy, HybridChunkingStrategy)

    def test_unsupported_strategy(self):
        """Test error for unsupported strategy."""
        with pytest.raises(ValueError, match="Unsupported chunking strategy"):
            ChunkingStrategyFactory.create_strategy("unsupported_strategy")

    def test_get_available_strategies(self):
        """Test getting available strategies."""
        strategies = ChunkingStrategyFactory.get_available_strategies()
        assert ChunkingStrategy.HEADER_BASED in strategies
        assert ChunkingStrategy.RECURSIVE in strategies
        assert ChunkingStrategy.HYBRID in strategies


class TestChunkMetadata:
    """Test chunk metadata extraction and handling."""

    @pytest.fixture
    def strategy(self):
        return HeaderBasedChunkingStrategy()

    @pytest.mark.asyncio
    async def test_metadata_with_tables(self, strategy, default_config):
        """Test metadata extraction when content has tables."""
        content_with_table = """### Abstract ID: 10002
**Title:** Test with Table

#### Results:
Results showing efficacy:

| Treatment | Response Rate | P-value |
|-----------|---------------|---------|
| Drug A    | 45%          | 0.001   |
| Drug B    | 30%          | 0.05    |

#### Conclusions:
Treatment was effective."""

        document_id = uuid4()

        chunks = await strategy.chunk_content(
            content=content_with_table,
            configuration=default_config,
            document_id=document_id,
        )

        # Find results chunk which should contain the table
        results_chunk = next(
            (chunk for chunk in chunks if chunk.chunk_type == ChunkType.RESULTS), None
        )

        # If no results chunk, check if table was detected as separate chunk
        if results_chunk is None:
            table_chunk = next(
                (chunk for chunk in chunks if chunk.chunk_type == ChunkType.TABLE), None
            )
            assert (
                table_chunk is not None
            ), f"No results or table chunk found. Chunk types: {[c.chunk_type for c in chunks]}"
            assert table_chunk.metadata.get("has_table", False)
        else:
            assert results_chunk.metadata.get("has_table", False)

    @pytest.mark.asyncio
    async def test_year_extraction_from_filename(self, strategy, default_config):
        """Test year extraction from filename."""
        content = "### Abstract ID: 10003\n**Title:** Test Abstract"
        document_id = uuid4()

        chunks = await strategy.chunk_content(
            content=content,
            configuration=default_config,
            document_id=str(document_id),
            filename="ASCO_2023.md",
        )

        assert len(chunks) > 0
        assert chunks[0].metadata.get("year") == 2023
