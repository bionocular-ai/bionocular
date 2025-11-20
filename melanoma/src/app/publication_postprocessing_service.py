"""Publication postprocessing service for orchestrating publication markdown processing."""

import logging
from pathlib import Path
from typing import Optional

from infrastructure.publication_postprocessor import PublicationPostprocessor

logger = logging.getLogger(__name__)


class PublicationPostprocessingResult:
    """Result of publication postprocessing operation."""

    def __init__(
        self,
        success: bool,
        input_path: str,
        output_path: str,
        lines_removed: int = 0,
        tables_repaired: int = 0,
        errors: Optional[list[str]] = None,
    ):
        """Initialize postprocessing result.

        Args:
            success: Whether postprocessing succeeded
            input_path: Path to input file
            output_path: Path to output file
            lines_removed: Number of lines removed during cleaning
            tables_repaired: Number of tables repaired
            errors: List of error messages
        """
        self.success = success
        self.input_path = input_path
        self.output_path = output_path
        self.lines_removed = lines_removed
        self.tables_repaired = tables_repaired
        self.errors = errors or []

    def __repr__(self) -> str:
        """String representation of result."""
        status = "✓" if self.success else "✗"
        return (
            f"{status} PublicationPostprocessingResult("
            f"input={Path(self.input_path).name}, "
            f"output={Path(self.output_path).name}, "
            f"lines_removed={self.lines_removed}, "
            f"tables_repaired={self.tables_repaired})"
        )


class PublicationPostprocessingService:
    """Service for orchestrating publication markdown postprocessing."""

    def __init__(self):
        """Initialize the publication postprocessing service."""
        self.processor = PublicationPostprocessor()

    def process_file(
        self, input_path: str, output_path: Optional[str] = None
    ) -> PublicationPostprocessingResult:
        """Process a single publication markdown file.

        Args:
            input_path: Path to input markdown file
            output_path: Optional path to output file. If None, creates output
                        in same directory with '_cleaned' suffix

        Returns:
            PublicationPostprocessingResult with processing details
        """
        try:
            input_file = Path(input_path)
            if not input_file.exists():
                return PublicationPostprocessingResult(
                    success=False,
                    input_path=input_path,
                    output_path=output_path or "",
                    errors=[f"Input file not found: {input_path}"],
                )

            # Determine output path
            if output_path is None:
                output_file = input_file.parent / f"{input_file.stem}_cleaned{input_file.suffix}"
            else:
                output_file = Path(output_path)

            # Read input file
            logger.info(f"Processing publication file: {input_path}")
            with open(input_file, encoding="utf-8") as f:
                content = f.read()

            original_line_count = len(content.split("\n"))

            # Process content
            cleaned_content = self.processor.process(content)

            cleaned_line_count = len(cleaned_content.split("\n"))
            lines_removed = original_line_count - cleaned_line_count

            # Count tables (rough estimate: count markdown table separators)
            tables_repaired = cleaned_content.count("|---|")

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write output file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(cleaned_content)

            logger.info(
                f"✓ Processed {input_path} -> {output_file} "
                f"(removed {lines_removed} lines, found {tables_repaired} tables)"
            )

            return PublicationPostprocessingResult(
                success=True,
                input_path=str(input_file),
                output_path=str(output_file),
                lines_removed=lines_removed,
                tables_repaired=tables_repaired,
            )

        except Exception as e:
            logger.error(f"Error processing file {input_path}: {e}", exc_info=True)
            return PublicationPostprocessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path or "",
                errors=[str(e)],
            )

    def process_batch(
        self, input_paths: list[str], output_dir: Optional[str] = None
    ) -> list[PublicationPostprocessingResult]:
        """Process multiple publication markdown files.

        Args:
            input_paths: List of paths to input markdown files
            output_dir: Optional output directory. If None, outputs are created
                       in same directory as inputs with '_cleaned' suffix

        Returns:
            List of PublicationPostprocessingResult objects
        """
        results = []

        if output_dir:
            output_path_obj = Path(output_dir)
            output_path_obj.mkdir(parents=True, exist_ok=True)

        for input_path in input_paths:
            if output_dir:
                input_file = Path(input_path)
                output_path = str(output_path_obj / input_file.name)
            else:
                output_path = None

            result = self.process_file(input_path, output_path)
            results.append(result)

        return results

