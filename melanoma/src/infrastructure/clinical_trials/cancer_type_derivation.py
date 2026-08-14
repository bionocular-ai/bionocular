"""Derive `clinical_trials.cancer_type` from a trial's own reported conditions.

The label used to be a byproduct of the ClinicalTrials.gov search term that
discovered the trial. That term cannot carry the meaning it was asked to:
`query.cond` is an Essie expression spanning `Condition`, `BriefTitle`,
`OfficialTitle`, `ConditionMeshTerm`, `ConditionAncestorTerm` and `Keyword`, and a
multi-word phrase resolves through a synonym thesaurus, so "Cutaneous melanoma"
collapses to MeSH D008545 Melanoma and returns 3708 of the registry's 3746 melanoma
studies - including every uveal, acral and mucosal trial.

Discovery and labelling are therefore separated. The search terms stay as the
ingestion net; the label is derived here from what the sponsor wrote.

Canonical bucket names come from `cancer_type_mapping.SKIN_CANCER_TYPES` and are the
values already stored in `clinical_trials.cancer_type`. The web layer maps the
`Cutaneous Melanoma` bucket to the display label "Cutaneous/Metastatic Melanoma"
(`web/src/lib/dashboard-constants.ts`); the stored string is deliberately unchanged.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Final

logger = logging.getLogger(__name__)

CUTANEOUS_MELANOMA: Final[str] = "Cutaneous Melanoma"
UVEAL_MELANOMA: Final[str] = "Uveal Melanoma"
ACRAL_MELANOMA: Final[str] = "Acral Melanoma"
MUCOSAL_MELANOMA: Final[str] = "Mucosal Melanoma"
BASAL_CELL_CARCINOMA: Final[str] = "Basal Cell Carcinoma"
MERKEL_CELL_CARCINOMA: Final[str] = "Merkel Cell Carcinoma"
CUTANEOUS_SCC: Final[str] = "Cutaneous Squamous Cell Carcinoma"
BRAIN_CNS_METASTASIS: Final[str] = "Cutaneous Melanoma with Brain/CNS Metastasis"

MELANOMA_SUBTYPES: Final[frozenset[str]] = frozenset(
    {UVEAL_MELANOMA, ACRAL_MELANOMA, MUCOSAL_MELANOMA}
)

# Everything to the right of one of these is a statement about what the trial does
# NOT study. "Melanoma (Excluding Uveal Melanoma)" keeps its leading "Melanoma";
# "Non-Melanoma Skin Cancer" keeps nothing.
NEGATION_MARKER: Final[re.Pattern[str]] = re.compile(
    r"\b(?:excluding|except|other than|without|non)\b"
)

# A trial whose conditions are generic cancer language rather than a named disease.
BASKET_MARKERS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p)
    for p in (
        r"\bsolid (?:tumou?rs?|cancers?|neoplasms?|malignanc\w*|disease)\b",
        r"^cancers?$",
        r"^carcinomas?$",
        r"\badvanced cancer\b",
        r"\bmalignanc",
        r"\bmalignant neoplasm\b",
        r"\bneoplasms by\b",
        r"\brare cancers?\b",
        r"\bunknown primary\b",
        r"\blife threatening\b",
        r"\bunspecified adult solid tumor\b",
    )
)

# Every token in a group must appear in the same condition string. Prefixes are
# intentional: "metasta" covers metastasis and metastases.
_TokenGroups = tuple[tuple[str, ...], ...]

MELANOMA_SUBTYPE_RULES: Final[dict[str, _TokenGroups]] = {
    UVEAL_MELANOMA: (
        ("uveal", "melanoma"),
        ("ocular", "melanoma"),
        ("intraocular", "melanoma"),
        ("choroidal", "melanoma"),
        ("choroid", "melanoma"),
        ("ciliary", "melanoma"),
        ("iris", "melanoma"),
    ),
    ACRAL_MELANOMA: (("acral", "melanoma"),),
    MUCOSAL_MELANOMA: (
        ("mucosal", "melanoma"),
        ("vulvar", "melanoma"),
        ("vaginal", "melanoma"),
        ("anorectal", "melanoma"),
        ("sinonasal", "melanoma"),
        ("conjunctival", "melanoma"),
        ("urethral", "melanoma"),
        ("esophageal", "melanoma"),
    ),
}

NON_MELANOMA_RULES: Final[dict[str, _TokenGroups]] = {
    BASAL_CELL_CARCINOMA: (
        ("basal", "cell", "carcinoma"),
        ("basal", "cell", "cancer"),
    ),
    MERKEL_CELL_CARCINOMA: (
        ("merkel", "cell", "carcinoma"),
        ("merkel", "cell", "cancer"),
        # Older names for the same disease. Both need "skin" in the same string:
        # neuroendocrine carcinoma arises throughout the body.
        ("neuroendocrine", "carcinoma", "skin"),
        ("trabecular", "carcinoma", "skin"),
    ),
}

BRAIN_CNS_RULES: Final[_TokenGroups] = (
    ("brain", "metasta"),
    ("cns", "metasta"),
    ("intracranial", "metasta"),
    ("leptomeningeal",),
)

SQUAMOUS: Final[re.Pattern[str]] = re.compile(r"\bsquamous\b|\bscc\b")
CARCINOMA_OR_CANCER: Final[re.Pattern[str]] = re.compile(
    r"\b(?:carcinoma|cancer|scc)\b"
)

SKIN_QUALIFIER: Final[re.Pattern[str]] = re.compile(
    r"\b(?:cutaneous|skin|cscc|scalp|eyelid)"
)

# Organs where squamous cell carcinoma also arises. A closed medical set, not an
# open-ended blocklist: naming one of these means the string is not cutaneous.
NON_SKIN_SITE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:head and neck|hypopharyn\w*|oropharyn\w*|nasopharyn\w*|pharyn\w*|laryn\w*"
    r"|lung|pulmonar\w*|esophag\w*|oesophag\w*|cervix|cervical|anus|anal|penile|penis"
    r"|vulva\w*|vagina\w*|oral cavity|tongue|tonsil\w*|bronch\w*|neck|thymic|bladder"
    r"|urotheli\w*|sinonasal|salivary|paranasal|nasal cavity|sinus|glottic|buccal"
    r"|gingiv\w*|palate|maxillary|trachea\w*|fallopian|colorectal|uterin\w*)"
)

# Conditions that establish the trial as dermatology-scoped.
SKIN_CANCER_CONTEXT: Final[re.Pattern[str]] = re.compile(
    r"\b(?:basal cell|merkel|actinic keratos\w*|keratoacanthoma|bowen|skin cancer"
    r"|skin neoplasm\w*|cutaneous|melanoma|kaposi|mycosis fungoides|sezary)"
)

MELANOMA: Final[re.Pattern[str]] = re.compile(r"\bmelanoma")


@dataclass(frozen=True)
class DerivedCancerTypes:
    """Buckets a trial earned, with the sponsor's own words backing each one.

    `evidence` maps a bucket to the original (un-normalised) condition string that
    produced it, so a reviewer or the chat agent can quote the justification rather
    than assert the tag.
    """

    buckets: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)
    is_basket: bool = False
    melanoma_unspecified: bool = False


def _normalise(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _positive_part(normalised: str) -> str:
    """The portion of a condition string that asserts rather than excludes."""
    match = NEGATION_MARKER.search(normalised)
    return normalised if match is None else normalised[: match.start()].strip()


def _matches(text: str, groups: _TokenGroups) -> bool:
    return any(
        all(re.search(rf"\b{token}", text) for token in group) for group in groups
    )


def _is_basket(normalised: list[str]) -> bool:
    """Whether the condition list is generic cancer language rather than a disease.

    Reads the whole string, never the positive part: dropping the text after a
    negation marker can leave a fragment that matches an anchored pattern, which would
    make 'Carcinoma, Non-Small-Cell Lung' read as the bare basket 'Carcinoma'.
    """
    return any(marker.search(text) for text in normalised for marker in BASKET_MARKERS)


def _derive_cutaneous_scc(
    originals: list[str],
    normalised: list[str],
    positives: list[str],
    is_basket: bool,
) -> tuple[str, str] | None:
    """Decide whether an SCC mention is cutaneous. Returns (bucket, evidence).

    Squamous cell carcinoma is a histology, not a site, and 191 condition strings in
    the corpus name it with no qualifier at all. A string that calls itself cutaneous
    wins outright, even when it also names a site: 'Cutaneous Squamous Cell Carcinoma
    of the Head and Neck' is a skin primary, and head and neck is where that skin is.
    Otherwise a named non-skin site beats trial-level skin context, and an unqualified
    mention is cutaneous only in a dermatology-scoped, non-basket trial.

    The qualifier is only ever read from the string that carries the SCC, so a trial
    listing 'Cutaneous Melanoma' beside 'Head and Neck Squamous Cell Carcinoma' still
    earns no cSCC bucket.

    Assertions are read from the positive part, but the organ is looked for in the
    whole string: in 'Squamous Cell Carcinoma, Non-Small Cell Lung' the site sits
    after the negation marker, and missing it would leave an apparently bare SCC.
    """
    squamous = [
        (original, full, text)
        for original, full, text in zip(originals, normalised, positives)
        if SQUAMOUS.search(text) and CARCINOMA_OR_CANCER.search(text)
    ]
    if not squamous:
        return None

    for original, _full, text in squamous:
        if SKIN_QUALIFIER.search(text):
            return CUTANEOUS_SCC, original

    unqualified = [(o, t) for o, full, t in squamous if not NON_SKIN_SITE.search(full)]
    if not unqualified:
        return None

    has_skin_context = any(SKIN_CANCER_CONTEXT.search(text) for text in positives)
    if has_skin_context and not is_basket:
        return CUTANEOUS_SCC, unqualified[0][0]
    return None


def derive_cancer_types(
    conditions: list[str],
    keywords: list[str] | None = None,
) -> DerivedCancerTypes:
    """Map a trial's reported conditions onto the eight canonical skin-cancer buckets.

    Args:
        conditions: `protocolSection.conditionsModule.conditions`, verbatim.
        keywords: accepted so callers need not change when keyword rules are added.
            Deliberately unused today - every bucket reads `conditions` only, so one
            field decides every tag.

    Returns:
        Buckets (sorted), per-bucket evidence, and the two agent caveat flags.
    """
    del keywords  # see docstring

    originals = list(conditions or [])
    normalised = [_normalise(text) for text in originals]
    positives = [_positive_part(text) for text in normalised]

    buckets: set[str] = set()
    evidence: dict[str, str] = {}
    claimed: set[int] = set()

    # Specific melanoma subtypes consume the string they matched, so the generic
    # bucket cannot also claim it. This is what keeps ['Metastatic Uveal Melanoma']
    # from deriving to both Uveal and Cutaneous.
    for bucket, groups in MELANOMA_SUBTYPE_RULES.items():
        for index, text in enumerate(positives):
            if _matches(text, groups):
                buckets.add(bucket)
                evidence.setdefault(bucket, originals[index])
                claimed.add(index)

    for bucket, groups in NON_MELANOMA_RULES.items():
        for index, text in enumerate(positives):
            if _matches(text, groups):
                buckets.add(bucket)
                evidence.setdefault(bucket, originals[index])
                break

    is_basket = _is_basket(normalised)

    scc = _derive_cutaneous_scc(originals, normalised, positives, is_basket)
    if scc is not None:
        buckets.add(scc[0])
        evidence.setdefault(scc[0], scc[1])

    residual = [
        index
        for index, text in enumerate(positives)
        if MELANOMA.search(text) and index not in claimed
    ]
    if residual:
        buckets.add(CUTANEOUS_MELANOMA)
        evidence.setdefault(CUTANEOUS_MELANOMA, originals[residual[0]])

    # Site of metastasis, not a histology: only meaningful on top of a melanoma.
    if buckets & (MELANOMA_SUBTYPES | {CUTANEOUS_MELANOMA}):
        for index, text in enumerate(positives):
            if _matches(text, BRAIN_CNS_RULES):
                buckets.add(BRAIN_CNS_METASTASIS)
                evidence.setdefault(BRAIN_CNS_METASTASIS, originals[index])
                break

    melanoma_unspecified = (
        bool(residual)
        and not (buckets & MELANOMA_SUBTYPES)
        and not any(
            MELANOMA.search(text) and SKIN_QUALIFIER.search(text) for text in positives
        )
    )

    return DerivedCancerTypes(
        buckets=sorted(buckets),
        evidence=evidence,
        is_basket=is_basket,
        melanoma_unspecified=melanoma_unspecified,
    )
