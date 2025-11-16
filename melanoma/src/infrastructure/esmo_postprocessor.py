"""
Simplified ESMO abstract postprocessor, optimized for clean input from 'marker'.

MODIFIED to meet user-specific section requirements:
1.  Removes 'Authors and Affiliations' from the final output.
2.  Extracts Markdown tables from the body to present them under a
    dedicated '#### Table:' heading.
3.  Specifically extracts 'Editorial acknowledgement' as a separate field
    while still removing all other 'Disclosure' information.
"""

import re

from domain.interfaces import PostprocessorInterface
from domain.models import ConferenceType, ParsedAbstract, PostprocessingConfiguration

# Expected ESMO 2020 abstract IDs in order (based on DOI sequence)
ESMO_2020_EXPECTED_IDS = [
    '1076O', '1077MO', '1078MO', '1079MO', '1080MO', '1081MO', '1082MO', '1083MO',
    '1084P', '1085P', '1086P', '1087P', '1088P', '1089P', '1090P', '1091P', '1092P', '1093P',
    '1094P', '1095P', '1096P', '1097P', '1098P', '1100P', '1101P', '1102P', '1103P', '1104P',
    '1105P', '1106P', '1107P', '1108P', '1109P', '1110P', '1111P', '1112P', '1113P', '1114P',
    '1115P', '1116P', '1117P', '1118P', '1119P', '1120P', '1121P', '1122P', '1123P', '1124P',
    '1125P', '1126P', '1127P', '1128P', '1129P', '1130P', '1131P', '1132P', '1133P', '1134P',
    '1135P', '1136P', '1137P', '1138P', '1139P', '1140P', '1141P', '1142P', '1143P', '1144P',
    '1145P', '1146P', '1147P', '1148P', '1149P', '1150P', '1151P', '1152P', '1153TiP', '1154TiP', '1155TiP'
]

# Expected ESMO 2021 abstract IDs in order (based on DOI sequence)
ESMO_2021_EXPECTED_IDS = [
    '1036O', '1037O', '1040O', '1038MO', '1039MO', '1041MO', '1042P', '1043P', '1044P', '1045P',
    '1046P', '1047P', '1048P', '1049P', '1050P', '1051P', '1052P', '1053P', '1054P', '1055P',
    '1056P', '1057P', '1058P', '1059P', '1060P', '1061P', '1062P', '1063P', '1064P', '1065P',
    '1066P', '1067P', '1068P', '1069P', '1070P', '1071P', '1072P', '1073P', '1074P', '1075P',
    '1076P', '1077P', '1078P', '1079P', '1080P', '1081P', '1082P', '1083P', '1084P', '1085P',
    '1086P', '1087P', '1088P', '1089TiP', '1090TiP', '1091TiP', '1092TiP', '1093TiP', '1094TiP', '1095TiP'
]

# Expected ESMO 2023 abstract IDs in order
ESMO_2023_EXPECTED_IDS = [
    '1081O', '1082O', '1083MO', '1084MO', '1085O', '1086MO', '1087MO', '1088MO', '1089P', '1090P',
    '1091P', '1092P', '1093P', '1094P', '1095P', '1096P', '1097P', '1098P', '1099P', '1100P',
    '1101P', '1102P', '1103P', '1104P', '1105P', '1106P', '1107P', '1108P', '1109P', '1110P',
    '1111P', '1112P', '1113P', '1114P', '1115P', '1116P', '1117P', '1118P', '1119P', '1120P',
    '1121P', '1122P', '1123P', '1124P', '1125P', '1126P', '1127P', '1128P', '1129P', '1130P',
    '1131P', '1132P', '1133P', '1134P', '1135P', '1136P', '1137P', '1138P', '1139P', '1140P',
    '1141P', '1142P', '1143P', '1144P', '1145P', '1146P', '1147P', '1148P', '1149P', '1150P',
    '1151P', '1152P', '1153P', '1154P', '1155P', '1156P', '1157P', '1158P', '1159P', '1160P',
    '1161P', '1162P', '1163P', '1164P', '1165P', '1166P', '1167P', '1168P', '1169P', '1170P',
    '1171P', '1172P', '1173P', '1174P', '1175P', '1176P', '1177P', '1178P', '1179P', '1180TiP', '1181TiP'
]

# Expected ESMO 2022 abstract IDs in order
ESMO_2022_EXPECTED_IDS = [
    '784O', '785O', '786O', '787O', '788O', '789O', '790MO', '791MO', '792MO', '793P',
    '794P', '795P', '796P', '797P', '798P', '799P', '800P', '801P', '802P', '803P',
    '804P', '805P', '806P', '807P', '808P', '809P', '810P', '811P', '812P', '813P',
    '814P', '815P', '816P', '817P', '818P', '819P', '820P', '821P', '822P', '823P',
    '824P', '825P', '826P', '827P', '828P', '829P', '830P', '831P', '832P', '833P',
    '834P', '835P', '836P', '837P', '838P', '839P', '840P', '841P', '842P', '843P',
    '844P', '845P', '846P', '847P', '848P', '849P', '850P', '851P', '852P', '853P',
    '854P', '855P', '856P', '857P', '858P', '859P', '860P', '861P', '862P', '863P',
    '864P', '865P', '866P', '867P', '868P', '869P', '870P', '871P', '872P', '873P',
    '874P', '875P', '876P', '877P', '878P', '879P', '880P', '881TiP', '882TiP', '883TiP',
    '884TiP', '885TiP', '886TiP'
]

