"""Slice parsed-markdown sections per family, with positional + keyword fallback.

Required families (IDENTIFICATION, RESPONSE_RATES, PFS_FAMILY, OS_FAMILY,
AE_GENERAL, AE_GRADE3_SPECIFIC) always return a non-empty slice; if classified
buckets are empty, fallback rules pull from `OTHER` blocks and positional
slices of the raw markdown.

Optional families (EFS_RFS_MFS, TIME_TO_METRICS, TEAE_*, TRAE_*) return
`None` when their anchor pattern hits nothing in classified-or-OTHER content
— the orchestrator uses this as a skip-signal.
"""
from __future__ import annotations

import re

from ..domain.extraction_models import AttributeFamily
from .markdown_section_parser import (
    ParsedDoc,
    SectionCategory,
    TableBlock,
)

_OPTIONAL_FAMILIES = {
    AttributeFamily.EFS_RFS_MFS,
    AttributeFamily.TIME_TO_METRICS,
    AttributeFamily.TRAE_GENERAL,
    AttributeFamily.TRAE_GRADE3_SPECIFIC,
    AttributeFamily.TEAE_GENERAL,
    AttributeFamily.TEAE_GRADE3_SPECIFIC,
}

_TABLE_KEYWORDS_BY_FAMILY: dict[AttributeFamily, re.Pattern[str]] = {
    AttributeFamily.RESPONSE_RATES: re.compile(
        r"\b(response|cr|pr|orr|dcr|outcome|efficacy)\b", re.I
    ),
    AttributeFamily.PFS_FAMILY: re.compile(
        r"\b(progression|pfs|outcome|efficacy|survival)\b", re.I
    ),
    AttributeFamily.OS_FAMILY: re.compile(r"\b(survival|os|outcome|efficacy)\b", re.I),
    AttributeFamily.EFS_RFS_MFS: re.compile(
        r"\b(efs|rfs|mfs|event[-\s]?free|recurrence[-\s]?free|relapse[-\s]?free|metastasis[-\s]?free)\b",
        re.I,
    ),
    AttributeFamily.TIME_TO_METRICS: re.compile(
        r"\b(ttr|ttp|ttnt|ttf|time[-\s]?to[-\s]?(response|progression|next|treatment|failure))\b",
        re.I,
    ),
    AttributeFamily.AE_GENERAL: re.compile(
        r"\b(adverse|grade|treatment-related|tolerability|safety)\b", re.I
    ),
    AttributeFamily.AE_GRADE3_SPECIFIC: re.compile(r"\b(adverse|grade)\b", re.I),
    AttributeFamily.TEAE_GENERAL: re.compile(
        r"\b(teae|treatment[-\s]?emergent|adverse|grade)\b", re.I
    ),
    AttributeFamily.TEAE_GRADE3_SPECIFIC: re.compile(
        r"\b(teae|treatment[-\s]?emergent|adverse|grade)\b", re.I
    ),
    AttributeFamily.TRAE_GENERAL: re.compile(
        r"\b(trae|treatment[-\s]?related|drug[-\s]?related|adverse)\b", re.I
    ),
    AttributeFamily.TRAE_GRADE3_SPECIFIC: re.compile(
        r"\b(trae|treatment[-\s]?related|drug[-\s]?related|adverse)\b", re.I
    ),
}


def _matching_tables(parsed: ParsedDoc, family: AttributeFamily) -> list[TableBlock]:
    pat = _TABLE_KEYWORDS_BY_FAMILY.get(family)
    if pat is None:
        return parsed.tables
    return [t for t in parsed.tables if any(pat.search(k) for k in t.keywords)]


def _join(parts: list[str]) -> str:
    return "\n\n".join(p for p in parts if p and p.strip())


def _positional_fallback(raw_md: str, lo: float, hi: float) -> str:
    """Return the chars in `[lo, hi]` of `raw_md`, snapped to paragraph boundaries."""
    if not raw_md:
        return ""
    n = len(raw_md)
    start, end = max(0, int(n * lo)), min(n, int(n * hi))
    # Snap start to next paragraph break, end to previous.
    while start < end and raw_md[start] not in "\n":
        start += 1
    while end > start and raw_md[end - 1] not in "\n":
        end -= 1
    return raw_md[start:end].strip()


def _other_blocks_matching(parsed: ParsedDoc, regex: re.Pattern[str]) -> str:
    return _join(
        [
            b
            for b in parsed.by_category.get(SectionCategory.OTHER, [])
            if regex.search(b)
        ]
    )


