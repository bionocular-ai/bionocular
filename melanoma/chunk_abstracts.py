#!/usr/bin/env python3
"""
Chunk Oncology Abstract Data Script

This script chunks real oncology abstract markdown files (ASCO, ESMO, etc.) using the core chunking system.
It demonstrates the chunking capabilities with actual oncology data following clean architecture.

Usage:
    python chunk_abstracts.py [--file ASCO_2020.md] [--strategy hybrid] [--max-abstracts 10]
    python chunk_abstracts.py [--file ESMO_2020.md] [--strategy header_based]
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional
from uuid import uuid4

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))  # noqa: E402

from domain.models import ChunkingConfiguration, ChunkingStrategy  # noqa: E402
from infrastructure.chunking_strategies import ChunkingStrategyFactory  # noqa: E402


class AbstractProcessor:
    """Processes oncology abstract files (ASCO, ESMO, etc.) using the chunking system."""

    def __init__(self, data_dir: Path = None):
        """Initialize the processor with data directory."""
        self.data_dir = data_dir or Path("data/processed")

    async def process_file(
        self,
        filename: str,
        strategy_name: str = "hybrid",
        max_abstracts: Optional[int] = None,
        chunk_size: int = 800,
        overlap: int = 150,
        verbose: bool = False
    ) -> dict:
        """Process a single ASCO data file."""

        file_path = self.data_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        print(f"📄 Processing: {file_path}")

        # Read the file
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        print(f"📊 File size: {len(content):,} characters")

        # Split into individual abstracts
        abstracts = content.split('### Abstract ID: ')
        abstracts = ['### Abstract ID: ' + abstract for abstract in abstracts[1:]]  # Skip first empty

        total_abstracts = len(abstracts)
        process_count = min(max_abstracts or total_abstracts, total_abstracts)

        print(f"📋 Found {total_abstracts} abstracts, processing {process_count}")

        # Setup chunking strategy
        strategy_enum = getattr(ChunkingStrategy, strategy_name.upper())
        strategy = ChunkingStrategyFactory.create_strategy(strategy_enum)

        config = ChunkingConfiguration(
            strategy=strategy_enum,
            max_chunk_size=chunk_size,
            chunk_overlap=overlap,
            preserve_tables=True,
            include_headers=True
        )

        # Process abstracts
        results = {
            'file': filename,
            'total_abstracts': total_abstracts,
            'processed_abstracts': process_count,
            'strategy': strategy_name,
            'config': {
                'chunk_size': chunk_size,
                'overlap': overlap
            },
            'abstracts': [],
            'summary': {
                'total_chunks': 0,
                'chunk_types': {},
                'sponsors': set(),
                'clinical_trials': set(),
                'years': set()
            }
        }

        for i, abstract in enumerate(abstracts[:process_count]):
            try:
                chunks = await strategy.chunk_content(
                    content=abstract,
                    configuration=config,
                    document_id=str(uuid4()),
                    filename=filename
                )

                # Extract metadata from first chunk
                metadata = chunks[0].metadata if chunks else {}
                chunk_types = [chunk.chunk_type.value for chunk in chunks]

                abstract_result = {
                    'index': i + 1,
                    'chunks': len(chunks),
                    'chunk_types': chunk_types,
                    'metadata': {
                        'abstract_id': metadata.get('abstract_id'),
                        'year': metadata.get('year'),
                        'clinical_trial_id': metadata.get('clinical_trial_id'),
                        'sponsor': metadata.get('sponsor'),
                        'title': metadata.get('title', '')[:100] + '...' if metadata.get('title') else None,
                        'has_table': metadata.get('has_table', False)
                    }
                }

                # Add full chunk details if verbose mode
                if verbose:
                    abstract_result['chunk_details'] = []
                    for idx, chunk in enumerate(chunks):
                        chunk_detail = {
                            'sequence': idx + 1,
                            'id': str(chunk.id),
                            'type': chunk.chunk_type.value,
                            'content': chunk.content,
                            'token_count': chunk.token_count,
                            'metadata': chunk.metadata,
                            'created_at': chunk.created_at.isoformat()
                        }
                        abstract_result['chunk_details'].append(chunk_detail)

                results['abstracts'].append(abstract_result)
                results['summary']['total_chunks'] += len(chunks)

                # Update summary statistics
                for chunk_type in chunk_types:
                    results['summary']['chunk_types'][chunk_type] = \
                        results['summary']['chunk_types'].get(chunk_type, 0) + 1

                if metadata.get('sponsor'):
                    results['summary']['sponsors'].add(metadata['sponsor'])
                if metadata.get('clinical_trial_id'):
                    results['summary']['clinical_trials'].add(metadata['clinical_trial_id'])
                if metadata.get('year'):
                    results['summary']['years'].add(metadata['year'])

                print(f"  ✅ Abstract {i+1}: {len(chunks)} chunks, {chunk_types}")

                # Print chunk details if verbose
                if verbose:
                    print(f"\n    📋 Detailed Chunks for Abstract {i+1}:")
                    for idx, chunk in enumerate(chunks):
                        print(f"    Chunk {idx+1} ({chunk.chunk_type.value}):")
                        print(f"      ID: {chunk.id}")
                        print(f"      Tokens: {chunk.token_count}")
                        print(f"      Content Preview: {chunk.content[:100]}{'...' if len(chunk.content) > 100 else ''}")
                        print(f"      Full Content:\n        {chunk.content[:300]}{'...' if len(chunk.content) > 300 else ''}")
                        print(f"      Metadata: {chunk.metadata}")
                        print()

            except Exception as e:
                print(f"  ❌ Error processing abstract {i+1}: {str(e)}")
                continue

        # Convert sets to lists for JSON serialization
        results['summary']['sponsors'] = list(results['summary']['sponsors'])
        results['summary']['clinical_trials'] = list(results['summary']['clinical_trials'])
        results['summary']['years'] = list(results['summary']['years'])

        return results

    def print_summary(self, results: dict):
        """Print a formatted summary of processing results."""
        print(f"\n{'='*60}")
        print("📊 PROCESSING SUMMARY")
        print(f"{'='*60}")

        print(f"📄 File: {results['file']}")
        print(f"🔧 Strategy: {results['strategy']}")
        print(f"📋 Abstracts: {results['processed_abstracts']}/{results['total_abstracts']}")
        print(f"📦 Total chunks: {results['summary']['total_chunks']}")
        print(f"📈 Avg chunks/abstract: {results['summary']['total_chunks']/results['processed_abstracts']:.1f}")

        print("\n🎯 Chunk Type Distribution:")
        for chunk_type, count in results['summary']['chunk_types'].items():
            percentage = (count / results['summary']['total_chunks']) * 100
            print(f"  {chunk_type}: {count} ({percentage:.1f}%)")

        print(f"\n🏢 Sponsors ({len(results['summary']['sponsors'])}):")
        for sponsor in sorted(results['summary']['sponsors'])[:5]:  # Show top 5
            print(f"  • {sponsor}")
        if len(results['summary']['sponsors']) > 5:
            print(f"  ... and {len(results['summary']['sponsors']) - 5} more")

        print(f"\n🧪 Clinical Trials: {len(results['summary']['clinical_trials'])}")
        print(f"📅 Years: {sorted(results['summary']['years'])}")

        print("\n💡 Sample Abstract Metadata:")
        if results['abstracts']:
            sample = results['abstracts'][0]
            print(f"  Abstract ID: {sample['metadata']['abstract_id']}")
            print(f"  Title: {sample['metadata']['title']}")
            print(f"  Sponsor: {sample['metadata']['sponsor']}")
            print(f"  Clinical Trial: {sample['metadata']['clinical_trial_id']}")
            print(f"  Has Table: {sample['metadata']['has_table']}")
            print(f"  Chunks: {sample['chunks']} ({', '.join(sample['chunk_types'])})")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Chunk oncology abstract data (ASCO, ESMO) with intelligent text splitting')
    parser.add_argument('--file', default='ASCO_2020.md',
                       help='Oncology data file to process (default: ASCO_2020.md, supports ASCO_*.md, ESMO_*.md)')
    parser.add_argument('--strategy', choices=['header_based', 'recursive', 'hybrid'],
                       default='hybrid', help='Chunking strategy (default: hybrid)')
    parser.add_argument('--max-abstracts', type=int,
                       help='Maximum number of abstracts to process (default: all)')
    parser.add_argument('--chunk-size', type=int, default=800,
                       help='Maximum chunk size in characters (default: 800)')
    parser.add_argument('--overlap', type=int, default=150,
                       help='Chunk overlap in characters (default: 150)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed chunk contents and metadata')

    args = parser.parse_args()

    try:
        processor = AbstractProcessor()

        print("🧬 Oncology Abstract Processing System")
        print("Processing real oncology data (ASCO, ESMO, etc.) with clean architecture chunking\n")

        results = await processor.process_file(
            filename=args.file,
            strategy_name=args.strategy,
            max_abstracts=args.max_abstracts,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            verbose=args.verbose
        )

        processor.print_summary(results)

        print("\n✅ Processing completed successfully!")
        print(f"Ready for RAG implementation with {results['summary']['total_chunks']} chunks")

    except KeyboardInterrupt:
        print("\n⏹️  Processing interrupted by user")
    except Exception as e:
        print(f"\n❌ Processing failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
