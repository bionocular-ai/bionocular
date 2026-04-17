"""Document section classification patterns — domain layer.

These mappings define what constitutes each section in a clinical trial
document (abstract or publication). They are oncology domain knowledge:
a "Results" section contains efficacy, safety, and survival data;
a "Methods" section contains patient eligibility and trial design.

Infrastructure (`langchain/chunking.py`) uses these patterns to assign
`ChunkType` labels during document ingestion.
"""

from .models import ChunkType

# Maps each ChunkType to the header keywords that identify it in abstract-style
# documents (where sections are marked with #### Section: headers).
SECTION_PATTERNS: dict[ChunkType, list[str]] = {
    ChunkType.BACKGROUND: ["background", "#### background:"],
    ChunkType.METHODS: ["method", "#### methods:"],
    ChunkType.TRIAL_DESIGN: ["trial design", "#### trial design:"],
    ChunkType.RESULTS: ["result", "#### results:"],
    ChunkType.CONCLUSIONS: ["conclusion", "#### conclusions:"],
    ChunkType.TABLE: ["table", "#### table:"],
    ChunkType.CLINICAL_TRIAL: [
        "clinical trial",
        "#### clinical trial",
        "#### clinical trial information:",
        "#### clinical trial identification:",
    ],
    ChunkType.SPONSOR: ["sponsor", "#### research sponsor:"],
    ChunkType.FUNDING: ["funding", "#### funding:"],
    ChunkType.DOI: ["doi", "#### doi:"],
    ChunkType.FULL_TEXT_REFERENCE: ["full text", "#### full text reference:"],
}

# Keywords used to classify chunks from publication-style headers
# (Main Section / Subsection markdown headers, not #### abstract headers).
# Each entry is a tuple of (ChunkType, keywords) checked in order.
PUBLICATION_SECTION_KEYWORDS: list[tuple[ChunkType, list[str]]] = [
    (
        ChunkType.RESULTS,
        [
            "result",
            "finding",
            "clinical activity",
            "efficacy",
            "safety",
            "adverse",
            "demographic",
            "response",
            "survival",
            "outcome",
            "summary",
        ],
    ),
    (
        ChunkType.METHODS,
        ["method", "patient", "trial design", "eligibility"],
    ),
    (
        ChunkType.BACKGROUND,
        ["background", "introduction"],
    ),
    (
        ChunkType.CONCLUSIONS,
        ["conclusion", "discussion"],
    ),
]
