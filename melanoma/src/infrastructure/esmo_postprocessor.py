"""ESMO abstract postprocessor implementation."""

import re

from domain.interfaces import PostprocessorInterface
from domain.models import ConferenceType, ParsedAbstract, PostprocessingConfiguration


class ESMOPostprocessor(PostprocessorInterface):
    """Postprocessor for ESMO conference abstracts."""

    def __init__(self):
        """Initialize the ESMO postprocessor."""
        self.conference_type = ConferenceType.ESMO

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
            cleaned_line = line.replace("<br>", "; ")
            cleaned_line = re.sub(r"<br\s*/?>", "; ", cleaned_line)

            # Fix common table formatting issues
            cleaned_line = re.sub(r"\s+", " ", cleaned_line)
            cleaned_line = cleaned_line.strip()

            # If it's a table row, process it specially
            if cleaned_line.startswith("|") and cleaned_line.endswith("|"):
                cells = cleaned_line.split("|")
                cleaned_cells = []
                for cell in cells:
                    cell = cell.strip()
                    cell = re.sub(r"\s+", " ", cell)
                    # Convert common abbreviations for clarity and RAG understanding
                    cell = cell.replace("mo", "months")
                    cell = cell.replace("pts", "patients")
                    cell = cell.replace("yrs", "years")
                    cell = cell.replace("vs", "versus")
                    cell = cell.replace("HR", "Hazard Ratio")
                    cell = cell.replace("CI", "Confidence Interval")
                    # Replace long runs of ! with NA (ESMO-specific OCR issue)
                    if "!!" in cell:
                        cell = re.sub(r"!{5,}", "NA", cell)
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
            if len(table_rows) > 2:
                cleaned_lines.append("**Clinical Study Results Table:**")
                cleaned_lines.append("")

            cleaned_lines.extend(table_rows)

        return "\n".join(cleaned_lines)

    def clean_section_text(self, text: str) -> str:
        """Clean residual artifacts from section content."""
        if text is None:
            return ""
        cleaned = text.strip()

        # Remove disclosure information patterns
        disclosure_patterns = [
            r"Disclosure:.*?(?=\n\n|\Z)",
            r"Financial Interests.*?(?=\n\n|\Z)",
            r"Non-Financial Interests.*?(?=\n\n|\Z)",
            r"All other authors have declared no conflicts of interest.*?(?=\n\n|\Z)",
            r"https://doi\.org/.*?(?=\n\n|\Z)",
            r"Editorial acknowledgement:.*?(?=\n\n|\Z)",
            r"Honoraria.*?(?=\n\n|\Z)",
            r"Advisory/Consultancy.*?(?=\n\n|\Z)",
            r"Research grant/Funding.*?(?=\n\n|\Z)",
            r"Travel/Accommodation/Expenses.*?(?=\n\n|\Z)",
            r"Shareholder/Stockholder/Stock options.*?(?=\n\n|\Z)",
            r"Speaker Bureau/Expert testimony.*?(?=\n\n|\Z)",
            r"Leadership role.*?(?=\n\n|\Z)",
            r"Licensing/Royalties.*?(?=\n\n|\Z)",
        ]

        for pattern in disclosure_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL | re.IGNORECASE)

        # Remove author affiliation information
        cleaned = re.sub(r"\d+\s*[A-Z][^;]+;\s*(?:\d+\s*[A-Z][^;]+;\s*)*", "", cleaned)

        # Remove span anchors and page references
        cleaned = re.sub(r'<span id="page-[^>]+"></span>', "", cleaned)
        cleaned = re.sub(r"!\[\]\([^)]+\)", "", cleaned)
        cleaned = re.sub(r"\{\d+\}[-]+", "", cleaned)
        cleaned = re.sub(r"\[(\d+)\]\(#page-[^)]+\)", r"", cleaned)
        cleaned = re.sub(r"#\s*$", "", cleaned)

        # Remove author name patterns
        cleaned = re.sub(r"[A-Z]\.[A-Z]\s+[A-Z][a-z]+\[[^\]]+\]", "", cleaned)
        cleaned = re.sub(
            r"^[A-Z]\.[A-Z]\s+[A-Z][a-z]+\[\d+\].*?(?=\n|$)",
            "",
            cleaned,
            flags=re.MULTILINE,
        )

        # Clean up extra whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def apply_foundational_cleanup(self, content: str) -> str:
        """Apply foundational cleanup to content."""
        # Remove page separators
        content = re.sub(r"(?m)^\{\d+\}-+\s*$", "", content)
        # Strip simple bold tags that leak from HTML
        content = content.replace("<b>", "").replace("</b>", "")
        return content

    def apply_content_normalization(self, content: str) -> str:
        """Apply content and OCR normalization."""
        # Global replacement: ¼ → =
        content = content.replace("¼", "=")

        # Fix ranges inside parentheses, avoid scientific notation
        parens_pattern = re.compile(r"\(([^)]*)\)")
        range_pattern = re.compile(
            r"(?i)(\b\d+(?:\.\d+)?)\s*e\s*(\d+(?:\.\d+)?|NA)\b(?!\s*[+-]?\d)"
        )

        def fix_ranges_in_parens(text: str) -> str:
            def repl(match):
                inner = match.group(1)
                fixed = range_pattern.sub(r"\1-\2", inner)
                return f"({fixed})"

            return parens_pattern.sub(repl, text)

        content = fix_ranges_in_parens(content)

        # Normalize counts n/N
        content = re.sub(r"(?i)\b([nN])\s*(?:\[|=)\s*(\d+)\b", r"\1 = \2", content)

        return content

    def apply_table_refinements(self, content: str) -> str:
        """Apply table-specific refinements."""

        def fix_table_line(line: str) -> str:
            line = re.sub(r"(?<=\|)([^|\n]*!{5,}[^|\n]*)(?=\|)", " NA ", line)
            line = re.sub(r"(<br\s*/?>)+", "; ", line, flags=re.IGNORECASE)
            line = line.replace("<b>", "").replace("</b>", "")
            line = re.sub(r"\s*(\|\s*)+$", "|", line)
            return line

        lines = content.splitlines()
        processed_lines = []

        for line in lines:
            if line.lstrip().startswith("|"):
                processed_lines.append(fix_table_line(line))
            else:
                processed_lines.append(line)

        return "\n".join(processed_lines)

    async def parse_abstract(self, abstract_text: str) -> ParsedAbstract:
        """Parse a single ESMO abstract from raw text."""
        parsed_data = {
            "id": "N/A",
            "title": "N/A",
            "authors_and_affiliations": "",
            "background": "",
            "trial_design": "",
            "methods": "",
            "results": "",
            "conclusions": "",
            "clinical_trial_info": "",
            "legal_entity": "",
            "funding": "",
            "doi": "",
        }

        # Apply preprocessing steps
        abstract_text = self.apply_foundational_cleanup(abstract_text)
        abstract_text = self.apply_content_normalization(abstract_text)
        abstract_text = self.apply_table_refinements(abstract_text)

        # Extract DOI link first
        doi_match = re.search(r"https://doi\.org/[^\s\n\)]+", abstract_text)
        if doi_match:
            parsed_data["doi"] = doi_match.group(0)

        # Remove disclosure sections
        disclosure_start = abstract_text.find("Financial Interests")
        if disclosure_start == -1:
            disclosure_start = abstract_text.find(
                "All other authors have declared no conflicts"
            )
        if disclosure_start == -1:
            disclosure_start = abstract_text.find("Disclosure:")

        if disclosure_start != -1:
            remaining_text = abstract_text[disclosure_start:]
            doi_match = re.search(r"https://doi\.org/[^\s]+", remaining_text)
            if doi_match:
                disclosure_end = disclosure_start + doi_match.end()
                abstract_text = (
                    abstract_text[:disclosure_start] + abstract_text[disclosure_end:]
                )
            else:
                abstract_text = abstract_text[:disclosure_start]

        # Pass 1: Separate header from body
        lines = abstract_text.strip().split("\n")
        header_lines: list[str] = []
        body_lines: list[str] = []
        header_ended = False
        section_markers = [
            "background:",
            "trial design:",
            "methods:",
            "results:",
            "conclusions:",
            "clinical trial identification:",
            "legal entity responsible for the study:",
            "funding:",
        ]

        for line in lines:
            line = line.strip()
            if not line or "melanoma and other skin tumours" in line.lower():
                continue

            # Skip image references and page separators
            if line.startswith("![](") or re.match(r"^\{\d+\}[-]+", line):
                continue

            # Stop processing if we hit another abstract
            if (
                line.startswith("# ")
                and re.search(r"\d{3,5}[A-Z]*", line)
                and len(header_lines) > 0
            ):
                break

            lower_line = line.lower()
            if not header_ended:
                marker_positions = [
                    lower_line.find(m) for m in section_markers if m in lower_line
                ]
                if marker_positions:
                    header_ended = True
                    start_idx = min(pos for pos in marker_positions if pos != -1)
                    body_lines.append(line[start_idx:])
                    continue

                header_lines.append(line)
            else:
                if line.startswith("# ") and re.search(r"\d{3,5}[A-Z]*", line):
                    break
                body_lines.append(line)

        # Pass 2: Parse header for ID, Title
        header_content = " ".join(header_lines)

        # ESMO ID pattern (1076O, 784O, etc.)
        id_pattern = r"\b(1\d{3}(?:[A-Z]+|TiP)|[78]\d{2}(?:O|MO|P|TiP))\b"
        id_match = re.search(id_pattern, header_content)
        if id_match:
            parsed_data["id"] = id_match.group(1)

        # If no ID found in header, check first line
        if parsed_data["id"] == "N/A":
            first_line = abstract_text.strip().split("\n")[0]
            id_match = re.match(r"^(1\d{3}(?:[A-Z]+|TiP))\s", first_line)
            if id_match:
                parsed_data["id"] = id_match.group(1)

        # Find title from header lines
        title_from_hash = None
        for hdr_line in header_lines:
            if hdr_line.startswith("#") and not hdr_line.upper().startswith(
                "# MELANOMA"
            ):
                title_candidate = hdr_line.lstrip("# ").strip()
                title_candidate = re.sub(
                    r"^(1\d{3}(?:[A-Z]+|TiP)|[78]\d{2}(?:O|MO|P|TiP))\s+",
                    "",
                    title_candidate,
                )
                if len(title_candidate) > 10:
                    title_from_hash = title_candidate
                    break

        if title_from_hash:
            parsed_data["title"] = self.clean_text(title_from_hash)
        else:
            # Try to extract from first line
            first_line = abstract_text.strip().split("\n")[0]
            title_match = re.match(
                r"^(1\d{3}(?:[A-Z]+|TiP)|[78]\d{2}(?:O|MO|P|TiP))\s+(.+)", first_line
            )
            if title_match:
                parsed_data["title"] = self.clean_text(title_match.group(2))
            elif "background:" in abstract_text.lower():
                parsed_data[
                    "title"
                ] = "Abstract content available (title missing in source)"

        # Pass 3: Parse body sections
        full_body_text = "\n".join(body_lines)

        # Extract tables separately
        table_lines = []
        cleaned_body_lines = []
        for line in body_lines:
            if line.strip().startswith("|") and "|" in line.strip()[1:]:
                table_lines.append(line)
            else:
                cleaned_body_lines.append(line)

        if table_lines:
            table_content = "\n".join(table_lines).strip()
            parsed_data["additional_content"] = self.clean_table_content(table_content)

        # Split body by section keywords
        section_keywords = [
            "background:",
            "trial design:",
            "methods:",
            "results:",
            "conclusions:",
            "clinical trial identification:",
            "legal entity responsible for the study:",
            "funding:",
        ]

        full_body_text = "\n".join(cleaned_body_lines)
        parts = re.split(
            f"({'|'.join(re.escape(k) for k in section_keywords)})",
            full_body_text,
            flags=re.IGNORECASE,
        )

        for i in range(1, len(parts), 2):
            if i + 1 >= len(parts):
                break

            key = parts[i].lower()
            content = parts[i + 1].strip()

            if key == "background:":
                parsed_data["background"] = self.clean_section_text(content)
            elif key == "trial design:":
                parsed_data["trial_design"] = self.clean_section_text(content)
            elif key == "methods:":
                parsed_data["methods"] = self.clean_section_text(content)
            elif key == "results:":
                parsed_data["results"] = self.clean_section_text(content)
            elif key == "conclusions:":
                parsed_data["conclusions"] = self.clean_section_text(content)
            elif key == "clinical trial identification:":
                trial_match = re.search(
                    r"(NCT\d+|EudraCT\s*\d{4}-\d{6}-\d{2})", content, re.IGNORECASE
                )
                if trial_match:
                    parsed_data["clinical_trial_info"] = trial_match.group(1)
                else:
                    parsed_data["clinical_trial_info"] = self.clean_section_text(
                        content
                    )
            elif key == "legal entity responsible for the study:":
                parsed_data["legal_entity"] = self.clean_section_text(content)
            elif key == "funding:":
                parsed_data["funding"] = self.clean_section_text(content)

        # Additional pass: look for embedded trial numbers
        if not parsed_data.get("clinical_trial_info"):
            trial_patterns = [
                r"(NCT\d+)",
                r"(EudraCT\s*\d{4}-\d{6}-\d{2})",
                r"(\d{4}-\d{6}-\d{2})",
                r"(ISRCTN\d+)",
                r"(DRKS\d+)",
            ]

            for pattern in trial_patterns:
                trial_match = re.search(pattern, full_body_text, re.IGNORECASE)
                if trial_match:
                    parsed_data["clinical_trial_info"] = trial_match.group(1)
                    break

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
            ("Trial Design", parsed_abstract.trial_design),
            ("Methods", parsed_abstract.methods),
            ("Results", parsed_abstract.results),
            ("Conclusions", parsed_abstract.conclusions),
        ]

        for display_name, content in section_order:
            if content:
                md_output.append(f"#### {display_name}:")
                md_output.append(f"{self.clean_text(content)}\n")

        # Add tables as a separate section with proper header for chunking
        if (
            hasattr(parsed_abstract, "additional_content")
            and parsed_abstract.additional_content
        ):
            md_output.append("#### Study Results:")
            md_output.append(parsed_abstract.additional_content)
            md_output.append("")

        # Metadata sections with headers for better RAG retrieval
        if parsed_abstract.clinical_trial_info:
            md_output.append("#### Clinical Trial Identification:")
            md_output.append(f"{parsed_abstract.clinical_trial_info}")
            md_output.append("")

        if parsed_abstract.legal_entity:
            md_output.append("#### Legal Entity Responsible for Study:")
            md_output.append(f"{parsed_abstract.legal_entity}")
            md_output.append("")

        if parsed_abstract.funding:
            md_output.append("#### Funding:")
            md_output.append(f"{parsed_abstract.funding}")
            md_output.append("")

        if parsed_abstract.doi:
            md_output.append("#### DOI:")
            md_output.append(f"{parsed_abstract.doi}")
            md_output.append("")

        return "\n".join(md_output)

    async def validate_abstract(self, parsed_abstract: ParsedAbstract) -> list[str]:
        """Validate parsed abstract and return list of issues."""
        issues = []

        # Check for valid ESMO Abstract ID
        if (
            not re.match(
                r"1\d{3}(?:[A-Z]+|TiP)|[78]\d{2}(?:O|MO|P|TiP)", parsed_abstract.id
            )
            and parsed_abstract.id != "N/A"
        ):
            issues.append("Missing/invalid Abstract ID")

        # Check for title - allow N/A if abstract has substantial content
        has_na_title = (
            parsed_abstract.title == "N/A" or not parsed_abstract.title.strip()
        )
        has_content_sections = any(
            [
                parsed_abstract.background,
                parsed_abstract.methods,
                parsed_abstract.results,
                parsed_abstract.conclusions,
            ]
        )

        if has_na_title and not has_content_sections:
            issues.append("Missing Title and Content")

        # Check for required sections (skip for TiP abstracts)
        is_tip_abstract = "TiP" in parsed_abstract.id
        if not is_tip_abstract:
            required_sections = ["background", "methods", "results", "conclusions"]
            for section in required_sections:
                content = getattr(parsed_abstract, section, "")
                if not content or content.strip() == "":
                    issues.append(f"Missing '{section.title()}' section")

        return issues
