"""Parse cleaned publication markdown into category-classified sections + tables.

Detection-first: every ``^#+ `` line is a header. Each header is classified by
keyword scoring against per-category lexicons. Headers that don't match any
canonical category land in `OTHER` (preserved for router fallback). Tables —
runs of `|`-prefixed lines — are captured separately with frequency keywords
so the router can pick relevant ones per family.

No hardcoded header-string synonym map. Lexicons grow from real misses
surfaced via `ParsedDoc.unclassified`.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SectionCategory(str, Enum):
    TITLE = "title"
    ABSTRACT = "abstract"
    METHODS = "methods"
    RESULTS = "results"
    SAFETY = "safety"  # often a sub-header under results — promoted to top-level
    DISCUSSION = "discussion"  # captured but not used by router (drop semantically)
    DROP = (
        "drop"  # explicit boilerplate — Research-in-context, Funding, References, etc.
    )
    OTHER = "other"  # unclassified — kept for fallback


# Per-category keyword weights. Tokens that strongly identify a category get higher weight.
# A header's category is `argmax(score)` after summing token weights present in the lower-cased
# header. Tie or all zero → OTHER. DROP wins over OTHER even on a single hit.
_LEXICONS: dict[SectionCategory, dict[str, int]] = {
    SectionCategory.METHODS: {
        "method": 5,
        "methodology": 5,
        "patient": 2,
        "study": 2,
        "design": 3,
        "procedure": 4,
        "intervention": 3,
        "statistical": 4,
        "analysis": 2,
        "eligibility": 5,
        "treatment": 1,
        "oversight": 3,
        "randomi": 4,
        "blind": 3,
        "endpoint": 4,
        "end-point": 4,
        "outcome": 1,
        "protocol": 4,
        "assessment": 2,
        "selection": 2,
        "monitoring": 2,
        "specimen": 3,
    },
    SectionCategory.RESULTS: {
        "result": 5,
        "finding": 5,
        "outcome": 3,
        "efficacy": 5,
        "response": 2,
        "activity": 3,
        "baseline": 2,
        "demographic": 3,
        "characteristic": 2,
        "follow-up": 2,
        "followup": 2,
        "survival": 2,
    },
    SectionCategory.SAFETY: {
        "safety": 5,
        "adverse": 5,
        "toxicity": 5,
        "tolerability": 5,
        "ae": 4,
        "teae": 4,
        "trae": 4,
        "grade": 1,
    },
    SectionCategory.ABSTRACT: {
        "abstract": 6,
        "summary": 6,
    },
    SectionCategory.DISCUSSION: {
        "discussion": 6,
        "interpretation": 5,
        "conclusion": 4,
        "implication": 4,
        "perspective": 3,
    },
    SectionCategory.DROP: {
        "research in context": 10,
        "evidence before": 10,
        "knowledge generated": 10,
        "what is already known": 10,
        "what this study adds": 10,
        "how this study might affect": 10,
        "added value": 10,
        "key objective": 10,
        "relevance": 6,
        "context": 3,
        "introduction": 6,
        "background": 5,
        "funding": 6,
        "role of the funding": 8,
        "acknowledg": 5,
        "reference": 5,
        "appendix": 4,
        "supplementary": 3,
        "competing interest": 6,
        "author contribution": 6,
        "data sharing": 5,
        "ethics": 4,
    },
}

_HEADER_RE = re.compile(r"^(#+)\s+(.*?)\s*$")
_TABLE_LINE_RE = re.compile(r"^\s*\|")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]{2,}")


def _norm(text: str) -> str:
    return re.sub(r"\*+", "", text).strip().lower()


def classify_header(header_text: str) -> SectionCategory:
    """Score a header against each category's lexicon; return argmax (tie → OTHER)."""
    norm = _norm(header_text)
    if not norm:
        return SectionCategory.OTHER

    scores: dict[SectionCategory, int] = defaultdict(int)
    for category, lex in _LEXICONS.items():
        for token, weight in lex.items():
            if token in norm:
                scores[category] += weight

    if not scores:
        return SectionCategory.OTHER

    # DROP wins over OTHER even on a small hit; over canonical only if it strictly beats them.
    best = max(scores.items(), key=lambda kv: kv[1])
    top_score = best[1]
    top_categories = [c for c, s in scores.items() if s == top_score]
    if len(top_categories) > 1:
        # Tie among canonicals → OTHER (force router fallback).
        # Tie that includes DROP → DROP wins (boilerplate is louder than canonical here).
        if SectionCategory.DROP in top_categories:
            return SectionCategory.DROP
        return SectionCategory.OTHER
    return best[0]


@dataclass(frozen=True)
class TableBlock:
    text: str
    keywords: frozenset[str]


@dataclass
class ParsedDoc:
    by_category: dict[SectionCategory, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    tables: list[TableBlock] = field(default_factory=list)
    unclassified: list[str] = field(default_factory=list)  # raw header text for tuning

    def text_for(self, category: SectionCategory) -> str:
        return "\n\n".join(self.by_category.get(category, [])).strip()


def parse_markdown(md: str) -> ParsedDoc:
    lines = md.splitlines()
    out = ParsedDoc()

    # Title: first H1, captured separately from the section walk so we don't
    # double-classify it (a real title like "Dabrafenib and trametinib in
    # patients with melanoma" would otherwise score METHODS via "patient" +
    # "treatment" tokens).
    title_line_idx: int | None = None
    for i, ln in enumerate(lines):
        m = _HEADER_RE.match(ln)
        if m and len(m.group(1)) == 1:
            out.by_category[SectionCategory.TITLE].append(_norm(m.group(2)).title())
            title_line_idx = i
            break

    current: SectionCategory | None = None
    buf: list[str] = []
    table_buf: list[str] = []
    in_table = False

    def flush_section() -> None:
        nonlocal buf
        if current is not None and buf:
            joined = "\n".join(buf).strip()
            if joined:
                out.by_category[current].append(joined)
        buf = []

    def flush_table() -> None:
        nonlocal table_buf, in_table
        if table_buf:
            text = "\n".join(table_buf).strip()
            keywords = frozenset(_WORD_RE.findall(text.lower()))
            out.tables.append(TableBlock(text=text, keywords=keywords))
        table_buf = []
        in_table = False

    for i, ln in enumerate(lines):
        # The line that produced TITLE was already consumed by the pre-loop;
        # skip it so its keywords don't leak into a Methods bucket.
        if i == title_line_idx:
            continue

        if _TABLE_LINE_RE.match(ln):
            in_table = True
            table_buf.append(ln)
            buf.append(ln)
            continue
        if in_table:
            flush_table()

        m = _HEADER_RE.match(ln)
        if not m:
            buf.append(ln)
            continue

        depth, raw_name = len(m.group(1)), m.group(2)
        category = classify_header(raw_name)

        if depth == 1:
            flush_section()
            if category is SectionCategory.OTHER:
                out.unclassified.append(raw_name)
            current = category
            continue

        # H2+: stays in the active H1 bucket (sub-section content, e.g. ## Efficacy under # Results),
        # UNLESS the H2 itself classifies as a different canonical category — promote it.
        # This handles publications whose results sub-blocks live under a generic # ABSTRACT or # Summary.
        if current is None and category not in {
            SectionCategory.OTHER,
            SectionCategory.DROP,
        }:
            current = category
            continue
        buf.append(ln)

    flush_section()
    flush_table()

    if out.unclassified:
        logger.info(
            "markdown_section_parser_unclassified count=%d headers=%s",
            len(out.unclassified),
            out.unclassified[:10],
        )
    return out
