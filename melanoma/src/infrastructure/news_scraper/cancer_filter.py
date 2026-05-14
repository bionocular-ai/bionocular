from .base import NewsArticleRaw

# Canonical type names match getDbCancerType() output in web/src/lib/api.ts
# so that .contains('cancer_type', [getDbCancerType(slug)]) queries match.
# Order matters: more specific subtypes checked before generic "Cutaneous Melanoma".
_BRAIN_CNS_KEYWORDS = [
    "melanoma brain metastasis",
    "melanoma cns metastasis",
    "melanoma brain met",
    "intracranial melanoma",
    "leptomeningeal melanoma",
]
_UVEAL_KEYWORDS = ["uveal melanoma", "ocular melanoma", "choroidal melanoma"]
_ACRAL_KEYWORDS = ["acral melanoma", "acral lentiginous melanoma"]
_MUCOSAL_KEYWORDS = ["mucosal melanoma"]
# "rare melanoma" refers collectively to uveal/acral/mucosal subtypes
_RARE_MELANOMA_KEYWORDS = ["rare melanoma"]
_CSCC_KEYWORDS = ["cutaneous squamous cell carcinoma", "cscc"]
_BCC_KEYWORDS = ["basal cell carcinoma", "bcc"]
_MCC_KEYWORDS = ["merkel cell carcinoma", "merkel cell cancer", "merkel cell"]


def assign_cancer_types(article: NewsArticleRaw) -> list[str]:
    text = (article.title + " " + article.description).lower()
    matched: list[str] = []

    if any(kw in text for kw in _RARE_MELANOMA_KEYWORDS):
        matched.append("Uveal Melanoma")
        matched.append("Acral Melanoma")
        matched.append("Mucosal Melanoma")
    else:
        if any(kw in text for kw in _UVEAL_KEYWORDS):
            matched.append("Uveal Melanoma")
        if any(kw in text for kw in _ACRAL_KEYWORDS):
            matched.append("Acral Melanoma")
        if any(kw in text for kw in _MUCOSAL_KEYWORDS):
            matched.append("Mucosal Melanoma")

    has_melanoma = "melanoma" in text
    has_brain_cns = any(kw in text for kw in _BRAIN_CNS_KEYWORDS) or (
        has_melanoma
        and any(
            kw in text
            for kw in [
                "brain metastasis",
                "brain-metastatic",
                "cns metastasis",
                "brain met",
                "intracranial",
            ]
        )
    )
    if has_brain_cns:
        matched.append("Cutaneous Melanoma with Brain/CNS Metastasis")

    _non_cutaneous_subtypes = {"Uveal Melanoma", "Acral Melanoma", "Mucosal Melanoma"}
    has_non_cutaneous_subtype = bool(set(matched) & _non_cutaneous_subtypes)
    if has_melanoma and (not has_non_cutaneous_subtype or "cutaneous" in text):
        matched.append("Cutaneous Melanoma")

    if any(kw in text for kw in _CSCC_KEYWORDS):
        matched.append("Cutaneous Squamous Cell Carcinoma")
    if any(kw in text for kw in _BCC_KEYWORDS):
        matched.append("Basal Cell Carcinoma")
    if any(kw in text for kw in _MCC_KEYWORDS):
        matched.append("Merkel Cell Carcinoma")

    return list(dict.fromkeys(matched))  # Remove duplicates, preserve order
