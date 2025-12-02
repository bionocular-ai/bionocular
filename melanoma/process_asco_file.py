"""Process a single ASCO file with the updated postprocessor."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from domain.models import ConferenceType, PostprocessingConfiguration
from infrastructure.asco_postprocessor import ASCOPostprocessor


async def process_asco_file(input_path: Path, output_path: Path):
    """Process a single ASCO markdown file."""

    print(f"Processing: {input_path}")
    print(f"Output to: {output_path}")

    # Read input file
    with open(input_path, encoding="utf-8") as f:
        content = f.read()

    # Initialize postprocessor
    postprocessor = ASCOPostprocessor()
    config = PostprocessingConfiguration(
        conference_type=ConferenceType.ASCO, exclude_authors=True
    )

    # Split into individual abstracts
    # DocStrange format uses page breaks and abstract IDs
    import re

    # Split by abstract ID patterns (with or without bold markers)
    # Patterns:
    # - **10000** or 10000 (regular abstracts)
    # - # 10000 or ## 10000 (markdown header format)
    # - **TPS10079** or TPS10079 (trials in progress)
    # - **LBA9500** or LBA9500 (late breaking)
    # - **9500** or 9500 (ASCO 2021+)

    # Use lookahead to split while keeping the ID with its content
    # Match at the start of line or after MELANOMA/SKIN CANCERS
    abstract_pattern = r"(?=(?:^|\n)(?:##\s+Page\s+\d+\s*\n)?(?:MELANOMA/SKIN CANCERS\s*\n)?(?:\*{0,2}|#{1,2}\s*)(?:TPS|LBA)?(?:100\d{2}|9[56]\d{2})(?:\*{0,2}|(?:\s|$)))"

    parts = re.split(abstract_pattern, content, flags=re.MULTILINE)

    # Filter out empty parts and the header (first part is usually file header)
    abstract_texts = [
        part.strip() for part in parts if part.strip() and len(part.strip()) > 100
    ]

    print(f"Found {len(abstract_texts)} abstracts to process")

    # Process each abstract
    processed_abstracts = []
    failed_count = 0

    for i, abstract_text in enumerate(abstract_texts, 1):
        try:
            # Parse the abstract
            parsed = await postprocessor.parse_abstract(abstract_text)

            # Validate
            issues = await postprocessor.validate_abstract(parsed)
            if issues:
                print(f"  Warning: Abstract {parsed.id} has issues: {issues}")

            # Format to markdown
            formatted = await postprocessor.format_to_markdown(parsed, config)

            processed_abstracts.append(formatted)

            if i % 10 == 0:
                print(f"  Processed {i}/{len(abstract_texts)} abstracts...")

        except Exception as e:
            print(f"  Error processing abstract {i}: {e}")
            failed_count += 1
            continue

    print(f"\nSuccessfully processed: {len(processed_abstracts)}/{len(abstract_texts)}")
    if failed_count > 0:
        print(f"Failed: {failed_count}")

    # Combine all abstracts with separators
    output_content = "\n\n---\n\n".join(processed_abstracts)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"\n✓ Output saved to: {output_path}")
    print(f"  File size: {len(output_content):,} characters")
    print(f"  Abstracts: {len(processed_abstracts)}")


async def main():
    """Main entry point."""
    input_file = Path("data/processed/ASCO_Abstracts/ASCO_2025.md")
    output_file = Path("data/postprocessed/ASCO_Abstracts/ASCO_2025.md")

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return 1

    await process_asco_file(input_file, output_file)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
