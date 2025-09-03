"""ASCO abstract postprocessor implementation."""

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
        """Clean and normalize text content."""
        if not text:
            return ""
        text = re.sub(r"\\n", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def clean_table_content(self, table_text: str) -> str:
        """Clean and format table content to be LLM-friendly and RAG-optimized."""
        if not table_text or not table_text.strip():
            return table_text

        lines = table_text.split("\n")
        cleaned_lines = []
        table_rows = []

        for line in lines:
            if not line.strip():
                cleaned_lines.append(line)
                continue

            # Clean HTML artifacts first
            cleaned_line = line.replace(
                "<br>", "; "
            )  # Convert line breaks to semicolons for readability
            cleaned_line = re.sub(r"<br\s*/?>", "; ", cleaned_line)

            # Fix common table formatting issues
            cleaned_line = re.sub(r"\s+", " ", cleaned_line)  # Normalize whitespace
            cleaned_line = cleaned_line.strip()

            # If it's a table row, process it specially
            if cleaned_line.startswith("|") and cleaned_line.endswith("|"):
                # Split by pipes and clean each cell
                cells = cleaned_line.split("|")
                cleaned_cells = []
                for cell in cells:
                    cell = cell.strip()
                    # Remove extra spaces and normalize
                    cell = re.sub(r"\s+", " ", cell)
                    # Convert common abbreviations for clarity and RAG understanding
                    cell = cell.replace("mo", "months")
                    cell = cell.replace("pts", "patients")
                    cell = cell.replace("yrs", "years")
                    cell = cell.replace("vs", "versus")
                    cell = cell.replace("HR", "Hazard Ratio")
                    cell = cell.replace("CI", "Confidence Interval")
                    # Handle empty cells for better formatting
                    if not cell:
                        cell = "-"
                    cleaned_cells.append(cell)
                cleaned_line = "|".join(cleaned_cells)
                table_rows.append(cleaned_line)
            else:
                cleaned_lines.append(cleaned_line)

        # If we have table rows, format them with enhanced structure
        if table_rows:
            # Add a descriptive header for all tables with consistent naming
            if len(table_rows) > 2:  # Has header, separator, and data rows
                cleaned_lines.append("**Clinical Study Results Table:**")
                cleaned_lines.append("")

            cleaned_lines.extend(table_rows)

        return "\n".join(cleaned_lines)

    def clean_section_text(self, text: str) -> str:
        """Clean residual artifacts from section content."""
        if text is None:
            return ""
        cleaned = text.strip()

        # Remove bold formatting artifacts (**text**)
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)

        # Remove malformed clinical trial information patterns
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

        # Remove duplicate trial IDs and cleanup
        cleaned = re.sub(r"([A-Z0-9\-]+)\s+\1", r"\1", cleaned)
        cleaned = re.sub(r"\s*\[$", "", cleaned)
        cleaned = re.sub(r"^\]\s*", "", cleaned)
        cleaned = re.sub(r"^\*\*\s+(?!\w+:)", "", cleaned)
        cleaned = re.sub(r"\s*\*\*$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    async def parse_abstract(self, abstract_text: str) -> ParsedAbstract:
        """Parse a single ASCO abstract from raw text."""
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

        # Pass 1: Separate the header from the main body
        lines = abstract_text.strip().split("\n")
        header_lines = []
        body_lines = []
        header_ended = False
        section_markers = [
            "background:",
            "methods:",
            "results:",
            "conclusions:",
            "clinical trial information:",
            "research sponsor:",
        ]

        for line in lines:
            line = line.strip()
            if not line or "melanoma/skin cancers" in line.lower():
                continue

            lower_line = line.lower()
            if not header_ended:
                # If any section marker appears, switch to body
                marker_positions = [
                    lower_line.find(m) for m in section_markers if m in lower_line
                ]
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

        # Prefer the first markdown header among filtered lines
        title_from_hash = None
        for hdr_line in header_lines_filtered:
            if hdr_line.startswith("#"):
                title_from_hash = hdr_line.lstrip("# ").strip()
                break

        if title_from_hash:
            title_from_hash = re.sub(r"\*\*(.*?)\*\*", r"\1", title_from_hash)
            parsed_data["title"] = self.clean_text(title_from_hash).strip(" -–—")

        parsed_data["authors_and_affiliations"] = header_content

        # Pass 3: Parse the body using section splitting
        full_body_text = "\n".join(body_lines)

        # Extract tables
        table_lines = []
        for line in body_lines:
            if line.strip().startswith("|") and "|" in line.strip()[1:]:
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
            "conclusions:",
            "clinical trial information:",
        ]
        parts = re.split(
            f"({'|'.join(re.escape(k) for k in section_keywords)})",
            full_body_text,
            flags=re.IGNORECASE,
        )

        for i in range(1, len(parts), 2):
            key = parts[i].lower()
            content = parts[i + 1].strip()

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

        # Check for full text reference
        if (
            "full, final text" in full_body_text
            or "Journal of Clinical Oncology" in full_body_text
            or "meetings.asco.org" in full_body_text
        ):
            parsed_data["full_text_reference"] = (
                "The full, final text of this abstract will be available at "
                "meetings.asco.org on the day of presentation and in the online "
                "supplement to the Journal of Clinical Oncology."
            )

        return ParsedAbstract(**parsed_data)

    async def format_to_markdown(
        self, parsed_abstract: ParsedAbstract, config: PostprocessingConfiguration
    ) -> str:
        """Format parsed abstract to structured markdown."""
        md_output = [
            f"### Abstract ID: {parsed_abstract.id}",
            f"**Title:** {parsed_abstract.title}\n",
        ]

        if not config.exclude_authors and parsed_abstract.authors_and_affiliations:
            md_output.append("#### Authors and Affiliations:")
            md_output.append(
                f"{self.clean_text(parsed_abstract.authors_and_affiliations)}\n"
            )

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
            md_output.append("#### Study Results:")
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