# Expected ESMO 2024 abstract IDs in order
ESMO_2024_EXPECTED_IDS = [
    '1076O', '1077MO', '1078MO', '1079MO', '1080MO', '1081MO', '1082O', '1083P', '1084P', '1085P',
    '1086P', '1087P', '1088P', '1089P', '1090P', '1091P', '1092P', '1093P', '1094P', '1095P',
    '1096P', '1097P', '1098P', '1099P', '1100P', '1101P', '1102P', '1103P', '1104P', '1105P',
    '1106P', '1107P', '1108P', '1109P', '1110P', '1111P', '1112P', '1113P', '1114P', '1115P',
    '1116P', '1117P', '1118P', '1119P', '1120P', '1121P', '1122P', '1123P', '1124P', '1125P',
    '1126P', '1127P', '1128P', '1129P', '1130P', '1131P', '1132P', '1133P', '1134P', '1135P',
    '1136P', '1137P', '1138P', '1139TiP', '1140TiP'
]


class ESMOPostprocessor(PostprocessorInterface):
    """Postprocessor for ESMO conference abstracts."""

    def __init__(self):
        """Initialize the ESMO postprocessor."""
        self.conference_type = ConferenceType.ESMO

    def get_conference_type(self) -> ConferenceType:
        """Get the conference type this processor handles."""
        return self.conference_type

    def clean_text(self, text: str) -> str:
        """Clean and normalize text content, collapsing whitespace."""
        if not text:
            return ""
        text = re.sub(r"\\n", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _normalize_latex_symbols(self, text: str) -> str:
        """
        Normalize LaTeX math symbols to Unicode for better LLM/RAG compatibility.
        
        Converts LaTeX math notation like $\\geq$, $\\leq$, $\\pm$ to Unicode symbols
        like ≥, ≤, ± that are better understood by LLMs and RAG systems.
        """
        if not text:
            return text
        
        cleaned = text
        
        # Handle superscripts: $BRAF^{V600}$ -> BRAF^V600
        cleaned = re.sub(r'\$([A-Za-z0-9]+)\^\{([^}]+)\}\$', r'\1^\2', cleaned)
        # Handle standalone superscripts: $^{...}$
        cleaned = re.sub(r'\$\^\{([^}]+)\}\$', r'^\1', cleaned)
        
        # Handle inline math with numbers: $\geq 1$ -> ≥1, $\leq 1$ -> ≤1
        cleaned = re.sub(r'\$\\geq\s*(\d+)\$', r'≥\1', cleaned)
        cleaned = re.sub(r'\$\\leq\s*(\d+)\$', r'≤\1', cleaned)
        
        # Handle \geq and \leq with negative space: $\geq \! 1$ -> ≥1, $\leq \! 10$ -> ≤10
        cleaned = re.sub(r'\$\\geq\s*\\!\s*(\d+)\$', r'≥\1', cleaned)
        cleaned = re.sub(r'\$\\leq\s*\\!\s*(\d+)', r'≤\1', cleaned)
        
        # Handle LaTeX math in expressions: $-13.8 \pm 1.7$ -> -13.8 ± 1.7
        # Match negative numbers, decimals, and LaTeX symbols together
        cleaned = re.sub(r'\$(-?\d+\.?\d*)\s*\\pm\s*(\d+\.?\d*)\$', r'\1 ± \2', cleaned)
        cleaned = re.sub(r'\$(-?\d+\.?\d*)\s*\\pm\s*(\d+\.?\d*)\s*\$', r'\1 ± \2', cleaned)  # Trailing space variant
        
        # Handle common LaTeX math symbols (standalone)
        cleaned = re.sub(r'\$\\geq\$', '≥', cleaned)
        cleaned = re.sub(r'\$\\leq\$', '≤', cleaned)
        cleaned = re.sub(r'\$\\pm\$', '±', cleaned)
        cleaned = re.sub(r'\$\\times\$', '×', cleaned)
        cleaned = re.sub(r'\$\\div\$', '÷', cleaned)
        cleaned = re.sub(r'\$\\alpha\$', 'α', cleaned)
        cleaned = re.sub(r'\$\\beta\$', 'β', cleaned)
        cleaned = re.sub(r'\$\\gamma\$', 'γ', cleaned)
        cleaned = re.sub(r'\$\\delta\$', 'δ', cleaned)
        cleaned = re.sub(r'\$\\sim\$', '~', cleaned)
        cleaned = re.sub(r'\$\\approx\$', '≈', cleaned)
        cleaned = re.sub(r'\$\\neq\$', '≠', cleaned)
        
        # Clean up any remaining standalone $ delimiters (from malformed LaTeX)
        cleaned = re.sub(r'\$\s*\$', '', cleaned)  # Empty $...$
        cleaned = re.sub(r'\$\s+', ' ', cleaned)  # $ followed by space
        cleaned = re.sub(r'\s+\$', ' ', cleaned)  # space followed by $
        
        return cleaned

    def clean_section_text(self, text: str) -> str:
        """
        Clean residual artifacts from section content.
        Preserves newlines for tables.
        """
        if text is None:
            return ""
        cleaned = text.strip()

        # Remove disclosure information patterns
        # **MODIFIED**: Removed 'Editorial acknowledgement' from this list
        disclosure_patterns = [
            r"Disclosure:.*?(?=\n\n|\Z)",
            r"Financial Interests.*?(?=\n\n|\Z)",
            r"Non-Financial Interests.*?(?=\n\n|\Z)",
            r"All other authors have declared no conflicts of interest.*?(?=\n\n|\Z)",
            r"https://doi\.org/.*?(?=\n\n|\Z)",
            # r"Editorial acknowledgement:.*?(?=\n\n|\Z)", # <-- REMOVED
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

        # Remove author affiliation information (less aggressive)
        cleaned = re.sub(r"<sup>\d+</sup>", "", cleaned)  # Clean up <sup> tags

        # Remove markdown formatting artifacts at start/end while preserving intentional formatting
        # Remove leading artifacts: * , ** (but preserve *word*, **word**)
        # Pattern: * or ** followed by space at start (artifact)
        # Only remove if it's followed by space (artifact), not if it's part of *word* formatting
        cleaned = re.sub(r'^(\*\*?)\s+', '', cleaned)
        # Pattern: # at start ONLY if it's a standalone line or followed by space (artifact)
        # Don't remove # if it's part of actual content (shouldn't happen, but be safe)
        # Only remove if it's at the very start and looks like a heading artifact
        cleaned = re.sub(r'^#+\s*$', '', cleaned, flags=re.MULTILINE)  # Standalone # lines
        cleaned = re.sub(r'^#+\s+', '', cleaned)  # # followed by space at start
        
        # Remove trailing artifacts: standalone * or ** or # at end
        # Remove trailing # (artifact) - only if it's standalone
        cleaned = re.sub(r'#+\s*$', '', cleaned)
        # Remove trailing * or ** if preceded by space (artifact)
        cleaned = re.sub(r'\s+(\*\*?)\s*$', '', cleaned)
        # Remove standalone * or ** on their own line
        cleaned = re.sub(r'^(\*\*?)\s*$', '', cleaned, flags=re.MULTILINE)

        # Remove span anchors, image links, and page references from marker
        cleaned = re.sub(r'<span id="page-[^>]+"></span>', "", cleaned)
        cleaned = re.sub(r"!\[\]\([^)]+\)", "", cleaned)
        cleaned = re.sub(r"\[(\d+)\]\(#page-[^)]+\)", r"", cleaned)

        # Remove footer noise (both standalone lines and inline)
        # Standalone lines
        cleaned = re.sub(r"(?m)^\s*S\d+\s*$", "", cleaned)
        cleaned = re.sub(r"(?m)^\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*$", "", cleaned)
        # Inline patterns (embedded in text)
        cleaned = re.sub(r"\s*\*\*S\d+\*\*\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*", " ", cleaned)
        cleaned = re.sub(r"\s*\*\*S\d+\*\*\s*", " ", cleaned)  # Just the S number part
        cleaned = re.sub(r"\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*", " ", cleaned)  # Just the volume part

        # Normalize LaTeX math symbols to Unicode for better LLM/RAG compatibility
        cleaned = self._normalize_latex_symbols(cleaned)
        
        # Remove LaTeX formatting commands (\bf, \it, \bfseries, etc.)
        # Handle patterns like: {\bf text} -> text, {\it text} -> text
        cleaned = re.sub(r'\\bf\s*', '', cleaned)  # Remove \bf
        cleaned = re.sub(r'\\it\s*', '', cleaned)  # Remove \it
        cleaned = re.sub(r'\\bfseries\s*', '', cleaned)  # Remove \bfseries
        cleaned = re.sub(r'\\itshape\s*', '', cleaned)  # Remove \itshape
        cleaned = re.sub(r'\\rm\s*', '', cleaned)  # Remove \rm (roman)
        cleaned = re.sub(r'\\em\s*', '', cleaned)  # Remove \em (emphasis)
        
        # Remove LaTeX artifacts and incomplete formatting
        # Remove patterns like: \*% (95% CI) <sup>†</sup>n (%) {\bf
        cleaned = re.sub(r'\\\*%[^.]*?\{\\bf\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\\\*%[^.]*?\{\\bf\s*', '', cleaned)
        
        # Remove LaTeX grouping braces, but preserve content
        # Handle nested braces: {text} -> text
        # Use iterative approach to handle nested braces
        max_iterations = 10
        for _ in range(max_iterations):
            new_cleaned = re.sub(r'\{([^{}]*)\}', r'\1', cleaned)
            if new_cleaned == cleaned:
                break
            cleaned = new_cleaned
        
        # Remove any remaining standalone braces (orphaned opening/closing braces)
        cleaned = re.sub(r'^\s*[{}]\s*', '', cleaned)  # Leading braces
        cleaned = re.sub(r'\s*[{}]\s*$', '', cleaned)  # Trailing braces
        cleaned = re.sub(r'\s+[{}]\s+', ' ', cleaned)  # Standalone braces with spaces
        
        # Remove escaped spaces and other LaTeX escapes
        cleaned = re.sub(r'\\ ', ' ', cleaned)  # Escaped space -> space
        cleaned = re.sub(r'\\$', '', cleaned)  # Escaped $ -> remove
        
        # Remove standalone $ delimiters (math mode)
        cleaned = re.sub(r'\$', '', cleaned)
        
        # Remove trailing LaTeX artifacts at end of sentences/sections
        # Patterns like: \*% (95% CI) <sup>†</sup>n (%) {\bf
        cleaned = re.sub(r'\s*\\\*%[^.]*?\{\\bf\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\s*\\\*%[^.]*?$', '', cleaned, flags=re.MULTILINE)
        
        # Clean up extra spaces created by removing LaTeX commands
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Clean up whitespace while preserving newlines for tables.
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"(\n\s*){3,}", "\n\n", cleaned)
        lines = [line.strip() for line in cleaned.split('\n')]
        cleaned_lines = [line for line in lines if line.strip() != "#"]
        
        cleaned = "\n".join(cleaned_lines).strip()

        return cleaned

    def apply_foundational_cleanup(self, content: str) -> str:
        """Apply foundational cleanup to content."""
        content = re.sub(r"(?m)^\{\d+\}-+\s*$", "", content)
        content = content.replace("<b>", "").replace("</b>", "")
        content = re.sub(r"!\[\]\([^)]+\)\n*", "", content)
        content = re.sub(r'<span id="[^>]+"></span>\n*', "", content)
        return content

    def apply_content_normalization(self, content: str) -> str:
        """Apply content and OCR normalization."""
        content = content.replace("¼", "=")
        content = re.sub(r"(?i)\b([nN])\s*(?:\[|=)\s*(\d+)\b", r"\1 = \2", content)
        # Fix OCR error: "e" in numeric ranges inside parentheses or square brackets should be "-"
        # e.g., (66e75) -> (66-75), (0.47e0.80) -> (0.47-0.80), [0.37e0.94] -> [0.37-0.94]
        content = re.sub(r'\((\d+(?:\.\d+)?)e(\d+(?:\.\d+)?)\)', r'(\1-\2)', content)
        content = re.sub(r'\[(\d+(?:\.\d+)?)e(\d+(?:\.\d+)?)\]', r'[\1-\2]', content)
        return content

    def clean_table_content(self, table_text: str) -> str:
        """Clean and format table content for ESMO abstracts.
        
        For ESMO abstracts, tables are already in markdown format, but we need to
        normalize LaTeX symbols for better LLM/RAG compatibility.
        """
        if not table_text:
            return ""
        
        # Apply LaTeX normalization to table content
        cleaned = self._normalize_latex_symbols(table_text)
        # Fix OCR error: "e" in numeric ranges inside parentheses or square brackets should be "-"
        # e.g., (66e75) -> (66-75), (0.47e0.80) -> (0.47-0.80), [0.37e0.94] -> [0.37-0.94]
        cleaned = re.sub(r'\((\d+(?:\.\d+)?)e(\d+(?:\.\d+)?)\)', r'(\1-\2)', cleaned)
        cleaned = re.sub(r'\[(\d+(?:\.\d+)?)e(\d+(?:\.\d+)?)\]', r'[\1-\2]', cleaned)
        return cleaned

    def apply_table_refinements(self, content: str) -> str:
        """Apply table-specific refinements (still useful for OCR artifacts).
        
        Note: We preserve table formatting (trailing spaces/pipes) to maintain alignment.
        """
        def fix_table_line(line: str) -> str:
            line = re.sub(r"(?<=\|)([^|\n]*!{5,}[^|\n]*)(?=\|)", " NA ", line)
            line = re.sub(r"(<br\s*/?>)+", "; ", line, flags=re.IGNORECASE)
            line = line.replace("<b>", "").replace("</b>", "")
            # Don't strip trailing pipes/spaces - they're needed for table alignment
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
            "editorial_acknowledgement": "", # <-- NEW FIELD
            "additional_content": "", # <-- Field for table
        }

        # Apply preprocessing steps
        abstract_text = self.apply_foundational_cleanup(abstract_text)
        abstract_text = self.apply_content_normalization(abstract_text)
        abstract_text = self.apply_table_refinements(abstract_text)

        # --- MODIFICATION: Extract specific fields before general cleanup ---
        # Extract Legal entity and Funding first (they might be embedded in editorial acknowledgement)
        legal_match = re.search(
            r"\*\*Legal entity responsible for the study:\*\*\s*(.*?)(?=\n\nFunding:|\n\nDisclosure:|\n\nhttps://doi\.org/|\Z)",
            abstract_text,
            flags=re.DOTALL | re.IGNORECASE
        )
        if legal_match:
            legal_text = legal_match.group(1).strip()
            # Remove any leading markdown formatting or asterisks
            legal_text = re.sub(r'^\*\*\s*', '', legal_text)
            legal_text = re.sub(r'^\*\s+', '', legal_text)
            # Also remove any trailing asterisks
            legal_text = re.sub(r'\s*\*\*$', '', legal_text)
            legal_text = re.sub(r'\s*\*$', '', legal_text)
            # Remove footer patterns like "**S688** Volume 34 ■ Issue S2 ■ 2023"
            legal_text = re.sub(r'\s*\*\*S\d+\*\*\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', legal_text)
            legal_text = re.sub(r'\s*\*\*S\d+\*\*\s*', ' ', legal_text)
            legal_text = re.sub(r'\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', legal_text)
            parsed_data["legal_entity"] = self.clean_text(legal_text).strip()
        
        funding_match = re.search(
            r"Funding:\s*(.*?)(?=\n\nDisclosure:|\n\nhttps://doi\.org/|\Z)",
            abstract_text,
            flags=re.DOTALL | re.IGNORECASE
        )
        if funding_match:
            funding_text = funding_match.group(1)
            # Remove any disclosure information that might be embedded
            funding_text = re.sub(r'\*\*Disclosure:.*$', '', funding_text, flags=re.DOTALL | re.IGNORECASE)
            funding_text = re.sub(r'Disclosure:.*$', '', funding_text, flags=re.DOTALL | re.IGNORECASE)
            funding_text = re.sub(r'Financial Interests.*$', '', funding_text, flags=re.DOTALL | re.IGNORECASE)
            # Remove tables that might be embedded in funding section
            funding_text = re.sub(r'\|\s*Table:.*?(?=\n\n|\Z)', '', funding_text, flags=re.DOTALL)
            funding_text = re.sub(r'\|.*?\|.*?\|', '', funding_text)  # Remove table rows
            # Remove footer patterns like "**S668** Volume 34 ■ Issue S2 ■ 2023"
            funding_text = re.sub(r'\s*\*\*S\d+\*\*\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', funding_text)
            funding_text = re.sub(r'\s*\*\*S\d+\*\*\s*', ' ', funding_text)
            funding_text = re.sub(r'\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', funding_text)
            # Use clean_section_text to remove artifacts like leading ** or #
            parsed_data["funding"] = self.clean_section_text(funding_text)
        
        # Extract Editorial Acknowledgement (but exclude Legal entity and Funding if embedded)
        ack_match = re.search(
            r"(Editorial acknowledgement:.*?(?=\n\nLegal entity|\n\nDisclosure:|\n\nhttps://doi\.org/|\Z))",
            abstract_text,
            flags=re.DOTALL | re.IGNORECASE
        )
        if ack_match:
            # Remove the "Editorial acknowledgement:" label from the content (it will be added as a section heading)
            ack_content = ack_match.group(1)
            # Strip the label and any markdown formatting (**: or :)
            ack_content = re.sub(r'^Editorial acknowledgement:\s*\*?\*?\s*', '', ack_content, flags=re.IGNORECASE)
            # Remove Legal entity and Funding if they're embedded in the acknowledgement
            ack_content = re.sub(r'\*\*Legal entity responsible for the study:\*\*.*?Funding:.*?(?=\Z|$)', '', ack_content, flags=re.DOTALL | re.IGNORECASE)
            ack_content = re.sub(r'\*\*Legal entity responsible for the study:\*\*.*?$', '', ack_content, flags=re.DOTALL | re.IGNORECASE)
            ack_content = re.sub(r'Funding:.*?$', '', ack_content, flags=re.DOTALL | re.IGNORECASE)
            # Remove footer patterns from editorial acknowledgement
            ack_content = re.sub(r'\s*\*\*S\d+\*\*\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', ack_content)
            ack_content = re.sub(r'\s*\*\*S\d+\*\*\s*', ' ', ack_content)
            ack_content = re.sub(r'\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', ack_content)
            
            # Remove tables embedded in editorial acknowledgement (e.g., "| Table: 1083P |")
            ack_content = re.sub(r'\|\s*Table:.*?(?=\n\n|\Z)', '', ack_content, flags=re.DOTALL)
            ack_content = re.sub(r'\|.*?\|.*?\|', '', ack_content)  # Remove table rows
            
            parsed_data["editorial_acknowledgement"] = self.clean_text(ack_content)
        
        # Extract DOI link
        # Handle both plain DOIs and markdown link formats
        # Pattern 1: Markdown link format: https://doi.org/[10.1016/...](https://doi.org/10.1016/...)
        markdown_doi_pattern = r"https://doi\.org/\[10\.1016/[ij]\.annonc\.\d{4}\.\d{2}\.\d{4}\]\(https://doi\.org/10\.1016/[ij]\.annonc\.\d{4}\.\d{2}\.\d{4}\)"
        markdown_match = re.search(markdown_doi_pattern, abstract_text)
        if markdown_match:
            # Extract the actual URL from the markdown link (the one in parentheses)
            url_match = re.search(r"\(https://doi\.org/10\.1016/[ij]\.annonc\.\d{4}\.\d{2}\.\d{4}\)", markdown_match.group(0))
            if url_match:
                # Remove the parentheses
                parsed_data["doi"] = url_match.group(0)[1:-1]
            else:
                # Fallback: extract from brackets
                bracket_match = re.search(r"\[(10\.1016/[ij]\.annonc\.\d{4}\.\d{2}\.\d{4})\]", markdown_match.group(0))
                if bracket_match:
                    parsed_data["doi"] = f"https://doi.org/{bracket_match.group(1)}"
        else:
            # Pattern 2: Plain DOI format
            plain_doi_pattern = r"https://doi\.org/10\.1016/[ij]\.annonc\.\d{4}\.\d{2}\.\d{4}[^\s\n\)]*"
            plain_match = re.search(plain_doi_pattern, abstract_text)
            if plain_match:
                # Clean up any trailing characters like > or other artifacts
                doi_url = plain_match.group(0).rstrip('>')
                parsed_data["doi"] = doi_url

        # Remove disclosure sections (marker leaves these in)
        disclosure_start = abstract_text.find("Financial Interests")
        if disclosure_start == -1:
            disclosure_start = abstract_text.find(
                "All other authors have declared no conflicts"
            )
        if disclosure_start == -1:
            disclosure_start = abstract_text.find("Disclosure:")

        if disclosure_start != -1:
            abstract_text = abstract_text[:disclosure_start]
        # --- END MODIFICATION ---

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

        for original_line in lines:
            line_stripped = original_line.strip()
            if not line_stripped or "melanoma and other skin tumours" in line_stripped.lower():
                continue

            # Check if this is a new abstract (starts with abstract ID in header or standalone)
            # This handles cases like "#### 1117P" or "10760" that indicate a new abstract
            if (
                line_stripped.startswith("# ")
                and re.search(r"\d{3,5}[A-Z]*", line_stripped)
                and len(header_lines) > 0
            ):
                break
            # Also check if line starts with abstract ID pattern (new abstract starting)
            if re.match(r"^(?:#+\s*)?(1\d{3,4}[A-Z]*|[78]\d{2}(?:O|MO|P|TiP))(?:\s|$)", line_stripped) and len(header_lines) > 0 and header_ended:
                break

            lower_line = line_stripped.lower()
            if not header_ended:
                # Check for section markers, handling markdown bold formatting (**Background**:)
                # Remove ** from the line for matching, but keep track of original position
                line_for_matching = lower_line.replace('**', '')
                marker_positions = []
                for m in section_markers:
                    pos = line_for_matching.find(m)
                    if pos != -1:
                        # Find the actual position in the original line (accounting for **)
                        # Count how many ** appear before the marker
                        stars_before = lower_line[:pos + lower_line.count('**', 0, pos) * 2].count('**')
                        actual_pos = pos + stars_before * 2
                        marker_positions.append(actual_pos)
                if marker_positions:
                    header_ended = True
                    start_idx = min(pos for pos in marker_positions if pos != -1)
                    # Preserve original line formatting for tables
                    body_lines.append(original_line[start_idx:])
                    continue

                header_lines.append(line_stripped)
            else:
                if line_stripped.startswith("# ") and re.search(r"\d{3,5}[A-Z]*", line_stripped):
                    break
                # Preserve original line formatting (important for tables)
                body_lines.append(original_line)

        # Pass 2: Parse header for ID, Title, and Authors
        # Pattern matches: 
        # - 1 followed by 3-4 digits with REQUIRED suffix (1076O, 1077MO, etc.) - ESMO 2020/2021/2024
        # - 1 followed by 3-4 digits ending in 0 (OCR error, e.g., 10810 -> 1081O) - ESMO 2023
        # - 7/8 followed by 2 digits with suffix (ESMO 2020/2021)
        # - 4-digit numbers starting with 7 or 8 (ESMO 2022: 7840, 7850, etc.)
        # Note: Require suffix for 1xxx patterns to avoid matching study numbers like "1325", "1901", "1540"
        # But also match 1xxx0 patterns (OCR errors where O is read as 0)
        # Exclude footer patterns like "**$747**" or "**S747**" - these should not match standalone IDs
        id_pattern = r"\b(1\d{3,4}(?:O|MO|P|TiP|0)|[78]\d{2}(?:O|MO|P|TiP)?|[78]\d{3})\b"
        full_header_text = "\n".join(header_lines)
        
        # First, try to find IDs that are on their own line (most reliable)
        # Look for lines that contain only the ID (possibly with whitespace)
        standalone_id_match = None
        for line in header_lines:
            stripped_line = line.strip()
            # Match if line contains only the ID (possibly with markdown formatting)
            if re.match(r'^(?:\*\*)?(1\d{3,4}(?:O|MO|P|TiP|0)|[78]\d{2}(?:O|MO|P|TiP)?|[78]\d{3})(?:\*\*)?\s*$', stripped_line):
                potential_id = re.search(r'(1\d{3,4}(?:O|MO|P|TiP|0)|[78]\d{2}(?:O|MO|P|TiP)?|[78]\d{3})', stripped_line)
                if potential_id:
                    # Make sure it's not a footer pattern like "**$747**" or "**S747**"
                    if not re.search(r'\*\*[$\$S]\d+\*\*', stripped_line):
                        standalone_id_match = potential_id
                        break
        
        # If we found a standalone ID, use it; otherwise fall back to pattern matching
        if standalone_id_match:
            id_match = standalone_id_match
        else:
            id_match = re.search(id_pattern, full_header_text)
        if id_match:
            extracted_id = id_match.group(1)
            # Normalize known OCR errors
            # ESMO 2020: 10760 -> 1076O (OCR error where O was read as 0)
            # ESMO 2021: 10360 -> 1036O, 10370 -> 1037O, 10400 -> 1040O
            # ESMO 2022: 7840 -> 784O, 7850 -> 785O, etc. (OCR error where O was read as 0)
            if extracted_id == "10760":
                extracted_id = "1076O"
            elif extracted_id == "10360":
                extracted_id = "1036O"
            elif extracted_id == "10370":
                extracted_id = "1037O"
            elif extracted_id == "10400":
                extracted_id = "1040O"
            elif re.match(r'^78[4-9]0$', extracted_id):
                # ESMO 2022: 7840-7890 -> 784O-789O (OCR error where O was read as 0)
                extracted_id = extracted_id[:-1] + "O"
            elif re.match(r'^78[4-9]$', extracted_id):
                # ESMO 2022: 784-789 -> 784O-789O (missing O suffix)
                extracted_id = extracted_id + "O"
            elif re.match(r'^10[89]\d0$', extracted_id):
                # ESMO 2023: 10810 -> 1081O, 10820 -> 1082O, etc.
                extracted_id = extracted_id[:-1] + "O"
            elif re.match(r'^11[0-9]\d0$', extracted_id):
                # ESMO 2023: 11000 -> 1100O, 11100 -> 1110O, etc.
                extracted_id = extracted_id[:-1] + "O"
            parsed_data["id"] = extracted_id
            full_header_text = full_header_text.replace(id_match.group(1), "", 1)
        
        title_found = False
        title_lines = []
        lines = full_header_text.split('\n')
        for i, line in enumerate(lines):
            cleaned_line = line.lstrip("# ").strip()
            # Skip footer patterns, author lines, and other non-title content
            if (re.match(r'^\*\*S\d+\*\*\s*Volume', cleaned_line) or
                re.match(r'^Volume \d+ ■ Issue S\d+ ■ \d{4}', cleaned_line) or
                cleaned_line.startswith("<sup>") or
                re.match(r"^[A-Z]\..*", line) or
                len(cleaned_line) < 10):
                continue
            # If we find a line that looks like a title (long enough, not author pattern)
            if len(cleaned_line) > 20:
                if not title_found:
                    parsed_data["title"] = self.clean_text(cleaned_line)
                    title_found = True
                    # Special case: Title ending with "KEYMAKER-" should include "Sequential targeted and immunotherapies in stage IV"
                    if parsed_data["title"].endswith("KEYMAKER-"):
                        parsed_data["title"] = self.clean_text(f"{parsed_data['title']} Sequential targeted and immunotherapies in stage IV")
                    # Check if title ends with "-" and next line might be continuation
                    elif parsed_data["title"].endswith("-") and i + 1 < len(lines):
                        next_line = lines[i + 1].lstrip("# ").strip()
                        # Check if next line looks like a title continuation
                        if (len(next_line) > 10 and 
                            not re.match(r"^[A-Z]\..*", next_line) and
                            not next_line.startswith("<sup>") and
                            not re.match(r'^\*\*S\d+\*\*\s*Volume', next_line)):
                            parsed_data["title"] = self.clean_text(f"{parsed_data['title']} {next_line}")
                    break
            elif title_found and len(cleaned_line) > 10 and not re.match(r"^[A-Z]\..*", line):
                # This might be a continuation of the title
                # Combine with previous title if it makes sense
                combined = f"{parsed_data['title']} {cleaned_line}"
                if len(combined) < 300:  # Reasonable title length
                    parsed_data["title"] = self.clean_text(combined)
                break
        
        if not title_found:
             parsed_data["title"] = "Title not found"
        
        # Clean footer patterns from title
        if parsed_data["title"] != "Title not found":
            parsed_data["title"] = re.sub(r'\s*\*\*S\d+\*\*\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', parsed_data["title"])
            parsed_data["title"] = re.sub(r'\s*\*\*S\d+\*\*\s*', ' ', parsed_data["title"])
            parsed_data["title"] = re.sub(r'\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', parsed_data["title"])
            parsed_data["title"] = parsed_data["title"].strip()

        # Pass 3: Parse body sections
        # --- MODIFICATION: Extract table lines first ---
        table_lines = []
        non_table_lines = []
        for line in body_lines:
            # Check if line is a table line without stripping (to preserve formatting)
            stripped = line.strip()
            if stripped.startswith("|") and "|" in stripped[1:]:
                # Preserve original line with all whitespace for table formatting
                table_lines.append(line)
            else:
                non_table_lines.append(line)

        if table_lines:
            table_content = "\n".join(table_lines).strip()
            parsed_data["additional_content"] = self.clean_table_content(table_content)  # Clean and normalize table content
        
        full_body_text = "\n".join(non_table_lines)
        # --- END MODIFICATION ---

        # Split body by section keywords
        # Handle both plain "Methods:" and markdown bold "**Methods**:"
        # Create patterns that match with or without markdown bold formatting
        section_patterns = []
        for marker in section_markers:
            # Match both "Methods:" and "**Methods**:"
            pattern = rf"(?:\*\*)?{re.escape(marker.rstrip(':'))}(?:\*\*)?:"
            section_patterns.append(pattern)
        
        combined_pattern = f"({'|'.join(section_patterns)})"
        parts = re.split(
            combined_pattern,
            full_body_text,
            flags=re.IGNORECASE,
        )

        for i in range(1, len(parts), 2):
            if i + 1 >= len(parts):
                break

            key = parts[i].lower()
            # Remove markdown bold formatting from key for matching
            key = re.sub(r'\*\*', '', key)
            content = parts[i + 1].strip()

            if key == "background:":
                # Remove leading "** " if present
                content = re.sub(r'^\*\*\s+', '', content)
                parsed_data["background"] = self.clean_section_text(content)
            elif key == "trial design:":
                # Remove embedded editorial acknowledgement
                content = re.sub(r'\*\*Editorial acknowledgement:\*\*.*$', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'Editorial acknowledgement:.*$', '', content, flags=re.DOTALL | re.IGNORECASE)
                parsed_data["trial_design"] = self.clean_section_text(content)
            elif key == "methods:":
                # Remove leading "** " if present
                content = re.sub(r'^\*\*\s+', '', content)
                parsed_data["methods"] = self.clean_section_text(content)
            elif key == "results:":
                parsed_data["results"] = self.clean_section_text(content)
            elif key == "conclusions:":
                # Remove any editorial acknowledgement that might be embedded
                content = re.sub(r'\*\*Editorial acknowledgement:\*\*.*$', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'Editorial acknowledgement:.*$', '', content, flags=re.DOTALL | re.IGNORECASE)
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
                # Only set if not already extracted earlier (to preserve cleaned version)
                if not parsed_data.get("legal_entity"):
                    legal_text = self.clean_section_text(content)
                    # Remove any markdown formatting
                    legal_text = re.sub(r'^\*\*\s*', '', legal_text)
                    legal_text = re.sub(r'^\*\s+', '', legal_text)
                    # Remove footer patterns like "**S688** Volume 34 ■ Issue S2 ■ 2023"
                    legal_text = re.sub(r'\s*\*\*S\d+\*\*\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', legal_text)
                    legal_text = re.sub(r'\s*\*\*S\d+\*\*\s*', ' ', legal_text)
                    legal_text = re.sub(r'\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', legal_text)
                    parsed_data["legal_entity"] = legal_text.strip()
            elif key == "funding:":
                # Only set if not already extracted earlier (to preserve cleaned version)
                if not parsed_data.get("funding"):
                    funding_text = content
                    # Remove any disclosure information that might be embedded
                    funding_text = re.sub(r'\*\*Disclosure:.*$', '', funding_text, flags=re.DOTALL | re.IGNORECASE)
                    funding_text = re.sub(r'Disclosure:.*$', '', funding_text, flags=re.DOTALL | re.IGNORECASE)
                    funding_text = re.sub(r'Financial Interests.*$', '', funding_text, flags=re.DOTALL | re.IGNORECASE)
                    # Remove tables that might be embedded in funding section
                    funding_text = re.sub(r'\|\s*Table:.*?(?=\n\n|\Z)', '', funding_text, flags=re.DOTALL)
                    funding_text = re.sub(r'\|.*?\|.*?\|', '', funding_text)  # Remove table rows
                    # Remove footer patterns like "**S668** Volume 34 ■ Issue S2 ■ 2023"
                    funding_text = re.sub(r'\s*\*\*S\d+\*\*\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', funding_text)
                    funding_text = re.sub(r'\s*\*\*S\d+\*\*\s*', ' ', funding_text)
                    funding_text = re.sub(r'\s*Volume \d+ ■ Issue S\d+ ■ \d{4}\s*', ' ', funding_text)
                    parsed_data["funding"] = self.clean_section_text(funding_text)

        return ParsedAbstract(**parsed_data)

    async def format_to_markdown(
        self, parsed_abstract: ParsedAbstract, config: PostprocessingConfiguration
    ) -> str:
        """Format parsed abstract to structured markdown."""
        md_output = [
            f"### Abstract ID: {parsed_abstract.id}",
            "",  # Blank line between Abstract ID and Title
        ]

        # --- MODIFICATION: Removed Authors/Affiliations ---
        # (Author block removed)
        # --- END MODIFICATION ---

        # Main content sections (including Title)
        section_order: list[tuple[str, str]] = [
            ("Title", parsed_abstract.title),
            ("Background", parsed_abstract.background),
            ("Trial Design", parsed_abstract.trial_design),
            ("Methods", parsed_abstract.methods),
            ("Results", parsed_abstract.results),
            ("Conclusions", parsed_abstract.conclusions),
        ]

        for display_name, content in section_order:
            if content:
                md_output.append(f"#### {display_name}:")
                # Use clean_text for final formatting
                md_output.append(f"{self.clean_text(content)}\n")

        # --- MODIFICATION: Add Table as a separate section ---
        if (
            hasattr(parsed_abstract, "additional_content")
            and parsed_abstract.additional_content
        ):
            md_output.append("#### Table:")
            md_output.append(parsed_abstract.additional_content) # Already clean markdown
            md_output.append("")
        # --- END MODIFICATION ---

        # --- MODIFICATION: Add Editorial Acknowledgement ---
        if parsed_abstract.editorial_acknowledgement:
            md_output.append("#### Editorial acknowledgement:")
            md_output.append(f"{parsed_abstract.editorial_acknowledgement}")
            md_output.append("")
        # --- END MODIFICATION ---

        # Metadata sections
        if parsed_abstract.clinical_trial_info:
            md_output.append("#### Clinical trial identification:")
            md_output.append(f"{parsed_abstract.clinical_trial_info}")
            md_output.append("")

        if parsed_abstract.legal_entity:
            md_output.append("#### Legal entity responsible for the study:")
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
        # Expected format: 1076O, 1077MO, 1084P, 1153TiP (ESMO 2020/2021)
        # Or 7840, 7850, etc. (ESMO 2022)
        # Also accept 10760 (will be normalized to 1076O)
        valid_id_pattern = r"1\d{3,4}(?:[A-Z]+|TiP)?|[78]\d{2}(?:O|MO|P|TiP)?|[78]\d{3}"
        if (
            not re.match(valid_id_pattern, parsed_abstract.id)
            and parsed_abstract.id != "N/A"
            and parsed_abstract.id != "10760"  # Known OCR variant
        ):
            issues.append("Missing/invalid Abstract ID")

        # Check for title
        if parsed_abstract.title == "N/A" or not parsed_abstract.title.strip():
            issues.append("Missing Title")

        # Check for required sections (skip for TiP abstracts)
        is_tip_abstract = "TiP" in parsed_abstract.id
        if not is_tip_abstract:
            required_sections = ["background", "methods", "results", "conclusions"]
            for section in required_sections:
                content = getattr(parsed_abstract, section, "")
                if not content or content.strip() == "":
                    # Don't flag missing sections if the abstract is clearly just a title
                    if any([parsed_abstract.background, parsed_abstract.methods, parsed_abstract.results, parsed_abstract.conclusions]):
                        issues.append(f"Missing '{section.title()}' section")

        return issues