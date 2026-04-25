"""Postprocessing service for orchestrating conference abstract processing."""

import logging
import re
from pathlib import Path

from domain.interfaces import PostprocessingServiceInterface, PostprocessorInterface
from domain.models import (
    ConferenceType,
    PostprocessingConfiguration,
    PostprocessingResult,
)
from infrastructure.asco_postprocessor import ASCOPostprocessor
from infrastructure.esmo_postprocessor import ESMOPostprocessor

logger = logging.getLogger(__name__)


class PostprocessingService(PostprocessingServiceInterface):
    """Service for orchestrating conference abstract postprocessing."""

    def __init__(self) -> None:
        """Initialize the postprocessing service."""
        self.processors: dict[ConferenceType, PostprocessorInterface] = {
            ConferenceType.ASCO: ASCOPostprocessor(),
            ConferenceType.ESMO: ESMOPostprocessor(),
        }

    def _get_processor(self, conference_type: ConferenceType) -> PostprocessorInterface:
        """Get the appropriate processor for a conference type."""
        if conference_type not in self.processors:
            raise ValueError(f"Unsupported conference type: {conference_type}")
        return self.processors[conference_type]

    def _extract_tables_by_id(self, content: str) -> dict[str, str]:
        """Extract all tables from content and return a dict mapping abstract ID to table content.

        Tables are identified by their ID in the format: | Table: 784O | or | Table: 7840 |
        Table IDs are normalized (e.g., 7840 -> 784O) to match abstract IDs.
        Handles ESMO 2022 (78xx) and ESMO 2023 (10xx, 11xx) patterns.
        """
        tables_by_id = {}

        lines = content.split("\n")
        current_table_id = None
        current_table_lines = []
        in_table = False
        waiting_for_table_start = (
            False  # For cases like "Table: 1123P description" where table starts later
        )

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if this line starts a new table with an ID
            # Pattern: | Table: 784O | or | Table: 7840 | or | Table: 805P |
            # Also handle: | Table: | 832P | (ID in first column) or plain text "Table: 872P"
            # Also handle ESMO 2023: 10xx, 11xx patterns
            # Also handle ESMO 2024: 10xx patterns (1076O, 1077MO, 1082O, 1083P, etc.)
            # Also handle split IDs: | Table: 109! | 5P | (should be 1095P) or | Table: 111   | L2P | (should be 1112P)
            # Note: [MO] matches single M or O, but we need MO as a sequence, so use (?:MO|M|O) with MO first
            table_id_match = re.search(
                r"(?:^\| Table:\s*([78]\d{3}|[78]\d{2}(?:MO|O|P|TiP)|10[67]\d(?:0|MO|O|M|P|TiP)|10[89]\d(?:0|MO|O|M|P|TiP)|11[0-9]\d(?:0|MO|O|M|P|TiP))|^\| Table:\s*\|\s*([78]\d{3}|[78]\d{2}(?:MO|O|P|TiP)|10[67]\d(?:0|MO|O|M|P|TiP)|10[89]\d(?:0|MO|O|M|P|TiP)|11[0-9]\d(?:0|MO|O|M|P|TiP))|^Table:\s*([78]\d{3}|[78]\d{2}(?:MO|O|P|TiP)|10[67]\d(?:0|MO|O|M|P|TiP)|10[89]\d(?:0|MO|O|M|P|TiP)|11[0-9]\d(?:0|MO|O|M|P|TiP)))",
                stripped,
            )
            if table_id_match:
                # Get the matched ID (could be from any of the three groups)
                table_id = (
                    table_id_match.group(1)
                    or table_id_match.group(2)
                    or table_id_match.group(3)
                )
                # Save previous table if any
                if current_table_id and current_table_lines:
                    table_content = "\n".join(current_table_lines).strip()
                    if table_content:
                        tables_by_id[current_table_id] = table_content

                # Normalize OCR errors: 7840 -> 784O, 7860 -> 786O, etc.
                if re.match(r"^78[4-9]0$", table_id):
                    table_id = table_id[:-1] + "O"
                elif re.match(r"^10[67]\d0$", table_id):
                    # ESMO 2024: 10760 -> 1076O, 10820 -> 1082O
                    table_id = table_id[:-1] + "O"
                elif re.match(r"^10[89]\d0$", table_id):
                    table_id = table_id[:-1] + "O"
                elif re.match(r"^11[0-9]\d0$", table_id):
                    table_id = table_id[:-1] + "O"

                # Check if this is a markdown table row (starts with |) or plain text
                if stripped.startswith("|"):
                    # Table starts immediately
                    current_table_id = table_id
                    current_table_lines = [line]
                    in_table = True
                    waiting_for_table_start = False
                else:
                    # Plain text "Table: 1123P description" - table will start later
                    current_table_id = table_id
                    current_table_lines = [line]  # Include the header line
                    in_table = False
                    waiting_for_table_start = True
            elif waiting_for_table_start:
                # We're waiting for the actual table to start after a "Table: ID description" line
                if stripped.startswith("|") and "|" in stripped[1:]:
                    # Table has started
                    current_table_lines.append(line)
                    in_table = True
                    waiting_for_table_start = False
                elif not stripped:
                    # Empty line - continue waiting
                    current_table_lines.append(line)
                else:
                    # Description text - include it
                    current_table_lines.append(line)
            elif in_table:
                # Check if this is a table line (starts with | and has at least one more |)
                if stripped.startswith("|") and "|" in stripped[1:]:
                    # Continue current table
                    current_table_lines.append(line)
                elif not stripped:
                    # Empty line - might be within table or end of table
                    # Check next few lines to see if table continues
                    next_non_empty = None
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if lines[j].strip():
                            next_non_empty = lines[j].strip()
                            break

                    if (
                        next_non_empty
                        and next_non_empty.startswith("|")
                        and "|" in next_non_empty[1:]
                    ):
                        # Table continues - include empty line
                        current_table_lines.append(line)
                    else:
                        # Table ended - save it
                        if current_table_id and current_table_lines:
                            table_content = "\n".join(current_table_lines).strip()
                            if table_content:
                                tables_by_id[current_table_id] = table_content
                        current_table_id = None
                        current_table_lines = []
                        in_table = False
                        waiting_for_table_start = False
                else:
                    # Non-empty, non-table line - table has ended
                    # Save the table
                    if current_table_id and current_table_lines:
                        table_content = "\n".join(current_table_lines).strip()
                        if table_content:
                            tables_by_id[current_table_id] = table_content
                    current_table_id = None
                    current_table_lines = []
                    in_table = False
                    waiting_for_table_start = False
            else:
                # Try to handle split table IDs: | Table: 109! | 5P | or | Table: 111   | L2P |
                split_id_match = re.search(
                    r"^\| Table:\s*(\d+)[!L]?\s*\|\s*([0-9L]?[0-9]P)", stripped
                )
                if split_id_match:
                    part1 = split_id_match.group(1)
                    part2 = split_id_match.group(2)
                    # Fix OCR errors: "!" -> "5", "L" -> "2"
                    part2 = part2.replace("L", "2").replace("!", "5")
                    # Combine parts
                    if part1.startswith("109") and part2.startswith("5"):
                        table_id = "1095P"
                    elif part1.startswith("111") and part2.startswith("2"):
                        table_id = "1112P"
                    else:
                        table_id = part1 + part2

                    # Save previous table if any
                    if current_table_id and current_table_lines:
                        table_content = "\n".join(current_table_lines).strip()
                        if table_content:
                            tables_by_id[current_table_id] = table_content

                    current_table_id = table_id
                    current_table_lines = [line]
                    in_table = True
                    waiting_for_table_start = False

        # Save last table if any
        if current_table_id and current_table_lines:
            table_content = "\n".join(current_table_lines).strip()
            if table_content:
                tables_by_id[current_table_id] = table_content

        logger.info(f"Extracted {len(tables_by_id)} tables with IDs")
        return tables_by_id

    def _split_abstracts(
        self, content: str, conference_type: ConferenceType, input_path: str = ""
    ) -> list[str]:
        """Split raw content into individual abstracts."""
        if conference_type == ConferenceType.ASCO:
            # ASCO format: Split by --- page separators, then re-attach orphan table
            # chunks (table captions + HTML tables split off from their parent abstract)
            raw = [p.strip() for p in re.split(r"\n---\n", content) if p.strip()]
            abstract_id_pat = re.compile(
                r"\b(?:(?:TPS|LBA)\s*)?(?:100\d{2}|9[56]\d{2})\b"
            )
            section_pat = re.compile(
                r"(?i)(background|methods|results|conclusions)\s*[:\*]"
            )
            merged: list[str] = []
            for chunk in raw:
                is_orphan = not abstract_id_pat.search(
                    chunk[:200]
                ) and not section_pat.search(chunk)
                if is_orphan and merged:
                    merged[-1] = merged[-1] + "\n\n" + chunk
                else:
                    merged.append(chunk)
            return merged

        elif conference_type == ConferenceType.ESMO:
            # ESMO format: Split by DOI links (more reliable - each abstract ends with a DOI)
            # Each abstract should end with: https://doi.org/10.1016/j.annonc.YYYY.MM.NNNN
            # Pattern handles both plain DOIs and markdown link formats like:
            # https://doi.org/[10.1016/j.annonc.2020.08.1278](https://doi.org/10.1016/j.annonc.2020.08.1278)

            # Pattern for DOI links - matches the actual DOI URL
            # Handles:
            # - Plain DOIs: https://doi.org/10.1016/j.annonc.2020.08.1200
            # - OCR errors: https://doi.org/10.1016/i.annonc.2020.08.1261 (i instead of j)
            # - Markdown links: https://doi.org/[10.1016/j.annonc.2020.08.1278](...)
            # - HTML artifacts: https://doi.org/10.1016/j.annonc.2020.08.1223>
            doi_pattern = (
                r"https://doi\.org/10\.1016/[ij]\.annonc\.\d{4}\.\d{2}\.\d{4}[^\)\s]*"
            )

            # Find all DOI positions in the content
            all_doi_matches = list(re.finditer(doi_pattern, content))

            # Deduplicate: if two DOIs are very close together (within 100 chars),
            # they're likely the same DOI in a markdown link format
            # Keep only the last occurrence (the one in parentheses)
            doi_matches = []
            for i, match in enumerate(all_doi_matches):
                if i == 0:
                    doi_matches.append(match)
                else:
                    prev_match = all_doi_matches[i - 1]
                    # If this DOI is very close to previous and has same DOI number, skip it
                    distance = match.start() - prev_match.end()
                    if distance < 100 and match.group() == prev_match.group():
                        # This is a duplicate in markdown link - skip the first one, keep this one
                        doi_matches[-1] = match  # Replace previous with this one
                    else:
                        doi_matches.append(match)

            # For ESMO 2022, use abstract ID splitting as primary method (not all abstracts have DOIs)
            is_2022 = "2022" in input_path

            # For 2022, prefer abstract ID splitting if we have few DOIs
            if is_2022 and len(doi_matches) < 50:
                # Use abstract ID splitting for ESMO 2022
                # Pattern matches: 7840, 7850 (4-digit), 791MO, 792MO, 796P, etc. (3-digit + suffix)
                # Also match image markers that often precede abstracts: ![](_page_X_Picture_Y.jpeg) or ![](_page_X_Figure_Y.jpeg)
                # ESMO 2022: 78xx patterns, ESMO 2024: 10xx patterns, ESMO 2025: 16xxeP and 17xxeTiP patterns
                abstract_id_pattern = r"^([78]\d{3}|[78]\d{2}(?:O|MO|P|eP|eTiP|TiP)|10[67]\d[0O]|10[67]\d[MO]|10[67]\dP|10[67]\deP|10[67]\deTiP|10[67]\dTiP|1\d{3,4}eP|1\d{3,4}eTiP)$"
                image_marker_pattern = (
                    r"^!\[\]\(_page_\d+_(Picture|Figure)_\d+\.jpeg\)$"
                )
                # Pattern for "Background:" that appears at start of abstract (after DOI or image)
                background_pattern = (
                    r"^(?:<span[^>]*>)*\s*(?:\*\*)?Background(?:\*\*)?:"
                )

                lines = content.split("\n")
                abstract_texts = []
                current_abstract: list[str] = []
                in_abstract = False
                last_was_doi = False
                last_was_image = False

                for i, line in enumerate(lines):
                    stripped_line = line.strip()

                    # Check if this line is an abstract ID (standalone line with just the ID)
                    if re.match(abstract_id_pattern, stripped_line):
                        if in_abstract and current_abstract:
                            abstract_text = "\n".join(current_abstract).strip()
                            if len(abstract_text) > 50:
                                abstract_texts.append(abstract_text)
                        current_abstract = [line]
                        in_abstract = True
                        last_was_doi = False
                        last_was_image = False
                    # Check for image markers that often precede abstracts
                    elif re.match(image_marker_pattern, stripped_line):
                        if in_abstract and current_abstract:
                            # If we're already in an abstract, this might be a new one
                            # Check if previous line was a DOI or empty, or if we just saw a DOI recently
                            if i > 0 and (last_was_doi or lines[i - 1].strip() == ""):
                                abstract_text = "\n".join(current_abstract).strip()
                                if len(abstract_text) > 50:
                                    abstract_texts.append(abstract_text)
                                current_abstract = [line]
                                in_abstract = True
                            else:
                                current_abstract.append(line)
                        else:
                            current_abstract = [line]
                            in_abstract = True
                        last_was_image = True
                        last_was_doi = False
                    # Check for "Background:" that appears after DOI or image (start of new abstract)
                    elif re.match(
                        background_pattern, stripped_line, re.IGNORECASE
                    ) and (last_was_doi or last_was_image):
                        if in_abstract and current_abstract:
                            abstract_text = "\n".join(current_abstract).strip()
                            if len(abstract_text) > 50:
                                abstract_texts.append(abstract_text)
                        current_abstract = [line]
                        in_abstract = True
                        last_was_doi = False
                        last_was_image = False
                    # Check if this line contains a DOI
                    elif re.search(doi_pattern, line):
                        current_abstract.append(line)
                        last_was_doi = True
                        last_was_image = False
                    # After a DOI, continue collecting content (tables, footnotes) until we hit a new abstract marker
                    # New abstract markers: abstract ID, image marker, or title after empty line + image
                    elif last_was_doi and stripped_line:
                        # Check if this is a new abstract starting
                        is_new_abstract = False
                        # Don't treat tables as new abstracts - they belong to current abstract
                        is_table_line = (
                            stripped_line.startswith("|") and "|" in stripped_line[1:]
                        )
                        is_table_footer = (
                            stripped_line
                            and not stripped_line.startswith("|")
                            and not stripped_line.startswith("Background")
                            and not stripped_line.startswith("Methods")
                            and not stripped_line.startswith("Results")
                            and not stripped_line.startswith("Conclusions")
                            and not stripped_line.startswith("Clinical trial")
                            and not stripped_line.startswith("Editorial")
                            and not stripped_line.startswith("Legal entity")
                            and not stripped_line.startswith("Funding")
                            and not stripped_line.startswith("Disclosure")
                            and not stripped_line.startswith("https://doi.org")
                            and not stripped_line.startswith("![]")
                            and i > 0
                            and lines[i - 1].strip().startswith("|")
                        )

                        if is_table_line or is_table_footer:
                            # This is table content - continue with current abstract
                            current_abstract.append(line)
                        # Check for abstract ID
                        elif re.match(abstract_id_pattern, stripped_line):
                            is_new_abstract = True
                        # Check for markdown heading with abstract ID (e.g., "## 850P")
                        elif re.match(
                            r"^##+\s*([78]\d{3}|[78]\d{2}(?:O|MO|P|TiP))$",
                            stripped_line,
                        ):
                            is_new_abstract = True
                        # Check for image marker - this starts a new abstract
                        elif re.match(image_marker_pattern, stripped_line):
                            is_new_abstract = True
                        # Check for title after empty line (likely new abstract)
                        # But only if previous line was empty AND we haven't seen an image marker recently
                        elif (
                            i > 0
                            and lines[i - 1].strip() == ""
                            and not last_was_image
                            and (
                                stripped_line.startswith("#")
                                or (
                                    len(stripped_line) > 20
                                    and len(stripped_line) < 200
                                    and not re.match(
                                        r"^(Background|Methods|Results|Conclusions|Trial design|Clinical trial identification|Editorial acknowledgement|Legal entity|Funding|Disclosure):",
                                        stripped_line,
                                        re.IGNORECASE,
                                    )
                                    and not re.match(r"^https://", stripped_line)
                                    and not re.match(r"^!\[\]", stripped_line)
                                )
                            )
                        ):
                            # Check if next few lines contain author info
                            lookahead_lines = lines[i + 1 : min(i + 5, len(lines))]
                            has_author_info = any(
                                "<sup>" in line for line in lookahead_lines
                            )
                            has_plain_authors = any(
                                re.match(r"^[A-Z]\.\s*[A-Z][a-z]+", line.strip())
                                for line in lookahead_lines
                                if line.strip()
                            )
                            # Check for LaTeX-formatted author lines
                            has_latex_authors = any(
                                "$" in line and ("\\text{" in line or "\\frac{" in line)
                                for line in lookahead_lines
                            )
                            if (
                                has_author_info
                                or has_plain_authors
                                or has_latex_authors
                            ):
                                is_new_abstract = True

                        if is_new_abstract:
                            # Start new abstract
                            if current_abstract:
                                abstract_text = "\n".join(current_abstract).strip()
                                if len(abstract_text) > 50:
                                    abstract_texts.append(abstract_text)
                            current_abstract = [line]
                            in_abstract = True
                            # If this is an image marker, set flag so next line (title) gets added to this abstract
                            if re.match(image_marker_pattern, stripped_line):
                                last_was_image = True
                            else:
                                last_was_image = False
                            last_was_doi = False
                        else:
                            # Continue with current abstract (table, footnote, etc.)
                            current_abstract.append(line)
                    # Check for titles that appear after image markers (even if DOI was before image)
                    elif last_was_image and stripped_line:
                        # Check if this looks like a title:
                        # 1. Markdown heading starting with #
                        # 2. Or a line that's not too long and not a section header, followed by author info
                        is_title = False
                        if stripped_line.startswith("#"):
                            # Markdown heading - likely a title
                            is_title = True
                        elif (
                            len(stripped_line) > 20
                            and len(stripped_line) < 200
                            and not re.match(
                                r"^(Background|Methods|Results|Conclusions|Trial design|Clinical trial identification|Editorial acknowledgement|Legal entity|Funding|Disclosure):",
                                stripped_line,
                                re.IGNORECASE,
                            )
                            and not re.match(r"^https://", stripped_line)
                            and not re.match(r"^!\[\]", stripped_line)
                        ):
                            # Check if next few lines contain author info (have <sup> tags, LaTeX formatting, or look like author names)
                            # This indicates it's likely a title
                            lookahead_lines = lines[i + 1 : min(i + 5, len(lines))]
                            has_author_info = any(
                                "<sup>" in line for line in lookahead_lines
                            )
                            # Check for plain author lines (names with initials like "Y. Yang, B. Lian" or "J.T. Moyers<sup>1</sup>")
                            # Pattern matches: "Y. Yang" or "J.T. Moyers" (with or without space after period)
                            has_plain_authors = any(
                                re.match(r"^[A-Z]\.\s*[A-Z][a-z]+", line.strip())
                                for line in lookahead_lines
                                if line.strip()
                            )
                            # Check for LaTeX-formatted author lines (e.g., $\frac{\text{...}}$ or $\text{...}$)
                            has_latex_authors = any(
                                "$" in line and ("\\text{" in line or "\\frac{" in line)
                                for line in lookahead_lines
                            )
                            if (
                                has_author_info
                                or has_plain_authors
                                or has_latex_authors
                            ):
                                is_title = True

                        if is_title:
                            # If we just saw an image marker (last_was_image is True), always add title to current abstract
                            # This handles the case: DOI -> image marker -> title
                            if last_was_image and in_abstract and current_abstract:
                                # Add title to existing abstract that started with image marker
                                current_abstract.append(line)
                                last_was_doi = False
                                last_was_image = False
                            else:
                                # Check if current abstract only has an image marker (and possibly empty lines)
                                non_empty_lines = [
                                    line for line in current_abstract if line.strip()
                                ]
                                if (
                                    in_abstract
                                    and current_abstract
                                    and len(non_empty_lines) == 1
                                    and re.match(
                                        image_marker_pattern, non_empty_lines[0].strip()
                                    )
                                ):
                                    # Add title to existing abstract that started with image marker
                                    current_abstract.append(line)
                                    last_was_doi = False
                                    last_was_image = False
                                else:
                                    # Start new abstract with title
                                    if in_abstract and current_abstract:
                                        abstract_text = "\n".join(
                                            current_abstract
                                        ).strip()
                                        if len(abstract_text) > 50:
                                            abstract_texts.append(abstract_text)
                                    current_abstract = [line]
                                    in_abstract = True
                                    last_was_doi = False
                                    last_was_image = False
                        else:
                            # Not a title, continue with current abstract
                            if in_abstract:
                                current_abstract.append(line)
                                if stripped_line:
                                    last_was_doi = False
                                    last_was_image = False
                    elif in_abstract:
                        current_abstract.append(line)
                        # Don't reset last_was_image flag on empty lines - we need it for title detection
                        # Only reset on non-empty content that's not a title
                        if stripped_line:
                            # Check if this might be a title (don't reset flag yet)
                            is_potential_title = stripped_line.startswith("#") or (
                                len(stripped_line) > 20
                                and len(stripped_line) < 200
                                and not re.match(
                                    r"^(Background|Methods|Results|Conclusions|Trial design|Clinical trial identification|Editorial acknowledgement|Legal entity|Funding|Disclosure):",
                                    stripped_line,
                                    re.IGNORECASE,
                                )
                                and not re.match(r"^https://", stripped_line)
                                and not re.match(r"^!\[\]", stripped_line)
                            )
                            if not is_potential_title:
                                last_was_doi = False
                                last_was_image = False

                if in_abstract and current_abstract:
                    abstract_text = "\n".join(current_abstract).strip()
                    if len(abstract_text) > 50:
                        abstract_texts.append(abstract_text)

                if len(abstract_texts) > len(doi_matches):
                    return abstract_texts

            if not doi_matches:
                # Fallback: try splitting by abstract IDs if no DOIs found
                abstract_id_pattern = r"^(?:#+\s*)?(1\d{3,4}[A-Za-z]*|[78]\d{2}(?:O|MO|P|eP|eTiP|TiP)?|[78]\d{3})(?:\s|$)"
                lines = content.split("\n")
                abstract_texts = []
                current_abstract = []
                in_abstract = False

                for line in lines:
                    stripped_line = line.strip()
                    if re.match(abstract_id_pattern, stripped_line):
                        if in_abstract and current_abstract:
                            abstract_text = "\n".join(current_abstract).strip()
                            if len(abstract_text) > 50:
                                abstract_texts.append(abstract_text)
                        current_abstract = [line]
                        in_abstract = True
                    elif in_abstract:
                        current_abstract.append(line)

                if in_abstract and current_abstract:
                    abstract_text = "\n".join(current_abstract).strip()
                    if len(abstract_text) > 50:
                        abstract_texts.append(abstract_text)

                return abstract_texts

            # Split content by DOI positions
            # Strategy: Split content at each DOI, then for each section find where the abstract starts
            abstract_texts = []
            # Updated pattern to include ESMO 2022 format: 7840, 7850, etc. (4-digit numbers starting with 78)
            # Also includes ESMO 2025 format: 1686eP (lowercase e followed by P) and 1703eTiP (lowercase e followed by TiP)
            abstract_id_pattern = r"^(?:#+\s*)?(1\d{3,4}[A-Za-z]*|[78]\d{2}(?:O|MO|P|eP|eTiP|TiP)?|[78]\d{3})(?:\s|$)"

            # Split content at each DOI position
            split_positions = [0]  # Start with beginning
            for match in doi_matches:
                # Split after the DOI (include the DOI in the abstract)
                split_positions.append(match.end())
            split_positions.append(len(content))  # End with file end

            # Process each section between split positions
            for i in range(len(split_positions) - 1):
                section_start = split_positions[i]
                section_end = split_positions[i + 1]
                section_content = content[section_start:section_end]

                # Find where the abstract actually starts in this section
                # (look for abstract ID, skip header content)
                lines = section_content.split("\n")
                abstract_start_idx = 0

                for j, line in enumerate(lines):
                    stripped = line.strip()
                    # Skip empty lines and header content
                    if not stripped:
                        continue
                    # Check if this is an abstract ID (start of abstract)
                    if re.match(abstract_id_pattern, stripped):
                        abstract_start_idx = j
                        break
                    # Also check if we see content that indicates we're in an abstract
                    if any(
                        keyword in stripped.lower()
                        for keyword in ["background:", "methods:", "results:"]
                    ):
                        # We're already in an abstract, start from beginning of section
                        break

                # Extract the abstract from the found start
                abstract_lines = lines[abstract_start_idx:]
                abstract_text = "\n".join(abstract_lines).strip()

                # Only add if it looks like a valid abstract
                if len(abstract_text) > 50:
                    abstract_texts.append(abstract_text)

            return abstract_texts

        else:
            raise ValueError(f"Unsupported conference type: {conference_type}")

    async def process_file(
        self, input_path: str, output_path: str, config: PostprocessingConfiguration
    ) -> PostprocessingResult:
        """Process a single file containing conference abstracts."""
        try:
            logger.info(f"Processing file: {input_path}")

            # Read input file
            input_file = Path(input_path)
            if not input_file.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            with open(input_file, encoding="utf-8") as f:
                content = f.read()

            # Get the appropriate processor
            processor = self._get_processor(config.conference_type)

            # Extract all tables with their IDs before splitting abstracts (for ESMO 2022/2023/2024)
            tables_by_id = {}
            if config.conference_type == ConferenceType.ESMO and (
                "2022" in input_path or "2023" in input_path or "2024" in input_path
            ):
                tables_by_id = self._extract_tables_by_id(content)

            # Split content into individual abstracts
            abstract_texts = self._split_abstracts(
                content, config.conference_type, input_path
            )
            logger.info(f"Found {len(abstract_texts)} abstracts to process")

            # Process each abstract
            formatted_abstracts = []
            abstracts_with_warnings = 0
            structured_metadata_count = 0
            conference_specific_features = 0
            errors = []

            # For ESMO 2020/2021/2022/2023/2024, use expected ID list to assign correct IDs
            expected_ids = None
            if config.conference_type == ConferenceType.ESMO:
                if "2020" in input_path:
                    from infrastructure.esmo_postprocessor import ESMO_2020_EXPECTED_IDS

                    expected_ids = ESMO_2020_EXPECTED_IDS
                elif "2021" in input_path:
                    from infrastructure.esmo_postprocessor import ESMO_2021_EXPECTED_IDS

                    expected_ids = ESMO_2021_EXPECTED_IDS
                elif "2022" in input_path:
                    from infrastructure.esmo_postprocessor import ESMO_2022_EXPECTED_IDS

                    expected_ids = ESMO_2022_EXPECTED_IDS
                elif "2023" in input_path:
                    from infrastructure.esmo_postprocessor import ESMO_2023_EXPECTED_IDS

                    expected_ids = ESMO_2023_EXPECTED_IDS
                elif "2024" in input_path:
                    from infrastructure.esmo_postprocessor import ESMO_2024_EXPECTED_IDS

                    expected_ids = ESMO_2024_EXPECTED_IDS

            # First pass: normalize OCR errors and collect extracted IDs
            parsed_abstracts_list = []
            extracted_id_to_index = {}  # Map extracted ID to abstract index

            for i, abstract_text in enumerate(abstract_texts):
                try:
                    parsed_abstract = await processor.parse_abstract(abstract_text)

                    # Filter out invalid abstracts (no title or minimal content)
                    # Skip abstracts that are just image markers, section headers, or have no meaningful content
                    if (
                        parsed_abstract.title == "N/A"
                        or not parsed_abstract.title.strip()
                    ):
                        logger.warning(f"Skipping abstract {i}: No title found")
                        continue

                    # Skip abstracts that are too short (likely just headers or image markers)
                    # Check if abstract has meaningful content beyond just the title
                    has_content = any(
                        [
                            parsed_abstract.background,
                            parsed_abstract.methods,
                            parsed_abstract.results,
                            parsed_abstract.conclusions,
                            parsed_abstract.trial_design,
                            parsed_abstract.authors_and_affiliations,
                        ]
                    )
                    if not has_content and len(abstract_text.strip()) < 100:
                        logger.warning(
                            f"Skipping abstract {i}: Insufficient content (likely header/image marker only)"
                        )
                        continue

                    # Normalize known OCR errors first
                    if parsed_abstract.id == "10760":
                        parsed_abstract.id = "1076O"
                    elif parsed_abstract.id == "10360":
                        parsed_abstract.id = "1036O"
                    elif parsed_abstract.id == "10370":
                        parsed_abstract.id = "1037O"
                    elif parsed_abstract.id == "10400":
                        parsed_abstract.id = "1040O"
                    elif re.match(r"^78[4-9]0$", parsed_abstract.id):
                        parsed_abstract.id = parsed_abstract.id[:-1] + "O"
                    elif re.match(r"^10[89]\d0$", parsed_abstract.id):
                        # ESMO 2023: 10810 -> 1081O, 10820 -> 1082O, etc.
                        parsed_abstract.id = parsed_abstract.id[:-1] + "O"
                    elif re.match(r"^11[0-9]\d0$", parsed_abstract.id):
                        # ESMO 2023: 11000 -> 1100O, 11100 -> 1110O, etc.
                        parsed_abstract.id = parsed_abstract.id[:-1] + "O"

                    # Track extracted IDs (if valid)
                    if (
                        parsed_abstract.id != "N/A"
                        and expected_ids
                        and parsed_abstract.id in expected_ids
                    ):
                        extracted_id_to_index[parsed_abstract.id] = i

                    parsed_abstracts_list.append(parsed_abstract)
                except Exception as e:
                    errors.append(f"Error parsing abstract {i}: {str(e)}")
                    continue

            # Second pass: assign IDs only to abstracts with N/A
            if expected_ids:
                # Track which expected IDs have been assigned
                assigned_ids = set()

                # First, preserve all correctly extracted IDs
                for parsed_abstract in parsed_abstracts_list:
                    if (
                        parsed_abstract.id != "N/A"
                        and expected_ids
                        and parsed_abstract.id in expected_ids
                    ):
                        assigned_ids.add(parsed_abstract.id)

                # Then, assign missing IDs sequentially to abstracts with N/A
                na_indices = [
                    i for i, pa in enumerate(parsed_abstracts_list) if pa.id == "N/A"
                ]
                expected_index = 0

                for na_idx in na_indices:
                    # Find next unassigned expected ID
                    while expected_index < len(expected_ids):
                        expected_id = expected_ids[expected_index]
                        if expected_id not in assigned_ids:
                            parsed_abstracts_list[na_idx].id = expected_id
                            assigned_ids.add(expected_id)
                            expected_index += 1
                            break
                        expected_index += 1

            # Third pass: Assign tables to abstracts based on table IDs (for ESMO 2022/2023/2024)
            # This replaces any tables that were extracted during parsing with the correct ones based on table IDs
            if (
                config.conference_type == ConferenceType.ESMO
                and (
                    "2022" in input_path or "2023" in input_path or "2024" in input_path
                )
                and tables_by_id
            ):
                from infrastructure.esmo_postprocessor import ESMOPostprocessor

                esmo_processor = ESMOPostprocessor()

                # First, remove tables from abstracts that don't match their ID
                # Check if a table in additional_content has a different ID than the abstract
                for parsed_abstract in parsed_abstracts_list:
                    if parsed_abstract.additional_content:
                        # Check if the table has an ID that doesn't match the abstract ID
                        # Handle multiple formats: | Table: 832P |, | Table: | 832P |, Table: 832P
                        # Use same pattern as extraction with MO first to match correctly
                        table_id_match = re.search(
                            r"(?:^\| Table:\s*([78]\d{3}|[78]\d{2}(?:MO|O|P|TiP)|10[67]\d(?:0|MO|O|M|P|TiP)|10[89]\d(?:0|MO|O|M|P|TiP)|11[0-9]\d(?:0|MO|O|M|P|TiP))|^\| Table:\s*\|\s*([78]\d{3}|[78]\d{2}(?:MO|O|P|TiP)|10[67]\d(?:0|MO|O|M|P|TiP)|10[89]\d(?:0|MO|O|M|P|TiP)|11[0-9]\d(?:0|MO|O|M|P|TiP))|^Table:\s*([78]\d{3}|[78]\d{2}(?:MO|O|P|TiP)|10[67]\d(?:0|MO|O|M|P|TiP)|10[89]\d(?:0|MO|O|M|P|TiP)|11[0-9]\d(?:0|MO|O|M|P|TiP)))",
                            parsed_abstract.additional_content,
                            re.MULTILINE,
                        )
                        if table_id_match:
                            table_id = (
                                table_id_match.group(1)
                                or table_id_match.group(2)
                                or table_id_match.group(3)
                            )
                            # Normalize OCR errors
                            if re.match(r"^78[4-9]0$", table_id):
                                table_id = table_id[:-1] + "O"
                            elif re.match(r"^10[67]\d0$", table_id):
                                table_id = table_id[:-1] + "O"
                            elif re.match(r"^10[89]\d0$", table_id):
                                table_id = table_id[:-1] + "O"
                            elif re.match(r"^11[0-9]\d0$", table_id):
                                table_id = table_id[:-1] + "O"
                            # If table ID doesn't match abstract ID, remove it
                            if (
                                parsed_abstract.id != "N/A"
                                and table_id != parsed_abstract.id
                            ):
                                parsed_abstract.additional_content = ""
                                logger.debug(
                                    f"Removed mismatched table {table_id} from abstract {parsed_abstract.id}"
                                )

                # Then, assign correct tables based on table IDs
                for parsed_abstract in parsed_abstracts_list:
                    if (
                        parsed_abstract.id != "N/A"
                        and tables_by_id
                        and parsed_abstract.id in tables_by_id
                    ):
                        # Replace or add the table from the extracted tables
                        table_content = tables_by_id[parsed_abstract.id]
                        if table_content:
                            # Clean the table content using the processor's method
                            parsed_abstract.additional_content = (
                                esmo_processor.clean_table_content(table_content)
                            )
                            logger.debug(
                                f"Assigned table to abstract {parsed_abstract.id}"
                            )

            # Process parsed abstracts
            for i, parsed_abstract in enumerate(parsed_abstracts_list):
                try:
                    # Validate the abstract
                    validation_issues = await processor.validate_abstract(
                        parsed_abstract
                    )
                    if validation_issues:
                        abstracts_with_warnings += 1
                        logger.warning(
                            f"Abstract {parsed_abstract.id}: {', '.join(validation_issues)}"
                        )

                    # Count structured metadata
                    if any(
                        [
                            parsed_abstract.clinical_trial_info,
                            parsed_abstract.sponsor,
                            parsed_abstract.legal_entity,
                            parsed_abstract.funding,
                            parsed_abstract.doi,
                        ]
                    ):
                        structured_metadata_count += 1

                    # Count conference-specific features
                    if config.conference_type == ConferenceType.ESMO:
                        if (
                            parsed_abstract.trial_design
                            or parsed_abstract.doi
                            or parsed_abstract.legal_entity
                        ):
                            conference_specific_features += 1
                    elif config.conference_type == ConferenceType.ASCO:
                        if (
                            parsed_abstract.full_text_reference
                            or "TPS" in parsed_abstract.id
                        ):
                            conference_specific_features += 1

                    # Format to markdown
                    formatted_md = await processor.format_to_markdown(
                        parsed_abstract, config
                    )
                    formatted_abstracts.append(formatted_md)

                except Exception as e:
                    error_msg = f"Error processing abstract {i+1}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Write output file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n\n---\n\n".join(formatted_abstracts))

            # Validate the output file
            validation_summary = await self.validate_file(output_path)

            result = PostprocessingResult(
                success=True,
                abstracts_processed=len(formatted_abstracts),
                abstracts_with_warnings=abstracts_with_warnings,
                structured_metadata_count=structured_metadata_count,
                conference_specific_features=conference_specific_features,
                output_path=output_path,
                validation_summary=validation_summary,
                errors=errors,
            )

            logger.info(
                f"Processing completed: {len(formatted_abstracts)} abstracts processed"
            )
            return result

        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            return PostprocessingResult(
                success=False,
                abstracts_processed=0,
                abstracts_with_warnings=0,
                structured_metadata_count=0,
                conference_specific_features=0,
                output_path=output_path,
                validation_summary={},
                errors=[str(e)],
            )

    async def process_batch(
        self,
        input_paths: list[str],
        output_dir: str,
        config: PostprocessingConfiguration,
    ) -> list[PostprocessingResult]:
        """Process multiple files in batch."""
        results = []
        output_directory = Path(output_dir)
        output_directory.mkdir(parents=True, exist_ok=True)

        for input_path in input_paths:
            input_file = Path(input_path)
            output_file = output_directory / f"enhanced_{input_file.name}"

            result = await self.process_file(input_path, str(output_file), config)
            results.append(result)

        return results

    async def validate_file(self, file_path: str) -> dict[str, any]:
        """Validate a processed file and return validation summary."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            abstracts = content.split("\n\n---\n\n")
            total_abstracts = len(abstracts)
            warnings = 0

            # Count different types of abstracts and features
            structured_metadata_count = 0
            conference_features = {
                "tps_abstracts": 0,
                "full_text_references": 0,
                "trial_design_sections": 0,
                "doi_links": 0,
            }

            # Check for structured headers vs legacy inline format
            structured_sections = [
                "#### Clinical Trial Information:",
                "#### Research Sponsor:",
                "#### Clinical Trial Identification:",
                "#### Legal Entity Responsible for Study:",
                "#### Funding:",
                "#### DOI:",
                "#### Table:",
            ]

            for abstract in abstracts:
                # Count structured metadata
                metadata_present = any(
                    section in abstract for section in structured_sections
                )
                if metadata_present:
                    structured_metadata_count += 1

                # Count conference-specific features
                if "TPS" in abstract:
                    conference_features["tps_abstracts"] += 1
                if "#### Full Text Reference:" in abstract:
                    conference_features["full_text_references"] += 1
                if "#### Trial Design:" in abstract:
                    conference_features["trial_design_sections"] += 1
                if "#### DOI:" in abstract:
                    conference_features["doi_links"] += 1

                # Basic validation
                if "### Abstract ID:" not in abstract:
                    warnings += 1
                # Check if title section is present (new format: #### Title:)
                if "#### Title:" not in abstract:
                    warnings += 1

            rag_optimization = (
                "Enhanced"
                if structured_metadata_count > total_abstracts * 0.8
                else "Basic"
            )

            return {
                "total_abstracts": total_abstracts,
                "abstracts_with_warnings": warnings,
                "structured_metadata_count": structured_metadata_count,
                "rag_optimization": rag_optimization,
                "conference_features": conference_features,
                "validation_status": "Passed" if warnings == 0 else "Warnings",
            }

        except Exception as e:
            return {"error": str(e), "validation_status": "Failed"}
