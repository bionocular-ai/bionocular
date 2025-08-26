#!/usr/bin/env python3
"""Simple CLI to process a PDF with Marker and save outputs.

Usage:
  poetry run python run_marker.py <input_pdf> <output_dir>
"""

import sys
import json
import asyncio
from pathlib import Path

# Ensure src is on path when running from project root
SRC_PATH = Path(__file__).parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.infrastructure.marker_processor import MarkerPDFProcessor  # noqa: E402


async def process_pdf(input_pdf: Path, output_dir: Path) -> None:
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    output_dir.mkdir(parents=True, exist_ok=True)

    processor = MarkerPDFProcessor(use_llm=False, extract_images=True)
    file_bytes = input_pdf.read_bytes()

    # Extract text and metadata
    text = await processor.extract_text(file_bytes)
    metadata = await processor.extract_metadata(file_bytes)

    stem = input_pdf.stem
    (output_dir / f"{stem}.md").write_text(text, encoding="utf-8")
    (output_dir / f"{stem}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved: {output_dir / f'{stem}.md'}")
    print(f"Saved: {output_dir / f'{stem}.json'}")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: poetry run python run_marker.py <input_pdf> <output_dir>")
        sys.exit(1)

    input_pdf = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    asyncio.run(process_pdf(input_pdf, output_dir))


if __name__ == "__main__":
    main()
