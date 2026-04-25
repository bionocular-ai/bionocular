"""ASCO abstract postprocessor implementation.

Optimized for DocStrange cloud conversion output, which provides:
- Clean Unicode text (no broken symbols)
- Proper HTML tables
- Bold markdown headers (**Background:**, etc.)
- Minimal need for symbol fixing
"""

import re

from domain.interfaces import PostprocessorInterface
from domain.models import ConferenceType, ParsedAbstract, PostprocessingConfiguration


class ASCOPostprocessor(PostprocessorInterface):
    """Postprocessor for ASCO conference abstracts."""

    def __init__(self):
        """Initialize the ASCO postprocessor."""
        self.conference_type = ConferenceType.ASCO

    def get_conference_type(self) -> ConferenceType:
        """Get the conference type this processor handles."""
        return self.conference_type

    def clean_text(self, text: str) -> str:
        """Clean and normalize text content.

        Removes formatting artifacts that hurt RAG/LLM performance:
        - Italic markers (*text*)
        - HTML superscript/subscript tags
        - Excessive whitespace
        """
        if not text:
            return ""

        # Remove italic markers around single words/genes (common in medical text)
        # *BRAF* → BRAF, *P* → P
        text = re.sub(r"\*([A-Za-z0-9\-]+)\*", r"\1", text)

        # Convert HTML superscript to plain text or caret notation
        # <sup>v600</sup> → v600 (merge with previous word)
        # This handles cases like BRAF<sup>v600</sup> → BRAFv600
        text = re.sub(r"<sup>(.*?)</sup>", r"\1", text)

        # Convert HTML subscript similarly
        text = re.sub(r"<sub>(.*?)</sub>", r"\1", text)

        # Clean up other HTML remnants
        text = re.sub(r"</?em>", "", text)
        text = re.sub(r"</?i>", "", text)
        text = re.sub(r"</?b>", "", text)
        text = re.sub(r"</?strong>", "", text)

        # Normalize line breaks and whitespace
        text = re.sub(r"\\n", " ", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def remove_pdf_artifacts(self, text: str) -> str:
        """Remove PDF conversion artifacts and junk from DocStrange output.

        This pre-cleaning step removes:
        - Page markers (## Page N)
        - Section headers (MELANOMA/SKIN CANCERS)
        - Copyright footers
        - Page separators (---)
        """
        if not text:
            return ""

        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Skip page markers
            if re.match(r"^##\s+Page\s+\d+$", line_stripped):
                continue

            # Skip section headers
            if line_stripped.upper() == "MELANOMA/SKIN CANCERS":
                continue

            # Skip copyright footers
            if "© 2020 American Society of Clinical Oncology" in line:
                continue
            if line_stripped.startswith("<footer>") and "©" in line:
                continue
            if line_stripped == "</footer>":
                continue
            if "Visit abstracts.asco.org" in line:
                continue

            # Skip page separators
            if re.match(r"^-{3,}$", line_stripped):
                continue

            # Keep the line
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def clean_table_content(self, table_text: str) -> str:
        """Convert HTML tables to clean Markdown format for better RAG/LLM performance.

        Markdown tables are:
        - More readable for LLMs
        - Better for embeddings (less noise)
        - Widely supported
        - More compact than HTML
        """
        if not table_text or not table_text.strip():
            return table_text

        # Check if it's an HTML table
        if "<table>" in table_text.lower():
            return self._convert_html_table_to_markdown(table_text)

        # If it's already markdown or other format, just clean it
        cleaned = table_text

        # Convert line breaks in tables to more readable format
        cleaned = re.sub(r"<br\s*/?>", "; ", cleaned)

        # Remove HTML formatting artifacts
        cleaned = re.sub(r"<sup>(.*?)</sup>", r"\1", cleaned)
        cleaned = re.sub(r"<sub>(.*?)</sub>", r"\1", cleaned)
        cleaned = re.sub(r"\*([A-Za-z0-9\-]+)\*", r"\1", cleaned)

        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Expand common medical abbreviations for better RAG retrieval
        abbreviation_map = {
            r"\bmo\b": "months",
            r"\bpts\b": "patients",
            r"\byrs\b": "years",
            r"\bvs\b": "versus",
            r"\bwks\b": "weeks",
        }

        for pattern, replacement in abbreviation_map.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        return cleaned.strip()

    def _convert_html_table_to_markdown(self, html_table: str) -> str:
        """Convert HTML table to Markdown format.

        Handles:
        - <thead> and <tbody> sections
        - Column spanning (colspan)
        - Row headers (<th>)
        - Data cells (<td>)
        """
        from html.parser import HTMLParser

        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows = []
                self.current_row = []
                self.current_cell = []
                self.in_header = False
                self.in_cell = False

            def handle_starttag(self, tag, attrs):
                if tag == "tr":
                    self.current_row = []
                elif tag in ["th", "td"]:
                    self.current_cell = []
                    self.in_cell = True
                    self.current_colspan = 1
                    # Handle colspan
                    for attr, value in attrs:
                        if attr == "colspan":
                            self.current_colspan = int(value)
                elif tag == "thead":
                    self.in_header = True
                elif tag == "tbody":
                    self.in_header = False

            def handle_endtag(self, tag):
                if tag == "tr":
                    if self.current_row:
                        self.rows.append(self.current_row)
                elif tag in ["th", "td"]:
                    cell_text = " ".join(self.current_cell).strip()
                    # Add cell with colspan handling
                    # First cell gets the text, remaining get empty strings
                    self.current_row.append(cell_text)
                    for _ in range(self.current_colspan - 1):
                        self.current_row.append("")
                    self.in_cell = False
                    self.current_cell = []

            def handle_data(self, data):
                if self.in_cell:
                    self.current_cell.append(data.strip())

        # Parse the HTML table
        parser = TableParser()
        try:
            parser.feed(html_table)
        except Exception:
            # If parsing fails, return original
            return html_table

        if not parser.rows:
            return html_table

        # Find max columns
        max_cols = max(len(row) for row in parser.rows) if parser.rows else 0

        # Normalize all rows to have the same number of columns
        normalized_rows = []
        for row in parser.rows:
            if len(row) < max_cols:
                row.extend([""] * (max_cols - len(row)))
            normalized_rows.append(row)

        # Build markdown table
        markdown_lines = []

        for i, row in enumerate(normalized_rows):
            # Build row
            row_text = "| " + " | ".join(cell if cell else " " for cell in row) + " |"
            markdown_lines.append(row_text)

            # Add separator after first row (header)
            if i == 0:
                separator = "| " + " | ".join(["---"] * max_cols) + " |"
                markdown_lines.append(separator)

        result = "\n".join(markdown_lines)

        # Clean HTML artifacts from table content
        result = re.sub(r"<sup>(.*?)</sup>", r"\1", result)
        result = re.sub(r"<sub>(.*?)</sub>", r"\1", result)
        result = re.sub(r"\*([A-Za-z0-9\-]+)\*", r"\1", result)

        # Expand abbreviations
        abbreviation_map = {
            r"\bmo\b": "months",
            r"\bpts\b": "patients",
            r"\byrs\b": "years",
            r"\bvs\b": "versus",
            r"\bwks\b": "weeks",
        }

        for pattern, replacement in abbreviation_map.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def clean_section_text(self, text: str) -> str:
        """Clean residual artifacts from section content.

        Since DocStrange output is already clean, we only need to:
        - Remove bold formatting artifacts for consistency
        - Clean up any remaining clinical trial reference formatting
        - Normalize whitespace
        """
        if text is None:
            return ""
        cleaned = text.strip()

        # Remove bold formatting artifacts (**text**) for consistent markdown output
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)

        # Remove malformed clinical trial information patterns
        # (These can still appear in some conversions)
        patterns_to_remove = [
            r"\[Clinical trial infor\]\([^)]+\)\[mation: NCT\d+\.\]\([^)]+\)",
            r"\[Clinical trial\]\([^)]+\)\s*\[information: NCT\d+\.\]\([^)]+\)",
            r"\[Clinical\]\([^)]+\)\s*\[trial information: NCT\d+\.\]\([^)]+\)",
            r"\[Clinical trial information: NCT\d+\.\]\([^)]+\)",
            r"Clinical trial information: NCT\d+\.?",
            r"\(Clinical trial ID: NCT\d+\)",
            r"\[Clinical\]\([^)]+\)\s*trial information:\s*\[NCT\d+\.\]\([^)]+\)",
            r"\[NCT\d+\.\]\([^)]+\)",
            r"\[Clinical\]\([^)]+\)",
            r"Clinical trial\s*\[information:\]\([^)]+\)",
            r"\[([A-Z0-9\-]+\.?)\]\(http://clinicaltrials\.gov/show/[^)]+\)",
            r"trial information:\s*[A-Z0-9\-]+",
        ]

        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Remove duplicate trial IDs and final cleanup
        cleaned = re.sub(r"([A-Z0-9\-]+)\s+\1", r"\1", cleaned)
        cleaned = re.sub(r"\s*\[$", "", cleaned)
        cleaned = re.sub(r"^\]\s*", "", cleaned)
        cleaned = re.sub(r"^\*\*\s+(?!\w+:)", "", cleaned)
        cleaned = re.sub(r"\s*\*\*$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    async def parse_abstract(self, abstract_text: str) -> ParsedAbstract:
        """Parse a single ASCO abstract from raw text.

        Optimized for DocStrange output with pre-cleaning step.
        """
        parsed_data = {
            "id": "N/A",
            "title": "N/A",
            "authors_and_affiliations": "",
            "background": "",
            "methods": "",
            "results": "",
            "conclusions": "",
            "clinical_trial_info": "",
            "sponsor": "",
            "full_text_reference": "",
            "additional_content": "",
        }

        # Pre-cleaning: Remove PDF junk before parsing
        abstract_text = self.remove_pdf_artifacts(abstract_text)

        # Pass 1: Separate the header from the main body
        lines = abstract_text.strip().split("\n")
        header_lines = []
        body_lines = []
        header_ended = False

        # DocStrange output has bold section markers like **Background:**
        section_markers = [
            "background:",
            "methods:",
            "results:",
            "re-sults:",  # Variant with hyphen
            "conclusions:",
            "clinical trial information:",
            "full text reference:",
            "research sponsor:",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            lower_line = line.lower()
            if not header_ended:
                # If any section marker appears, switch to body
                # Use precise matching to avoid false matches (e.g., "trial results:" shouldn't match "results:")
                # Section markers should only match if they appear as actual section headers:
                # - At start of line (after optional markdown like ** or ##)
                # - In bold format like **Results:**
                # NOT in the middle of sentences like "trial results:"
                marker_positions = []
                for marker in section_markers:
                    # Pattern 1: Marker at start of line (after optional markdown like ** or ##)
                    # Examples: "**Results:**", "## Results:", "Results:"
                    pattern1 = r"^(?:\*{0,2}|#+\s*)" + re.escape(marker) + r"(?:\s|$)"
                    if re.match(pattern1, lower_line):
                        marker_positions.append(0)
                        continue

                    # Pattern 2: Marker in bold format anywhere in line
                    # Example: "Some text **Results:** more text"
                    pattern2 = r"\*\*" + re.escape(marker) + r"\*\*"
                    match2 = re.search(pattern2, lower_line)
                    if match2:
                        marker_positions.append(match2.start())
                        continue

                    # Pattern 3: Marker at start of line after whitespace (but not in middle of sentence)
                    # Only match if line starts with the marker (after trimming)
                    # This handles cases where there might be leading spaces
                    if lower_line.strip().startswith(marker):
                        # Make sure it's not part of a longer word
                        stripped = lower_line.strip()
                        if (
                            len(stripped) == len(marker)
                            or not stripped[len(marker) : len(marker) + 1].isalnum()
                        ):
                            marker_positions.append(lower_line.find(marker.strip()))

                if marker_positions:
                    header_ended = True
                    start_idx = min(pos for pos in marker_positions if pos != -1)

                    # Special case for full text reference + research sponsor
                    if (
                        "full, final text" in line
                        or "Journal of Clinical Oncology" in line
                    ) and "Research Sponsor:" in line:
                        body_lines.append(line)
                    else:
                        body_lines.append(line[start_idx:])
                    continue

                # Special case for LBA abstracts
                if "full, final text" in line or "meetings.asco.org" in line:
                    header_ended = True
                    body_lines.append(line)
                    continue

                header_lines.append(line)
            else:
                body_lines.append(line)

        # Pass 2: Parse the header for ID, Title, and Authors
        header_content = " ".join(header_lines)

        # Extract ASCO ID pattern (10000, 9501, TPS9585, LBA9503, etc.)
        id_pattern = r"\b(?:(?:TPS|LBA)\s*)?(?:100\d{2}|9[56]\d{2})\b"
        id_match = re.search(id_pattern, header_content, flags=re.IGNORECASE)
        if id_match:
            parsed_data["id"] = id_match.group(0)

        # Extract title
        session_keywords = [
            "poster session",
            "oral abstract session",
            "poster discussion",
            "session",
            "board #",
            "displayed in poster",
            "discussed in poster",
            "fri,",
            "sat,",
            "sun,",
        ]

        def is_session_line(line: str) -> bool:
            lower = line.lower()
            if re.match(r"^#*\s*(?:(?:TPS|LBA)\s*)?(?:100\d{2}|9[56]\d{2})\b", lower):
                return True
            return any(kw in lower for kw in session_keywords)

        header_lines_filtered = [
            line for line in header_lines if line and not is_session_line(line)
        ]

        # Extract title - try multiple strategies for DocStrange format
        title = None

        # Strategy 1: Look for markdown headers (# Title)
        for hdr_line in header_lines_filtered:
            if hdr_line.startswith("#"):
                title = hdr_line.lstrip("# ").strip()
                break

        def looks_like_author_line(line: str) -> bool:
            """Check if a line looks like an author/affiliation line."""
            line_lower = line.lower()
            if ";" in line:
                return True
            institutional_keywords = [
                "university",
                "hospital",
                "center",
                "centre",
                "institute",
                "department",
            ]
            keyword_count = sum(1 for kw in institutional_keywords if kw in line_lower)
            if keyword_count >= 2:
                return True
            if re.search(r"[A-Z][a-z]+\s+[A-Z][a-z]+.*;", line):
                return True
            return False

        # Strategy 2: Look for bold text (DocStrange format: **Title here**)
        # Take the first valid bold line — title always precedes author block in source.
        if not title:
            for hdr_line in header_lines_filtered:
                bold_match = re.match(r"^\*\*(.*?)\*\*$", hdr_line.strip())
                if bold_match:
                    bold_text = bold_match.group(1).strip()
                    if re.match(
                        r"^(?:(?:TPS|LBA)\s*)?(?:100\d{2}|9[56]\d{2})$", bold_text
                    ):
                        continue
                    if looks_like_author_line(bold_text):
                        continue
                    title = bold_text
                    break

        # Strategy 3: Look for plain text title (not bold/markdown)
        # This handles cases where title is plain text after session info
        if not title:
            for hdr_line in header_lines_filtered[:10]:  # Check first 10 lines
                line_stripped = hdr_line.strip()
                # Skip if it's a markdown header (already checked)
                if line_stripped.startswith("#"):
                    continue
                # Skip if it's bold (already checked)
                if line_stripped.startswith("**") and line_stripped.endswith("**"):
                    continue
                # Skip if it's too short
                if len(line_stripped) < 30:
                    continue
                # Skip if it looks like an author line
                if looks_like_author_line(line_stripped):
                    continue
                # Skip if it's just an abstract ID
                if re.match(
                    r"^(?:(?:TPS|LBA)\s*)?(?:100\d{2}|9[56]\d{2})$", line_stripped
                ):
                    continue
                # This looks like a title
                title = line_stripped
                break

        if title:
            # Remove any remaining bold markers
            title = re.sub(r"\*\*(.*?)\*\*", r"\1", title)
            parsed_data["title"] = self.clean_text(title).strip(" -–—")

        parsed_data["authors_and_affiliations"] = header_content

        # Pass 3: Parse the body using section splitting
        full_body_text = "\n".join(body_lines)

        # Extract tables - DocStrange provides both HTML and markdown tables
        # Look for HTML table tags or markdown pipe tables
        table_lines = []
        in_html_table = False

        for line in body_lines:
            # Check for HTML table markers
            if "<table>" in line.lower():
                in_html_table = True

            if in_html_table:
                table_lines.append(line)

            if "</table>" in line.lower():
                in_html_table = False
                continue

            # Also capture markdown pipe tables
            if (
                not in_html_table
                and line.strip().startswith("|")
                and "|" in line.strip()[1:]
            ):
                table_lines.append(line)

        if table_lines:
            table_content = "\n".join(table_lines).strip()
            parsed_data["additional_content"] = self.clean_table_content(table_content)

        # Extract research sponsor
        if "Research Sponsor:" in full_body_text:
            sponsor_match = re.search(
                r"Research Sponsor:\s*(.*?)(?:\s*$|\s*\n|\s*\|)",
                full_body_text,
                re.IGNORECASE | re.DOTALL,
            )
            if sponsor_match:
                sponsor_text = sponsor_match.group(1).strip()
                sponsor_text = re.sub(
                    r"\[Clinical.*", "", sponsor_text, flags=re.IGNORECASE
                )
                sponsor_text = re.sub(
                    r"NCT\d+.*", "", sponsor_text, flags=re.IGNORECASE
                )
                sponsor_text = sponsor_text.strip().rstrip(".")
                parsed_data["sponsor"] = sponsor_text

        # Extract sections
        section_keywords = [
            "background:",
            "methods:",
            "results:",
            "re-sults:",  # Variant with hyphen (e.g., "Re-sults:")
            "conclusions:",
            "clinical trial information:",
            "full text reference:",
        ]
        parts = re.split(
            f"({'|'.join(re.escape(k) for k in section_keywords)})",
            full_body_text,
            flags=re.IGNORECASE,
        )

        for i in range(1, len(parts), 2):
            key = parts[i].lower()
            content = parts[i + 1].strip()

            # Normalize "re-sults:" to "results:" for consistency
            if key == "re-sults:":
                key = "results:"

            if key == "background:":
                parsed_data["background"] = self.clean_section_text(content)
            elif key == "methods:":
                parsed_data["methods"] = self.clean_section_text(content)
            elif key == "results:":
                parsed_data["results"] = self.clean_section_text(content)
            elif key == "conclusions:":
                conclusions_text = content.strip()
                if "Research Sponsor:" in conclusions_text:
                    sponsor_pos = conclusions_text.find("Research Sponsor:")
                    conclusions_text = conclusions_text[:sponsor_pos].strip()
                parsed_data["conclusions"] = self.clean_section_text(conclusions_text)
            elif key == "clinical trial information:":
                # Extract NCT or other trial ID
                nct_match = re.search(r"(NCT\d+)", content, re.IGNORECASE)
                if nct_match:
                    parsed_data["clinical_trial_info"] = nct_match.group(1)
                else:
                    # Look for other trial ID formats
                    trial_patterns = [
                        r"(\d{4}-\d{6}-\d{2})",
                        r"(UMIN\d+)",
                        r"(ISRCTN\d+)",
                        r"(DRKS\d+)",
                        r"(ACTRN\d+)",
                    ]
                    for pattern in trial_patterns:
                        trial_match = re.search(pattern, content, re.IGNORECASE)
                        if trial_match:
                            parsed_data["clinical_trial_info"] = trial_match.group(1)
                            break
            elif key == "full text reference:":
                # Preserve original text format (don't clean it)
                full_text_ref = content.strip()
                # Remove "Research Sponsor:" if it appears in the same section
                if "Research Sponsor:" in full_text_ref:
                    sponsor_pos = full_text_ref.find("Research Sponsor:")
                    full_text_ref = full_text_ref[:sponsor_pos].strip().rstrip(" .")
                parsed_data["full_text_reference"] = full_text_ref

        # Fallback: Extract full text reference if not found as a section
        # (for cases where it appears without a section marker)
        if not parsed_data["full_text_reference"] and (
            "full, final text" in full_body_text
            or "Journal of Clinical Oncology" in full_body_text
            or "meetings.asco.org" in full_body_text
        ):
            # Try to find the full text reference line(s)
            # It typically appears before "Research Sponsor:" or at the end
            full_text_pattern = r"(The full, final text.*?)(?:Research Sponsor:|$)"
            full_text_match = re.search(
                full_text_pattern, full_body_text, re.IGNORECASE | re.DOTALL
            )
            if full_text_match:
                full_text_ref = full_text_match.group(1).strip()
                # Clean up any trailing punctuation/spaces but preserve the original format
                full_text_ref = full_text_ref.rstrip(" .")
                parsed_data["full_text_reference"] = full_text_ref
            else:
                # Fallback: look for lines containing the keywords
                for line in body_lines:
                    line_lower = line.lower()
                    if (
                        "full, final text" in line_lower
                        or "journal of clinical oncology" in line_lower
                    ):
                        # Extract up to "Research Sponsor:" if present
                        if "Research Sponsor:" in line:
                            sponsor_pos = line.find("Research Sponsor:")
                            full_text_ref = line[:sponsor_pos].strip().rstrip(" .")
                        else:
                            full_text_ref = line.strip().rstrip(" .")
                        parsed_data["full_text_reference"] = full_text_ref
                        break

        return ParsedAbstract(**parsed_data)

    async def format_to_markdown(
        self, parsed_abstract: ParsedAbstract, config: PostprocessingConfiguration
    ) -> str:
        """Format parsed abstract to structured markdown.

        Optimized for RAG by:
        - Excluding authors/affiliations (not needed for retrieval)
        - Using consistent section headers for optimal chunking
        - Keeping table data clean and structured
        """
        md_output = [
            f"### Abstract ID: {parsed_abstract.id}",
            "",
        ]

        # Title as a proper section for better RAG chunking
        if parsed_abstract.title and parsed_abstract.title != "N/A":
            md_output.append("#### Title:")
            md_output.append(f"{parsed_abstract.title}\n")

        # Main content sections with consistent headers for optimal chunking
        section_order: list[tuple[str, str]] = [
            ("Background", parsed_abstract.background),
            ("Methods", parsed_abstract.methods),
            ("Results", parsed_abstract.results),
            ("Conclusions", parsed_abstract.conclusions),
        ]

        for display_name, content in section_order:
            if content:
                md_output.append(f"#### {display_name}:")
                md_output.append(f"{self.clean_text(content)}\n")

        # Add tables as a separate section with proper header for chunking
        if parsed_abstract.additional_content:
            md_output.append("#### Table:")
            md_output.append(parsed_abstract.additional_content)
            md_output.append("")

        # Metadata sections with headers for better RAG retrieval
        if parsed_abstract.clinical_trial_info:
            md_output.append("#### Clinical Trial Information:")
            md_output.append(f"{parsed_abstract.clinical_trial_info}")
            md_output.append("")

        if parsed_abstract.sponsor:
            md_output.append("#### Research Sponsor:")
            md_output.append(f"{parsed_abstract.sponsor}")
            md_output.append("")

        if parsed_abstract.full_text_reference:
            md_output.append("#### Full Text Reference:")
            md_output.append(f"{parsed_abstract.full_text_reference}")
            md_output.append("")

        return "\n".join(md_output)

    async def validate_abstract(self, parsed_abstract: ParsedAbstract) -> list[str]:
        """Validate parsed abstract and return list of issues."""
        issues = []

        # Check for valid Abstract ID
        if not re.match(
            r"(?:(?:TPS|LBA)\s*)?(?:100\d{2}|9[56]\d{2})", parsed_abstract.id
        ):
            issues.append("Missing/invalid Abstract ID")

        # Check for title
        if parsed_abstract.title == "N/A" or not parsed_abstract.title.strip():
            issues.append("Missing Title")

        # Check if this is a TPS abstract (Trials in Progress)
        is_tps_abstract = "TPS" in parsed_abstract.id
        has_full_text_reference = bool(parsed_abstract.full_text_reference)

        # Only check for missing sections if not TPS and not full text reference
        if not has_full_text_reference and not is_tps_abstract:
            required_sections = ["background", "methods", "results", "conclusions"]
            for section in required_sections:
                content = getattr(parsed_abstract, section, "")
                if not content or content.strip() == "":
                    issues.append(f"Missing '{section.title()}' section")

        return issues
