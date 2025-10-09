"""Tests for LangChain chunking service."""

import sys
from pathlib import Path
from uuid import uuid4

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.app.langchain_factory_service import (  # noqa: E402
    LangChainServiceFactory,
    ServiceConfiguration,
)
from src.domain.models import (  # noqa: E402
    ChunkingConfiguration,
    ChunkingStrategy,
    ChunkType,
)


@pytest.fixture
def sample_abstract():
    """Sample abstract content for testing."""
    return """### Abstract ID: 10000
**Title:** Pembrolizumab versus placebo after complete resection of high-risk stage III melanoma

#### Background:
We conducted the phase 3 double-blind EORTC 1325/KEYNOTE-054 trial to evaluate pembrolizumab vs placebo in patients with resected high-risk stage III melanoma.

#### Methods:
Eligible pts included those ≥18 yrs of age with complete resection of cutaneous melanoma metastatic to lymph node(s).

#### Results:
Overall, 15%/46%/39% of pts had stage IIIA/IIIB/IIIC. At 3.05-yr median follow-up, pembrolizumab prolonged RFS.

#### Conclusions:
Pembrolizumab provided a sustained improvement in RFS in resected high-risk stage III melanoma.

**Clinical trial information:** NCT02362594.

**Research Sponsor:** Merck"""


@pytest.fixture
def default_config():
    """Default chunking configuration."""
    return ChunkingConfiguration(
        strategy=ChunkingStrategy.HEADER_BASED, max_chunk_size=1000, chunk_overlap=200
    )


class TestLangChainChunkingService:
    """Test LangChain chunking service."""

    @pytest.fixture
    def strategy(self, default_config):
        config = ServiceConfiguration(
            chunking_strategy="header_based",
            embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
            llm_provider="openai",
            llm_model="gpt-3.5-turbo",
            temperature=0.1,
            persist_directory="./test_chroma_db",
            collection_name="test_chunks",
        )
        factory = LangChainServiceFactory(config)
        return factory.create_chunking_service()

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
        assert all(chunk.document_id == str(document_id) for chunk in chunks)

        # Check that we have different chunk types
        chunk_types = {chunk.chunk_type for chunk in chunks}
        assert len(chunk_types) > 1

        # Check that we have header chunks
        header_chunks = [
            chunk for chunk in chunks if chunk.chunk_type == ChunkType.ABSTRACT_HEADER
        ]
        assert len(header_chunks) > 0

        # Check that we have content chunks
        content_chunks = [
            chunk
            for chunk in chunks
            if chunk.chunk_type
            in [
                ChunkType.BACKGROUND,
                ChunkType.METHODS,
                ChunkType.RESULTS,
                ChunkType.CONCLUSIONS,
            ]
        ]
        assert len(content_chunks) > 0

    @pytest.mark.asyncio
    async def test_metadata_extraction(self, strategy, sample_abstract, default_config):
        """Test metadata extraction from chunks."""
        document_id = uuid4()

        chunks = await strategy.chunk_content(
            content=sample_abstract,
            configuration=default_config,
            document_id=str(document_id),
            filename="ASCO_2020.md",
        )

        # Find metadata chunk
        metadata_chunk = next(
            (chunk for chunk in chunks if "sponsor" in chunk.metadata), None
        )
        assert metadata_chunk is not None
        assert "sponsor" in metadata_chunk.metadata
        assert metadata_chunk.metadata["sponsor"] == "Merck"

    def test_supports_configuration(self, strategy, default_config):
        """Test configuration support check."""
        assert strategy.supports_configuration(default_config)

        # Test with different strategy
        unsupported_config = ChunkingConfiguration(strategy=ChunkingStrategy.RECURSIVE)
        assert not strategy.supports_configuration(unsupported_config)

    @pytest.mark.asyncio
    async def test_empty_content(self, strategy, default_config):
        """Test handling of empty content."""
        chunks = await strategy.chunk_content(
            content="",
            configuration=default_config,
            document_id=str(uuid4()),
            filename="empty.md",
        )
        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_whitespace_only_content(self, strategy, default_config):
        """Test handling of whitespace-only content."""
        chunks = await strategy.chunk_content(
            content="   \n\n   \t   \n   ",
            configuration=default_config,
            document_id=str(uuid4()),
            filename="whitespace.md",
        )
        assert len(chunks) == 0
