"""Command-line interface for postprocessing operations."""

import asyncio
import logging
import sys
from pathlib import Path

try:
    import click
except ImportError:
    print("Click is required for the CLI. Install with: poetry add click")
    sys.exit(1)

from app.postprocessing_service import PostprocessingService
from domain.models import ConferenceType, PostprocessingConfiguration

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.group()
def postprocess():
    """Conference abstract postprocessing tools."""
    pass


@postprocess.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option(
    "--conference",
    "-c",
    type=click.Choice(["asco", "esmo"], case_sensitive=False),
    required=True,
    help="Conference type (ASCO or ESMO)",
)
@click.option(
    "--include-authors",
    is_flag=True,
    default=False,
    help="Include author information in output",
)
@click.option(
    "--preserve-tables/--no-preserve-tables",
    default=True,
    help="Preserve table formatting",
)
@click.option(
    "--expand-abbreviations/--no-expand-abbreviations",
    default=True,
    help="Expand medical abbreviations",
)
@click.option(
    "--standardize-terminology/--no-standardize-terminology",
    default=True,
    help="Standardize medical terminology",
)
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable verbose output"
)
def file(
    input_path: str,
    output_path: str,
    conference: str,
    include_authors: bool,
    preserve_tables: bool,
    expand_abbreviations: bool,
    standardize_terminology: bool,
    verbose: bool,
):
    """Process a single conference abstract file.

    INPUT_PATH: Path to the raw markdown file to process
    OUTPUT_PATH: Path where the processed file will be saved
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    async def process_file_async():
        try:
            # Create configuration
            config = PostprocessingConfiguration(
                conference_type=ConferenceType(conference.lower()),
                exclude_authors=not include_authors,
                preserve_tables=preserve_tables,
                expand_abbreviations=expand_abbreviations,
                standardize_terminology=standardize_terminology,
            )

            # Initialize service
            service = PostprocessingService()

            click.echo(f"🚀 Processing {conference.upper()} file: {input_path}")
            click.echo(f"📄 Output will be saved to: {output_path}")

            # Process the file
            result = await service.process_file(input_path, output_path, config)

            if result.success:
                click.echo("\n✅ Processing completed successfully!")
                click.echo("📊 Results:")
                click.echo(f"  - Abstracts processed: {result.abstracts_processed}")
                click.echo(
                    f"  - Abstracts with warnings: {result.abstracts_with_warnings}"
                )
                click.echo(
                    f"  - Structured metadata: {result.structured_metadata_count}"
                )
                click.echo(
                    f"  - Conference features: {result.conference_specific_features}"
                )

                if result.validation_summary:
                    validation = result.validation_summary
                    rag_status = validation.get("rag_optimization", "Unknown")
                    click.echo(
                        f"  - RAG optimization: {'✅ Enhanced' if rag_status == 'Enhanced' else '⚠️ Basic'}"
                    )

                if result.errors:
                    click.echo("\n⚠️ Errors encountered:")
                    for error in result.errors:
                        click.echo(f"  - {error}")
            else:
                click.echo("\n❌ Processing failed!")
                for error in result.errors:
                    click.echo(f"  - {error}")
                sys.exit(1)

        except Exception as e:
            click.echo(f"\n❌ Error: {str(e)}")
            sys.exit(1)

    asyncio.run(process_file_async())


@postprocess.command()
@click.argument(
    "input_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
@click.argument("output_dir", type=click.Path())
@click.option(
    "--conference",
    "-c",
    type=click.Choice(["asco", "esmo"], case_sensitive=False),
    required=True,
    help="Conference type (ASCO or ESMO)",
)
@click.option("--pattern", default="*.md", help="File pattern to match (default: *.md)")
@click.option(
    "--include-authors",
    is_flag=True,
    default=False,
    help="Include author information in output",
)
@click.option(
    "--preserve-tables/--no-preserve-tables",
    default=True,
    help="Preserve table formatting",
)
@click.option(
    "--expand-abbreviations/--no-expand-abbreviations",
    default=True,
    help="Expand medical abbreviations",
)
@click.option(
    "--standardize-terminology/--no-standardize-terminology",
    default=True,
    help="Standardize medical terminology",
)
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable verbose output"
)
def batch(
    input_dir: str,
    output_dir: str,
    conference: str,
    pattern: str,
    include_authors: bool,
    preserve_tables: bool,
    expand_abbreviations: bool,
    standardize_terminology: bool,
    verbose: bool,
):
    """Process multiple conference abstract files in batch.

    INPUT_DIR: Directory containing raw markdown files
    OUTPUT_DIR: Directory where processed files will be saved
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    async def process_batch_async():
        try:
            # Find input files
            input_path = Path(input_dir)
            input_files = list(input_path.glob(pattern))

            if not input_files:
                click.echo(
                    f"❌ No files found matching pattern '{pattern}' in {input_dir}"
                )
                sys.exit(1)

            click.echo(f"📁 Found {len(input_files)} files to process")

            # Create configuration
            config = PostprocessingConfiguration(
                conference_type=ConferenceType(conference.lower()),
                exclude_authors=not include_authors,
                preserve_tables=preserve_tables,
                expand_abbreviations=expand_abbreviations,
                standardize_terminology=standardize_terminology,
            )

            # Initialize service
            service = PostprocessingService()

            # Process files
            input_paths = [str(f) for f in input_files]
            results = await service.process_batch(input_paths, output_dir, config)

            # Summary
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            total_abstracts = sum(r.abstracts_processed for r in results)
            total_warnings = sum(r.abstracts_with_warnings for r in results)

            click.echo("\n📊 Batch Processing Summary:")
            click.echo(f"  - Files processed: {successful}/{len(results)}")
            click.echo(f"  - Total abstracts: {total_abstracts}")
            click.echo(f"  - Total warnings: {total_warnings}")

            if failed > 0:
                click.echo(f"  - Failed files: {failed}")
                for result in results:
                    if not result.success:
                        click.echo(
                            f"    ❌ {result.output_path}: {', '.join(result.errors)}"
                        )

            click.echo("\n✅ Batch processing completed!")

        except Exception as e:
            click.echo(f"\n❌ Error: {str(e)}")
            sys.exit(1)

    asyncio.run(process_batch_async())


