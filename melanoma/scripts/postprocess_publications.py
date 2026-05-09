#!/usr/bin/env python3
"""CLI script for postprocessing publication markdown files.

Usage:
    poetry run python postprocess_publications.py <input_file> [output_file]
    poetry run python postprocess_publications.py --batch <input_dir> [output_dir]

Examples:
    # Process a single file
    poetry run python postprocess_publications.py data/processed/Publications/Batch-I_3.md

    # Process all files in a directory
    poetry run python postprocess_publications.py --batch data/processed/Publications/
"""

import argparse
import sys
from pathlib import Path

from src.app.publication_postprocessing_service import PublicationPostprocessingService


def main():
    """Main entry point for publication postprocessing CLI."""
    parser = argparse.ArgumentParser(
        description="Postprocess publication markdown files for RAG/LLM extraction"
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input markdown file or directory (for batch mode)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Output file or directory (optional, defaults to input with '_cleaned' suffix)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all .md files in input directory",
    )
    parser.add_argument(
        "--pattern",
        default="*.md",
        help="File pattern for batch processing (default: *.md)",
    )

    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        sys.exit(1)

    service = PublicationPostprocessingService()

    if args.batch:
        # Batch processing
        input_dir = Path(args.input)
        if not input_dir.is_dir():
            print(f"❌ Error: {input_dir} is not a directory")
            sys.exit(1)

        output_dir = Path(args.output) if args.output else None

        # Find all matching files
        input_files = list(input_dir.glob(args.pattern))
        if not input_files:
            print(f"❌ No files matching pattern '{args.pattern}' found in {input_dir}")
            sys.exit(1)

        print(f"📁 Processing {len(input_files)} files from {input_dir}...")
        results = service.process_batch(
            [str(f) for f in input_files], str(output_dir) if output_dir else None
        )

        # Print summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_lines_removed = sum(r.lines_removed for r in results)
        total_tables = sum(r.tables_repaired for r in results)

        print(f"\n{'='*60}")
        print("📊 Batch Processing Summary")
        print(f"{'='*60}")
        print(f"✓ Successful: {successful}/{len(results)}")
        if failed > 0:
            print(f"✗ Failed: {failed}/{len(results)}")
        print(f"📉 Total lines removed: {total_lines_removed:,}")
        print(f"📊 Total tables found: {total_tables}")

        if failed > 0:
            print("\n❌ Failed files:")
            for r in results:
                if not r.success:
                    print(f"  - {Path(r.input_path).name}: {', '.join(r.errors)}")

    else:
        # Single file processing
        input_file = Path(args.input)
        if not input_file.exists():
            print(f"❌ Error: File not found: {input_file}")
            sys.exit(1)

        output_file = args.output

        print(f"📄 Processing: {input_file}")
        result = service.process_file(str(input_file), output_file)

        if result.success:
            print("✓ Success!")
            print(f"  Output: {result.output_path}")
            print(f"  Lines removed: {result.lines_removed:,}")
            print(f"  Tables found: {result.tables_repaired}")
        else:
            print("❌ Error processing file:")
            for error in result.errors:
                print(f"  - {error}")
            sys.exit(1)


if __name__ == "__main__":
    main()
