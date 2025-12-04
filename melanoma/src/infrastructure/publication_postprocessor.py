"""Publication postprocessor implementation.

Handles postprocessing of full research publication markdown files converted from PDFs.
Focuses on cleaning artifacts, repairing tables, and optimizing content for RAG/LLM extraction.
"""

import csv
import io
import logging
import re
from typing import Optional

from domain.constants import PublicationPostprocessingPatterns

logger = logging.getLogger(__name__)


class PublicationPostprocessor:
    """Postprocessor for research publication markdown files."""

    def __init__(self):
        """Initialize the publication postprocessor."""
        self.patterns = PublicationPostprocessingPatterns()

    def process(self, content: str) -> str:
        """Process publication markdown content through all cleaning steps.

        Args:
            content: Raw markdown content from PDF conversion

        Returns:
            Cleaned markdown content optimized for RAG/LLM extraction
        """
        if not content:
            return content

        # Step 1: Global de-noising (headers, footers, copyright, page numbers)
        content = self._remove_headers_footers(content)

        # Step 2: Fix section headers with spacing issues
        content = self._fix_section_headers(content)

        # Step 3: Remove graph artifacts (number sequences, "No. at Risk" tables)
        content = self._remove_graph_artifacts(content)

        # Step 4: Repair CSV-dump tables (Batch-I_7 style)
        content = self._repair_csv_dump_tables(content)

        # Step 5: Repair split header tables (NEJM/Lancet style)
        content = self._repair_split_header_tables(content)

        # Step 6: Merge multi-page tables
        content = self._merge_multipage_tables(content)

        # Step 7: Remove image references
        content = self._remove_image_references(content)

        # Step 8: Remove References section
        content = self._remove_references_section(content)

        # Step 9: Remove Appendix section
        content = self._remove_appendix_section(content)

        # Step 10: Normalize citations
        content = self._normalize_citations(content)

        # Step 11: Final cleanup (whitespace normalization)
        content = self._final_cleanup(content)

        return content

    def _remove_headers_footers(self, content: str) -> str:
        """Remove headers, footers, copyright notices, and page numbers.

        Args:
            content: Markdown content

        Returns:
            Content with headers/footers removed
        """
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines (we'll normalize later)
            if not line_stripped:
                cleaned_lines.append("")
                continue

            # Check against all header/footer patterns
            patterns_to_remove = [
                self.patterns.DOWNLOADED_FROM,
                self.patterns.COPYRIGHT,
                self.patterns.PROTECTED_BY_COPYRIGHT,
                self.patterns.TECHNOLOGY_RELATED,
                self.patterns.NEJM_HEADER,
                self.patterns.LANCET_HEADER,
                self.patterns.JCO_HEADER,
                self.patterns.JITC_HEADER,
                self.patterns.PAGE_NUMBER,
                # Document type headers
                self.patterns.ORIGINAL_ARTICLE,
                self.patterns.ORIGINAL_REPORT,
                self.patterns.ORIGINAL_RESEARCH,
                self.patterns.RESEARCH_ARTICLE,
                self.patterns.RESEARCH_REPORT,
                self.patterns.SHORT_REPORT,
                self.patterns.BRIEF_REPORT,
                self.patterns.JOURNAL_CLINICAL_ONCOLOGY,
                self.patterns.SCIENCEDIRECT,
                self.patterns.CROSSMARK,
                self.patterns.JAMA_ONCOLOGY,
                self.patterns.AVAILABLE_ONLINE,
                self.patterns.JOURNAL_HOMEPAGE,
                self.patterns.OPEN_ACCESS,
                self.patterns.ESTABLISHED_IN,
                self.patterns.ORIGINAL_ARTICLE_WITH_JOURNAL,
            ]

            should_remove = False
            for pattern in patterns_to_remove:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    should_remove = True
                    break

            if not should_remove:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _fix_section_headers(self, content: str) -> str:
        """Fix section headers with spacing issues (e.g., "R esult s" -> "Results").

        Args:
            content: Markdown content

        Returns:
            Content with fixed section headers
        """
        lines = content.split("\n")
        fixed_lines = []

        # Common section names to fix
        section_fixes = {
            r"R\s+esult\s+s": "Results",
            r"A\s+bstract": "Abstract",
            r"B\s+ackground": "Background",
            r"M\s+ethods": "Methods",
            r"C\s+onclusions": "Conclusions",
            r"D\s+iscussion": "Discussion",
            r"I\s+ntroduction": "Introduction",
            r"S\s+ummary": "Summary",
            r"O\s+bjectives": "Objectives",
            r"P\s+atients": "Patients",
            r"T\s+reatment": "Treatment",
            r"E\s+fficacy": "Efficacy",
            r"S\s+afety": "Safety",
            r"A\s+ssessments": "Assessments",
            r"S\s+tatistical\s+A\s+nalysis": "Statistical Analysis",
        }

        for line in lines:
            line_stripped = line.strip()

            # Check if this is a header line (starts with #)
            if line_stripped.startswith("#"):
                # Try to fix common section name issues
                fixed_line = line
                for pattern, replacement in section_fixes.items():
                    # Match section name after the # symbols and optional spaces/formatting
                    # Pattern: #+ *optional formatting* section_name *optional formatting*
                    header_pattern = (
                        r"^(#{1,6}\s*\*?\*?)"  # Capture # symbols and optional bold markers
                        + pattern
                        + r"(\*?\*?\s*)$"  # Optional bold markers and end
                    )
                    fixed_line = re.sub(
                        header_pattern,
                        r"\1" + replacement + r"\2",
                        fixed_line,
                        flags=re.IGNORECASE,
                    )
                    if fixed_line != line:
                        break  # Stop after first match

                fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def _remove_graph_artifacts(self, content: str) -> str:
        """Remove graph artifacts: number sequences and 'No. at Risk' tables.

        Args:
            content: Markdown content

        Returns:
            Content with graph artifacts removed
        """
        lines = content.split("\n")
        cleaned_lines = []
        in_number_at_risk_table = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Check if we're starting a "No. at Risk" table
            if re.match(
                self.patterns.NUMBER_AT_RISK_START, line_stripped, re.IGNORECASE
            ):
                in_number_at_risk_table = True
                continue  # Skip the header line

            # If we're in a "No. at Risk" table, skip number sequence lines
            if in_number_at_risk_table:
                # Check if this is a number sequence line
                if re.match(self.patterns.NUMBER_AT_RISK_LINE, line_stripped):
                    continue  # Skip this line
                # If we hit a non-number line, we've left the table
                if line_stripped and not re.match(
                    self.patterns.NUMBER_AT_RISK_LINE, line_stripped
                ):
                    in_number_at_risk_table = False
                    # Don't skip this line, it's the content after the table

            # Remove standalone number sequences (graph axis labels)
            # But be careful not to remove table rows that happen to be numbers
            # Only remove if it's clearly a standalone sequence (not in a table)
            if re.match(self.patterns.NUMBER_SEQUENCE, line_stripped):
                # Check if this is part of a markdown table
                is_in_table = False
                # Look ahead and behind to see if we're in a table context
                for j in range(max(0, i - 2), min(len(lines), i + 3)):
                    if "|" in lines[j]:
                        is_in_table = True
                        break

                if not is_in_table:
                    continue  # Skip standalone number sequences

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _repair_csv_dump_tables(self, content: str) -> str:
        """Repair CSV-dump tables (Batch-I_7 style) by converting to Markdown tables.

        Args:
            content: Markdown content

        Returns:
            Content with CSV-dump tables converted to Markdown
        """
        lines = content.split("\n")
        repaired_lines: list[str] = []
        csv_block: list[str] = []
        in_csv_block = False

        for _i, line in enumerate(lines):
            line_stripped = line.strip()

            # Detect CSV-dump pattern: lines starting with quoted strings and commas
            if re.match(self.patterns.CSV_DUMP_PATTERN, line_stripped):
                if not in_csv_block:
                    in_csv_block = True
                    csv_block = []
                csv_block.append(line_stripped)
            else:
                # If we were collecting CSV lines, process them now
                if in_csv_block and csv_block:
                    markdown_table = self._convert_csv_to_markdown(csv_block)
                    if markdown_table:
                        repaired_lines.append(markdown_table)
                    csv_block = []
                    in_csv_block = False

                repaired_lines.append(line)

        # Handle CSV block at end of file
        if in_csv_block and csv_block:
            markdown_table = self._convert_csv_to_markdown(csv_block)
            if markdown_table:
                repaired_lines.append(markdown_table)

        return "\n".join(repaired_lines)

    def _convert_csv_to_markdown(self, csv_lines: list[str]) -> Optional[str]:
        """Convert CSV lines to Markdown table format.

        Args:
            csv_lines: List of CSV-formatted lines

        Returns:
            Markdown table string or None if conversion fails
        """
        if not csv_lines:
            return None

        try:
            # Parse CSV lines
            rows = []
            for line in csv_lines:
                # Handle hanging commas by checking if line ends with comma
                if line.endswith(","):
                    # This might be a continuation - for now, just strip trailing comma
                    line = line.rstrip(",")

                # Use CSV reader to properly handle quoted fields
                reader = csv.reader(io.StringIO(line))
                try:
                    row = next(reader)
                    if row:  # Only add non-empty rows
                        rows.append(row)
                except csv.Error:
                    # If CSV parsing fails, try simple split as fallback
                    # Remove quotes and split by comma
                    cleaned = line.replace('"', "")
                    row = [cell.strip() for cell in cleaned.split(",") if cell.strip()]
                    if row:
                        rows.append(row)
                except StopIteration:
                    continue

            if not rows:
                return None

            # Convert to Markdown table
            markdown_lines = []

            # Header row
            if rows:
                header = rows[0]
                markdown_lines.append("| " + " | ".join(header) + " |")
                # Separator row
                markdown_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                # Data rows
                for row in rows[1:]:
                    # Pad row to match header length
                    while len(row) < len(header):
                        row.append("")
                    # Truncate if too long
                    row = row[: len(header)]
                    markdown_lines.append("| " + " | ".join(row) + " |")

            return "\n".join(markdown_lines)

        except Exception as e:
            logger.warning(f"Failed to convert CSV to Markdown: {e}")
            return None

    def _repair_split_header_tables(self, content: str) -> str:
        """Repair tables with split headers (NEJM/Lancet style).

        Args:
            content: Markdown content

        Returns:
            Content with split headers merged
        """
        lines = content.split("\n")
        repaired_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]
            line_stripped = line.strip()

            # Check if this looks like a table row
            if "|" in line_stripped:
                # Check if next line is also a table row
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if "|" in next_line:
                        # Check if first row has empty cells except first column
                        cells = [
                            cell.strip() for cell in line_stripped.split("|")[1:-1]
                        ]
                        next_cells = [
                            cell.strip() for cell in next_line.split("|")[1:-1]
                        ]

                        # If first row is mostly empty except first cell, merge with next
                        if (
                            len(cells) > 1
                            and len(next_cells) > 1
                            and cells[0]
                            and not any(cells[1:])  # All other cells empty
                            and next_cells[0]  # Next row has content
                        ):
                            # Merge: combine first cell from row 1 with rest from row 2
                            merged_cells = [
                                cells[0] + " " + next_cells[0]
                            ] + next_cells[1:]
                            merged_row = "| " + " | ".join(merged_cells) + " |"
                            repaired_lines.append(merged_row)
                            i += 2  # Skip both original rows
                            continue

            repaired_lines.append(line)
            i += 1

        return "\n".join(repaired_lines)

    def _merge_multipage_tables(self, content: str) -> str:
        """Merge tables that span multiple pages.

        Args:
            content: Markdown content

        Returns:
            Content with multi-page tables merged
        """
        lines = content.split("\n")
        merged_lines: list[str] = []
        i = 0
        current_table: list[str] = []
        in_table = False

        while i < len(lines):
            line = lines[i]
            line_stripped = line.strip()

            # Check for table continuation marker
            if re.search(self.patterns.TABLE_CONTINUED, line_stripped, re.IGNORECASE):
                # Skip the continuation marker, keep collecting table rows
                i += 1
                continue

            # Check if this is a table row
            if "|" in line_stripped:
                if not in_table:
                    in_table = True
                    current_table = []

                current_table.append(line)

                # Check if next line is not a table row (end of table)
                if i + 1 >= len(lines) or "|" not in lines[i + 1].strip():
                    # End of table - check if we should merge with previous table
                    if len(merged_lines) > 0:
                        prev_line = merged_lines[-1].strip()
                        if "|" in prev_line:
                            # Previous line was a table row - check column count
                            prev_cols = prev_line.count("|") - 1
                            current_cols = line_stripped.count("|") - 1

                            if prev_cols == current_cols and prev_cols > 0:
                                # Same column count - merge tables
                                # Remove the last line (it was the end of previous table)
                                merged_lines.pop()
                                # Add all rows from current table
                                merged_lines.extend(current_table)
                                current_table = []
                                in_table = False
                                i += 1
                                continue

                i += 1
                continue

            # Not a table row
            if in_table:
                # We were in a table, now we're not - flush the table
                merged_lines.extend(current_table)
                current_table = []
                in_table = False

            merged_lines.append(line)
            i += 1

        # Flush any remaining table
        if in_table and current_table:
            merged_lines.extend(current_table)

        return "\n".join(merged_lines)

    def _remove_image_references(self, content: str) -> str:
        """Remove markdown image references.

        Args:
            content: Markdown content

        Returns:
            Content with image references removed
        """
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Remove markdown image syntax: ![](path) or ![alt](path)
            if re.match(r"^!\[.*?\]\(.*?\)$", line_stripped):
                continue  # Skip image lines

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _remove_references_section(self, content: str) -> str:
        """Remove References section and everything after it.

        Args:
            content: Markdown content

        Returns:
            Content with References section removed
        """
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Check for References section header (various formats)
            if re.match(
                r"^#{1,4}\s*\*?\*?References\*?\*?$", line_stripped, re.IGNORECASE
            ):
                # Stop processing - remove this line and everything after
                break

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _remove_appendix_section(self, content: str) -> str:
        """Remove Appendix section and everything after it.

        Args:
            content: Markdown content

        Returns:
            Content with Appendix section removed
        """
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Check for Appendix section header (various formats)
            if re.match(
                r"^#{1,4}\s*\*?\*?Appendix\*?\*?$", line_stripped, re.IGNORECASE
            ):
                # Stop processing - remove this line and everything after
                break

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _normalize_citations(self, content: str) -> str:
        """Normalize citation formats to reduce token noise.

        Args:
            content: Markdown content

        Returns:
            Content with normalized citations
        """
        # Convert [1-3] or ^1-3^ to (1-3)
        content = re.sub(self.patterns.CITATION_BRACKETS, r"(\1)", content)
        content = re.sub(self.patterns.CITATION_CARET, r"(\1)", content)

        return content

    def _final_cleanup(self, content: str) -> str:
        """Final cleanup: normalize whitespace and remove excessive blank lines.

        Args:
            content: Markdown content

        Returns:
            Content with normalized whitespace
        """
        # Normalize line endings
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        # Remove excessive blank lines (more than 2 consecutive)
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Trim trailing whitespace from each line
        lines = [line.rstrip() for line in content.split("\n")]
        content = "\n".join(lines)

        # Remove leading/trailing blank lines
        content = content.strip()

        return content