@postprocess.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable verbose output"
)
def validate(file_path: str, verbose: bool):
    """Validate a processed conference abstract file.

    FILE_PATH: Path to the processed markdown file to validate
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    async def validate_async():
        try:
            service = PostprocessingService()

            click.echo(f"🔍 Validating file: {file_path}")

            validation_summary = await service.validate_file(file_path)

            if "error" in validation_summary:
                click.echo(f"❌ Validation failed: {validation_summary['error']}")
                sys.exit(1)

            click.echo("\n📊 Validation Results:")
            click.echo(
                f"  - Total abstracts: {validation_summary.get('total_abstracts', 0)}"
            )
            click.echo(
                f"  - Abstracts with warnings: {validation_summary.get('abstracts_with_warnings', 0)}"
            )
            click.echo(
                f"  - Structured metadata: {validation_summary.get('structured_metadata_count', 0)}"
            )

            rag_status = validation_summary.get("rag_optimization", "Unknown")
            click.echo(
                f"  - RAG optimization: {'✅ Enhanced' if rag_status == 'Enhanced' else '⚠️ Basic'}"
            )

            status = validation_summary.get("validation_status", "Unknown")
            if status == "Passed":
                click.echo("  - Status: ✅ Passed")
            else:
                click.echo(f"  - Status: ⚠️ {status}")

            # Conference-specific features
            if "conference_features" in validation_summary:
                features = validation_summary["conference_features"]
                click.echo("\n🎯 Conference Features:")
                for feature, count in features.items():
                    if count > 0:
                        feature_name = feature.replace("_", " ").title()
                        click.echo(f"  - {feature_name}: {count}")

        except Exception as e:
            click.echo(f"❌ Error: {str(e)}")
            sys.exit(1)

    asyncio.run(validate_async())


@postprocess.command()
def info():
    """Show information about supported conference types and features."""
    click.echo("🏥 Conference Abstract Postprocessing System")
    click.echo("\n📋 Supported Conference Types:")

    click.echo("\n  🔬 ASCO (American Society of Clinical Oncology)")
    click.echo("    - Abstract ID formats: 10000, 9501, TPS9585, LBA9503")
    click.echo("    - Sections: Background, Methods, Results, Conclusions")
    click.echo("    - Metadata: Clinical Trial Information, Research Sponsor")
    click.echo("    - Features: Full Text References, TPS abstracts")

    click.echo("\n  🌍 ESMO (European Society for Medical Oncology)")
    click.echo("    - Abstract ID formats: 1076O, 784MO, 1153TiP")
    click.echo(
        "    - Sections: Background, Trial Design, Methods, Results, Conclusions"
    )
    click.echo("    - Metadata: Clinical Trial ID, Legal Entity, Funding, DOI")
    click.echo("    - Features: Trial Design sections, DOI links")

    click.echo("\n🎯 RAG Optimization Features:")
    click.echo("  - Structured section headers (#### Section:)")
    click.echo("  - Separated metadata chunks")
    click.echo("  - Enhanced table formatting")
    click.echo("  - Standardized terminology")
    click.echo("  - Clean content boundaries")

    click.echo("\n📖 Usage Examples:")
    click.echo("  # Process single ASCO file")
    click.echo("  postprocess file raw_asco.md processed_asco.md --conference asco")
    click.echo("")
    click.echo("  # Process ESMO directory in batch")
    click.echo("  postprocess batch ./raw_esmo/ ./processed_esmo/ --conference esmo")
    click.echo("")
    click.echo("  # Validate processed file")
    click.echo("  postprocess validate processed_file.md")


if __name__ == "__main__":
    postprocess()
