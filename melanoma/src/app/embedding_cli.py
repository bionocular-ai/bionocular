"""CLI commands for embedding generation and vector store operations."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import click

from ..domain.constants import EmbeddingDefaults, VectorStoreDefaults
from ..domain.models import EmbeddingConfiguration, EmbeddingModel
from ..infrastructure.embedding_service import BioClinicalEmbeddingService
from ..infrastructure.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


@click.group()
def embedding():
    """Embedding and vector store management commands."""
    pass


@embedding.command()
@click.option(
    "--model",
    "-m",
    type=click.Choice([model.value for model in EmbeddingModel]),
    default=EmbeddingDefaults.DEFAULT_MODEL.value,
    help="Embedding model to use",
)
@click.option(
    "--batch-size",
    "-b",
    type=int,
    default=EmbeddingDefaults.DEFAULT_BATCH_SIZE,
    help="Batch size for embedding generation",
)
@click.option(
    "--normalize/--no-normalize",
    default=EmbeddingDefaults.DEFAULT_NORMALIZE_EMBEDDINGS,
    help="Whether to normalize embeddings",
)
@click.option(
    "--max-length",
    "-l",
    type=int,
    default=EmbeddingDefaults.DEFAULT_MAX_SEQUENCE_LENGTH,
    help="Maximum sequence length",
)
def validate_model(model: str, batch_size: int, normalize: bool, max_length: int):
    """Validate that an embedding model is available and working."""

    async def validate_async():
        try:
            config = EmbeddingConfiguration(
                model_name=EmbeddingModel(model),
                batch_size=batch_size,
                normalize_embeddings=normalize,
                max_sequence_length=max_length,
            )

            service = BioClinicalEmbeddingService()

            click.echo(f"🔍 Validating model: {model}")
            is_valid = await service.validate_model(model)

            if is_valid:
                click.echo("✅ Model validation successful!")

                # Get embedding dimension
                dimension = await service.get_embedding_dimension(config)
                click.echo(f"📏 Embedding dimension: {dimension}")

            else:
                click.echo("❌ Model validation failed!")
                click.echo("Please check that the model is available and accessible.")

        except Exception as e:
            click.echo(f"❌ Validation error: {str(e)}")
            logger.error(f"Model validation failed: {e}")

    asyncio.run(validate_async())


@embedding.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--output-file",
    "-o",
    type=click.Path(),
    help="Output file for embeddings (default: input_file.embeddings.json)",
)
@click.option(
    "--model",
    "-m",
    type=click.Choice([model.value for model in EmbeddingModel]),
    default=EmbeddingDefaults.DEFAULT_MODEL.value,
    help="Embedding model to use",
)
@click.option(
    "--batch-size",
    "-b",
    type=int,
    default=EmbeddingDefaults.DEFAULT_BATCH_SIZE,
    help="Batch size for embedding generation",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def generate_embeddings(
    input_file: str,
    output_file: Optional[str],
    model: str,
    batch_size: int,
    verbose: bool,
):
    """Generate embeddings for text content in a file."""

    async def generate_async():
        try:
            if verbose:
                logging.getLogger().setLevel(logging.DEBUG)

            # Set up output file
            input_path = Path(input_file)
            if output_file is None:
                final_output_file = str(input_path.with_suffix(".embeddings.json"))
            else:
                final_output_file = output_file

            # Create configuration
            config = EmbeddingConfiguration(
                model_name=EmbeddingModel(model), batch_size=batch_size
            )

            # Initialize services
            embedding_service = BioClinicalEmbeddingService()

            click.echo(f"📄 Processing file: {input_file}")
            click.echo(f"🤖 Using model: {model}")
            click.echo(f"📦 Batch size: {batch_size}")

            # Read input file
            with open(input_file, encoding="utf-8") as f:
                content = f.read()

            # Split into lines or paragraphs
            texts = [line.strip() for line in content.split("\n") if line.strip()]

            if not texts:
                click.echo("❌ No text content found in file")
                return

            click.echo(f"📊 Found {len(texts)} text segments")

            # Generate embeddings
            click.echo("🔄 Generating embeddings...")
            embeddings = await embedding_service.generate_embeddings_batch(
                texts, config
            )

            # Save results
            import json

            results = {
                "model": model,
                "batch_size": batch_size,
                "total_texts": len(texts),
                "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                "texts": texts,
                "embeddings": embeddings,
            }

            with open(final_output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

            click.echo(f"✅ Embeddings saved to: {final_output_file}")
            click.echo(
                f"📏 Embedding dimension: {len(embeddings[0]) if embeddings else 0}"
            )

        except Exception as e:
            click.echo(f"❌ Error generating embeddings: {str(e)}")
            logger.error(f"Embedding generation failed: {e}")

    asyncio.run(generate_async())


@embedding.command()
@click.option(
    "--persist-dir",
    "-d",
    type=click.Path(),
    default=VectorStoreDefaults.DEFAULT_PERSIST_DIRECTORY,
    help="ChromaDB persist directory",
)
def vector_store_info(persist_dir: str):
    """Get information about the vector store."""

    async def info_async():
        try:
            vector_store = ChromaVectorStore(persist_directory=persist_dir)
            info = await vector_store.get_store_info()

            click.echo("📊 Vector Store Information:")
            click.echo(f"  Collection: {info['collection_name']}")
            click.echo(f"  Total chunks: {info['total_chunks']}")
            click.echo(f"  Persist directory: {info['persist_directory']}")

            if info.get("collection_metadata"):
                click.echo(
                    f"  Description: {info['collection_metadata'].get('description', 'N/A')}"
                )

        except Exception as e:
            click.echo(f"❌ Error getting store info: {str(e)}")
            logger.error(f"Store info retrieval failed: {e}")

    asyncio.run(info_async())


@embedding.command()
@click.option(
    "--persist-dir",
    "-d",
    type=click.Path(),
    default=VectorStoreDefaults.DEFAULT_PERSIST_DIRECTORY,
    help="ChromaDB persist directory",
)
@click.confirmation_option(prompt="Are you sure you want to clear the vector store?")
def clear_vector_store(persist_dir: str):
    """Clear all data from the vector store."""

    async def clear_async():
        try:
            vector_store = ChromaVectorStore(persist_directory=persist_dir)
            await vector_store.clear_store()
            click.echo("✅ Vector store cleared successfully!")

        except Exception as e:
            click.echo(f"❌ Error clearing store: {str(e)}")
            logger.error(f"Store clear failed: {e}")

    asyncio.run(clear_async())


if __name__ == "__main__":
    embedding()
