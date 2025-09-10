#!/usr/bin/env python3
"""
Embedding and Indexing Demo

This script demonstrates the complete embedding and indexing pipeline with real melanoma data.
Shows the system processing real ASCO abstracts, generating embeddings, and performing searches.

Usage:
    python demo_embedding_indexing.py
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any

# Domain imports
from src.domain.constants import EmbeddingDefaults, ChunkingDefaults
from src.domain.models import (
    ChunkWithEmbedding,
    EmbeddingConfiguration,
    EmbeddingModel,
    SearchQuery,
    ChunkingConfiguration
)

# Infrastructure imports
from src.infrastructure.chunking_strategies import ChunkingStrategyFactory
from src.infrastructure.embedding_service import BioClinicalEmbeddingService
from src.infrastructure.vector_store import ChromaVectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmbeddingIndexingDemo:
    """Demo for embedding and indexing pipeline."""
    
    def __init__(self, data_dir: str = "data/processed/ASCO_Abstracts"):
        # Disable ChromaDB telemetry to avoid errors
        import os
        os.environ["ANONYMIZED_TELEMETRY"] = "False"
        
        self.data_dir = Path(data_dir)
        self.embedding_service = BioClinicalEmbeddingService()
        self.vector_store = ChromaVectorStore(persist_directory="./demo_chroma_db")
        self.chunking_factory = ChunkingStrategyFactory()
        
        # Configuration
        self.embedding_config = EmbeddingConfiguration(
            model_name=EmbeddingModel.BIO_BERT_SNLI,
            batch_size=32,
            normalize_embeddings=True
        )
        
        self.chunking_config = ChunkingConfiguration(
            chunk_size=800,
            chunk_overlap=150,
            strategy="hybrid",
            preserve_tables=True,
            include_headers=True
        )
        
        # Demo queries
        self.demo_queries = [
            "pembrolizumab immunotherapy melanoma",
            "BRAF mutation targeted therapy",
            "clinical trial outcomes",
            "melanoma survival rates",
            "immunotherapy resistance",
            "adjuvant treatment",
            "phase 3 study",
            "adverse events toxicity"
        ]
    
    async def load_and_process_data(self, max_abstracts: int = 20) -> List[ChunkWithEmbedding]:
        """Load and process real ASCO data."""
        logger.info(f"🔄 Loading and processing {max_abstracts} abstracts...")
        
        chunks_with_embeddings = []
        abstract_count = 0
        
        # Process each year's data
        for year_file in sorted(self.data_dir.glob("ASCO_*.md")):
            if abstract_count >= max_abstracts:
                break
                
            logger.info(f"📄 Processing {year_file.name}...")
            
            try:
                content = year_file.read_text(encoding='utf-8')
                year = int(year_file.stem.split('_')[1])
                
                chunking_strategy = self.chunking_factory.create_strategy(
                    self.chunking_config.strategy,
                    self.chunking_config
                )
                
                abstract_sections = self._split_into_abstracts(content)
                
                for i, abstract_content in enumerate(abstract_sections[:max_abstracts - abstract_count]):
                    if abstract_count >= max_abstracts:
                        break
                        
                    chunks = await chunking_strategy.chunk_content(
                        content=abstract_content,
                        configuration=self.chunking_config
                    )
                    
                    # Convert to ChunkWithEmbedding
                    for chunk in chunks:
                        chunk_with_embedding = ChunkWithEmbedding(
                            id=chunk.id,
                            document_id=chunk.document_id,
                            content=chunk.content,
                            chunk_type=chunk.chunk_type,
                            metadata={
                                **chunk.metadata,
                                "year": year,
                                "conference": "ASCO",
                                "abstract_index": i
                            },
                            sequence_number=chunk.sequence_number,
                            embedding=None,
                            embedding_model=None,
                            embedding_dimension=None,
                            embedding_generated_at=None
                        )
                        chunks_with_embeddings.append(chunk_with_embedding)
                    
                    abstract_count += 1
                
                logger.info(f"  ✅ Processed {len(abstract_sections)} abstracts from {year_file.name}")
                
            except Exception as e:
                logger.error(f"❌ Error processing {year_file.name}: {e}")
                continue
        
        logger.info(f"✅ Processing complete: {len(chunks_with_embeddings)} chunks from {abstract_count} abstracts")
        return chunks_with_embeddings
    
    def _split_into_abstracts(self, content: str) -> List[str]:
        """Split markdown content into individual abstracts."""
        abstracts = []
        sections = content.split('{')
        
        for section in sections[1:]:
            if section.strip():
                abstract = '{' + section.strip()
                if len(abstract) > 100:
                    abstracts.append(abstract)
        
        return abstracts
    
    async def generate_embeddings(self, chunks: List[ChunkWithEmbedding]) -> List[ChunkWithEmbedding]:
        """Generate embeddings for all chunks."""
        logger.info(f"🔄 Generating embeddings for {len(chunks)} chunks...")
        
        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_service.generate_embeddings_batch(
            texts, self.embedding_config
        )
        
        embedding_dim = await self.embedding_service.get_embedding_dimension(self.embedding_config)
        
        for i, chunk in enumerate(chunks):
            chunk.embedding = embeddings[i]
            chunk.embedding_model = self.embedding_config.model_name.value
            chunk.embedding_dimension = embedding_dim
            chunk.embedding_generated_at = asyncio.get_event_loop().time()
        
        logger.info(f"✅ Embedding generation complete: {embedding_dim} dimensions")
        return chunks
    
    async def store_in_vector_db(self, chunks: List[ChunkWithEmbedding]) -> None:
        """Store chunks in vector database."""
        logger.info(f"🔄 Storing {len(chunks)} chunks in vector database...")
        await self.vector_store.store_chunks(chunks)
        logger.info("✅ Storage complete")
    
    async def demonstrate_search_capabilities(self) -> None:
        """Demonstrate search capabilities with detailed output."""
        logger.info("🔍 Demonstrating search capabilities...")
        
        for query_text in self.demo_queries:
            print(f"\n{'='*80}")
            print(f"🔎 Query: '{query_text}'")
            print(f"{'='*80}")
            
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(
                query_text, self.embedding_config
            )
            
            # Test different thresholds
            for threshold in [0.1, 0.2, 0.3, 0.4, 0.5]:
                search_query = SearchQuery(
                    text=query_text,
                    top_k=5,
                    similarity_threshold=threshold,
                    embedding=query_embedding,
                    metadata_filters={"conference": "ASCO"}
                )
                
                search_results = await self.vector_store.search_similar(search_query)
                
                if search_results:
                    print(f"\n📊 Threshold {threshold}: Found {len(search_results)} results")
                    for i, result in enumerate(search_results[:3]):  # Show top 3
                        chunk = result.chunk
                        print(f"\n  {i+1}. Score: {result.similarity_score:.3f}")
                        print(f"     Type: {chunk.chunk_type.value}")
                        print(f"     Year: {chunk.metadata.get('year', 'N/A')}")
                        print(f"     Content: {chunk.content[:200]}...")
                        if chunk.metadata.get('clinical_trial_id'):
                            print(f"     Trial: {chunk.metadata['clinical_trial_id']}")
                        if chunk.metadata.get('sponsor'):
                            print(f"     Sponsor: {chunk.metadata['sponsor']}")
                    break  # Stop at first threshold that finds results
                else:
                    print(f"  Threshold {threshold}: No results")
    
    async def show_performance_metrics(self, chunks: List[ChunkWithEmbedding], 
                                     processing_time: float) -> None:
        """Show performance metrics."""
        print(f"\n{'='*80}")
        print("📊 Performance Metrics")
        print(f"{'='*80}")
        
        # Calculate metrics
        chunks_per_second = len(chunks) / processing_time
        avg_chunk_size = sum(len(chunk.content) for chunk in chunks) / len(chunks)
        
        print(f"📈 Processing Statistics:")
        print(f"  • Total chunks processed: {len(chunks)}")
        print(f"  • Total processing time: {processing_time:.2f} seconds")
        print(f"  • Processing rate: {chunks_per_second:.2f} chunks/second")
        print(f"  • Average chunk size: {avg_chunk_size:.0f} characters")
        
        # Show embedding info
        if chunks:
            first_chunk = chunks[0]
            print(f"\n🔢 Embedding Information:")
            print(f"  • Embedding model: {first_chunk.embedding_model}")
            print(f"  • Embedding dimension: {first_chunk.embedding_dimension}")
            print(f"  • Normalization: {self.embedding_config.normalize_embeddings}")
        
        # Show vector store info
        store_info = await self.vector_store.get_store_info()
        print(f"\n🗄️ Vector Store Information:")
        print(f"  • Total chunks stored: {store_info['total_chunks']}")
        print(f"  • Collection name: {store_info['collection_name']}")
        print(f"  • Storage directory: {store_info['persist_directory']}")
    
    async def run_demo(self, max_abstracts: int = 20) -> None:
        """Run the complete demo."""
        logger.info("🚀 Starting Embedding and Indexing Demo")
        logger.info("=" * 80)
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Step 1: Load and process data
            chunks = await self.load_and_process_data(max_abstracts)
            
            # Step 2: Generate embeddings
            chunks_with_embeddings = await self.generate_embeddings(chunks)
            
            # Step 3: Store in vector database
            await self.store_in_vector_db(chunks_with_embeddings)
            
            # Step 4: Demonstrate search capabilities
            await self.demonstrate_search_capabilities()
            
            # Step 5: Show performance metrics
            total_time = asyncio.get_event_loop().time() - start_time
            await self.show_performance_metrics(chunks_with_embeddings, total_time)
            
            print(f"\n{'='*80}")
            print("🎉 Demo Complete!")
            print(f"⏱️  Total time: {total_time:.2f}s")
            print(f"📊 Chunks processed: {len(chunks)}")
            print(f"🚀 Processing rate: {len(chunks) / total_time:.2f} chunks/sec")
            print(f"🔍 Search queries tested: {len(self.demo_queries)}")
            print(f"{'='*80}")
            
        except Exception as e:
            logger.error(f"❌ Demo failed: {e}")
            raise
        
        finally:
            # Cleanup
            await self.embedding_service.cleanup_models()
            logger.info("🧹 Cleanup completed")


async def main():
    """Main function to run the demo."""
    demo = EmbeddingIndexingDemo()
    
    try:
        await demo.run_demo(max_abstracts=20)
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