def _grep_paragraphs(text: str, regex: re.Pattern[str]) -> str:
    if not text:
        return ""
    paragraphs = re.split(r"\n\s*\n", text)
    return _join([p for p in paragraphs if regex.search(p)])


def _resolve_methods(parsed: ParsedDoc, raw_md: str) -> str:
    text = parsed.text_for(SectionCategory.METHODS)
    if text:
        return text
    methods_re = re.compile(
        r"\b(method|study design|protocol|eligibility|statistical|endpoint|randomi)\b",
        re.I,
    )
    other_hits = _other_blocks_matching(parsed, methods_re)
    positional = _positional_fallback(raw_md, 0.25, 0.55)
    return _join([other_hits, positional])


def _resolve_results(parsed: ParsedDoc, raw_md: str) -> str:
    text = parsed.text_for(SectionCategory.RESULTS)
    if text:
        return text
    results_re = re.compile(
        r"\b(result|finding|efficacy|response|orr|median|survival|activity)\b", re.I
    )
    other_hits = _other_blocks_matching(parsed, results_re)
    positional = _positional_fallback(raw_md, 0.55, 0.95)
    return _join([other_hits, positional])


def _resolve_safety(parsed: ParsedDoc, raw_md: str) -> str:
    text = parsed.text_for(SectionCategory.SAFETY)
    if text:
        return text
    safety_re = re.compile(
        r"\b(adverse|safety|grade|toxicity|tolerability|teae|trae)\b", re.I
    )
    pieces: list[str] = [_other_blocks_matching(parsed, safety_re)]
    pieces.append(_grep_paragraphs(parsed.text_for(SectionCategory.RESULTS), safety_re))
    if not any(pieces):
        pieces.append(_grep_paragraphs(raw_md, safety_re))
    return _join(pieces)


def _resolve_abstract(parsed: ParsedDoc, raw_md: str) -> str:
    text = parsed.text_for(SectionCategory.ABSTRACT)
    if text:
        return text
    return raw_md[:1500] if raw_md else ""


def _ae_classification_sentence(methods_text: str) -> str:
    if not methods_text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", methods_text)
    keep: list[str] = []
    for s in sentences:
        low = s.lower()
        if "adverse event" in low and (
            "grad" in low
            or "ctcae" in low
            or "common terminology" in low
            or "considered related" in low
            or "treatment-related" in low
        ):
            keep.append(s)
    return " ".join(keep)


def slice_for_family(
    family: AttributeFamily, parsed: ParsedDoc, *, raw_md: str
) -> str | None:
    """Return the slice for `family`, or `None` to skip (optional families only)."""
    title = parsed.text_for(SectionCategory.TITLE)
    abstract = _resolve_abstract(parsed, raw_md)
    methods = _resolve_methods(parsed, raw_md)
    results = _resolve_results(parsed, raw_md)
    safety = _resolve_safety(parsed, raw_md)
    tables = _matching_tables(parsed, family)
    table_text = "\n\n".join(t.text for t in tables)
    other = parsed.text_for(SectionCategory.OTHER)

    if family is AttributeFamily.IDENTIFICATION:
        return _join([f"# Title\n{title}", abstract, methods, other])

    if family in {
        AttributeFamily.RESPONSE_RATES,
        AttributeFamily.PFS_FAMILY,
        AttributeFamily.OS_FAMILY,
    }:
        return _join([abstract, results, table_text, other])

    if family in {AttributeFamily.EFS_RFS_MFS, AttributeFamily.TIME_TO_METRICS}:
        anchor_pat = _TABLE_KEYWORDS_BY_FAMILY[family]
        haystack = _join([results, table_text, other])
        if not anchor_pat.search(haystack):
            return None
        return _join([results, table_text, other])

    if family in {
        AttributeFamily.AE_GENERAL,
        AttributeFamily.AE_GRADE3_SPECIFIC,
        AttributeFamily.TEAE_GENERAL,
        AttributeFamily.TEAE_GRADE3_SPECIFIC,
        AttributeFamily.TRAE_GENERAL,
        AttributeFamily.TRAE_GRADE3_SPECIFIC,
    }:
        ae_methods = _ae_classification_sentence(methods)
        anchor_pat = _TABLE_KEYWORDS_BY_FAMILY[family]
        signal = _join([safety, results, table_text, other])
        if family in _OPTIONAL_FAMILIES and not anchor_pat.search(signal):
            return None
        return _join([ae_methods, safety, results, table_text, other])

    return _join([abstract, results, table_text, other])
