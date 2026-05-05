"""Drug knowledge base for melanoma / skin-cancer corpus.

Pure domain module: dataclass + dict lookups + canonicalization helpers.
No I/O, no infrastructure dependencies.

Provides:
    - DrugInfo: (canonical, modality, target) triple per drug.
    - DRUG_KB: canonical-keyed knowledge base.
    - SYNONYMS: brand names / development codes mapped to canonical KB keys.
    - canonicalize / get_modality / get_target / get_drug_info functions
      that handle "+" combination strings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DrugInfo:
    """Static knowledge about a single drug or intervention."""

    canonical: str
    modality: str  # Small Molecule | Antibody | ADC | TCR | Cell Therapy | Vaccine | Oncolytic Virus | Procedure | Inert
    target: str  # PD-1 | PD-L1 | CTLA-4 | BRAF | MEK | LAG-3 | ... | "" for placebo/obs


# Knowledge base keyed by canonical drug name (lowercase lookup, original casing preserved in DrugInfo).
DRUG_KB: dict[str, DrugInfo] = {
    # --- Checkpoint inhibitors (anti PD-1 / PD-L1 / CTLA-4 / LAG-3) ---
    "nivolumab": DrugInfo("Nivolumab", "Antibody", "PD-1"),
    "pembrolizumab": DrugInfo("Pembrolizumab", "Antibody", "PD-1"),
    "cemiplimab": DrugInfo("Cemiplimab", "Antibody", "PD-1"),
    "ipilimumab": DrugInfo("Ipilimumab", "Antibody", "CTLA-4"),
    "tremelimumab": DrugInfo("Tremelimumab", "Antibody", "CTLA-4"),
    "atezolizumab": DrugInfo("Atezolizumab", "Antibody", "PD-L1"),
    "durvalumab": DrugInfo("Durvalumab", "Antibody", "PD-L1"),
    "avelumab": DrugInfo("Avelumab", "Antibody", "PD-L1"),
    "relatlimab": DrugInfo("Relatlimab", "Antibody", "LAG-3"),
    # --- MAPK pathway (BRAF / MEK inhibitors) ---
    "dabrafenib": DrugInfo("Dabrafenib", "Small Molecule", "BRAF"),
    "vemurafenib": DrugInfo("Vemurafenib", "Small Molecule", "BRAF"),
    "encorafenib": DrugInfo("Encorafenib", "Small Molecule", "BRAF"),
    "trametinib": DrugInfo("Trametinib", "Small Molecule", "MEK"),
    "cobimetinib": DrugInfo("Cobimetinib", "Small Molecule", "MEK"),
    "binimetinib": DrugInfo("Binimetinib", "Small Molecule", "MEK"),
    "tunlametinib": DrugInfo("Tunlametinib", "Small Molecule", "MEK"),
    # --- Other targeted therapies (KIT, multi-kinase) ---
    "imatinib": DrugInfo("Imatinib", "Small Molecule", "KIT"),
    "sorafenib": DrugInfo("Sorafenib", "Small Molecule", "multi-kinase"),
    "sunitinib": DrugInfo("Sunitinib", "Small Molecule", "multi-kinase"),
    "lenvatinib": DrugInfo("Lenvatinib", "Small Molecule", "multi-kinase"),
    # --- TCR / cell therapy ---
    "tebentafusp": DrugInfo("Tebentafusp", "TCR", "gp100"),
    "lifileucel": DrugInfo("Lifileucel", "Cell Therapy", "tumor-infiltrating"),
    # --- Oncolytic virus ---
    "talimogene laherparepvec": DrugInfo(
        "Talimogene Laherparepvec", "Oncolytic Virus", "HSV-1/GM-CSF"
    ),
    # --- Cytokines ---
    "interferon alfa-2b": DrugInfo("Interferon Alfa-2b", "Cytokine", "IFN-alpha"),
    "interleukin-2": DrugInfo("Interleukin-2", "Cytokine", "IL-2"),
    "bempegaldesleukin": DrugInfo("Bempegaldesleukin", "Cytokine", "IL-2"),
    # --- Vaccines (personalized neoantigen mRNA) ---
    "mrna-4157": DrugInfo("mRNA-4157", "Vaccine", "personalized neoantigen"),
    "bnt122": DrugInfo("BNT122", "Vaccine", "personalized neoantigen"),
    # --- Chemotherapy (legacy melanoma backbone) ---
    "dacarbazine": DrugInfo("Dacarbazine", "Small Molecule", "DNA alkylation"),
    "temozolomide": DrugInfo("Temozolomide", "Small Molecule", "DNA alkylation"),
    "fotemustine": DrugInfo("Fotemustine", "Small Molecule", "DNA alkylation"),
    "carmustine": DrugInfo("Carmustine", "Small Molecule", "DNA alkylation"),
    "lomustine": DrugInfo("Lomustine", "Small Molecule", "DNA alkylation"),
    "paclitaxel": DrugInfo("Paclitaxel", "Small Molecule", "microtubule"),
    "nab-paclitaxel": DrugInfo("Nab-paclitaxel", "Small Molecule", "microtubule"),
    "vinblastine": DrugInfo("Vinblastine", "Small Molecule", "microtubule"),
    "carboplatin": DrugInfo("Carboplatin", "Small Molecule", "DNA crosslink"),
    "cisplatin": DrugInfo("Cisplatin", "Small Molecule", "DNA crosslink"),
    "doxorubicin": DrugInfo("Doxorubicin", "Small Molecule", "topoisomerase II"),
    # --- HER2 (rare melanoma but useful for skin-cancer corpus) ---
    "trastuzumab": DrugInfo("Trastuzumab", "Antibody", "HER2"),
    # --- ADC examples (skin-cancer adjacent) ---
    "enfortumab vedotin": DrugInfo("Enfortumab Vedotin", "ADC", "Nectin-4"),
    # --- Non-drug interventions ---
    "placebo": DrugInfo("Placebo", "Inert", ""),
    "observation": DrugInfo("Observation", "Procedure", ""),
    "surgery": DrugInfo("Surgery", "Procedure", ""),
    "radiotherapy": DrugInfo("Radiotherapy", "Procedure", ""),
    "clnd": DrugInfo("CLND", "Procedure", ""),
}


# Synonyms (brand names + development codes) → canonical KB key.
# Lookup is case-insensitive.
SYNONYMS: dict[str, str] = {
    # Nivolumab
    "opdivo": "nivolumab",
    "bms-936558": "nivolumab",
    "mdx-1106": "nivolumab",
    # Pembrolizumab
    "keytruda": "pembrolizumab",
    "mk-3475": "pembrolizumab",
    "lambrolizumab": "pembrolizumab",
    # Cemiplimab
    "libtayo": "cemiplimab",
    "regn2810": "cemiplimab",
    # Ipilimumab
    "yervoy": "ipilimumab",
    "mdx-010": "ipilimumab",
    "bms-734016": "ipilimumab",
    # Tremelimumab
    "imjudo": "tremelimumab",
    "cp-675206": "tremelimumab",
    # Atezolizumab
    "tecentriq": "atezolizumab",
    "mpdl3280a": "atezolizumab",
    # Durvalumab
    "imfinzi": "durvalumab",
    "medi4736": "durvalumab",
    # Avelumab
    "bavencio": "avelumab",
    "msb0010718c": "avelumab",
    # Relatlimab
    "opdualag": "relatlimab",  # combo brand (nivo+rela) — common shorthand
    "bms-986016": "relatlimab",
    # BRAF / MEK
    "tafinlar": "dabrafenib",
    "gsk2118436": "dabrafenib",
    "zelboraf": "vemurafenib",
    "plx4032": "vemurafenib",
    "braftovi": "encorafenib",
    "lgx818": "encorafenib",
    "mekinist": "trametinib",
    "gsk1120212": "trametinib",
    "cotellic": "cobimetinib",
    "gdc-0973": "cobimetinib",
    "mektovi": "binimetinib",
    "mek162": "binimetinib",
    # Tebentafusp / lifileucel
    "kimmtrak": "tebentafusp",
    "imcgp100": "tebentafusp",
    "amtagvi": "lifileucel",
    "ln-144": "lifileucel",
    # Oncolytic virus
    "t-vec": "talimogene laherparepvec",
    "imlygic": "talimogene laherparepvec",
    # Cytokines
    "intron a": "interferon alfa-2b",
    "ifn-alpha-2b": "interferon alfa-2b",
    "proleukin": "interleukin-2",
    "il-2": "interleukin-2",
    "aldesleukin": "interleukin-2",
    "nktr-214": "bempegaldesleukin",
    # Multi-kinase
    "nexavar": "sorafenib",
    "sutent": "sunitinib",
    "lenvima": "lenvatinib",
    "gleevec": "imatinib",
    "glivec": "imatinib",
    # Chemo brands
    "dtic": "dacarbazine",
    "temodar": "temozolomide",
    "temodal": "temozolomide",
    "muphoran": "fotemustine",
    "abraxane": "nab-paclitaxel",
    # Trastuzumab
    "herceptin": "trastuzumab",
    # ADC
    "padcev": "enfortumab vedotin",
    # Non-drug variants
    "obs": "observation",
    "watchful waiting": "observation",
    "active surveillance": "observation",
    "complete lymph node dissection": "clnd",
    "radiation therapy": "radiotherapy",
    "radiation": "radiotherapy",
    "rt": "radiotherapy",
}


def _lookup(name: str) -> DrugInfo | None:
    """Internal: case-insensitive lookup of a single (non-combo) drug name."""
    if not name:
        return None
    key = name.strip().lower()
    if not key:
        return None
    if key in DRUG_KB:
        return DRUG_KB[key]
    if key in SYNONYMS:
        return DRUG_KB.get(SYNONYMS[key])
    return None


def _split_combo(name: str) -> list[str]:
    """Split a combination string on '+' into trimmed parts."""
    return [p.strip() for p in name.split("+") if p.strip()]


def canonicalize(name: str) -> str:
    """Canonicalize a drug name (or '+'-separated combo) via DRUG_KB / SYNONYMS.

    Unknown tokens pass through unchanged. Empty input returns empty string.
    """
    if not name or not name.strip():
        return ""
    parts = _split_combo(name)
    if len(parts) > 1:
        return " + ".join(canonicalize(p) for p in parts)
    info = _lookup(name)
    if info is not None:
        return info.canonical
    return name.strip()


def get_modality(name: str) -> str:
    """Return modality for a drug or combo. Combos dedupe modality, preserve order.

    Unknown drugs contribute "" (filtered out). Empty input returns "".
    """
    if not name or not name.strip():
        return ""
    parts = _split_combo(name)
    if len(parts) > 1:
        seen: list[str] = []
        for p in parts:
            info = _lookup(p)
            mod = info.modality if info is not None else ""
            if mod and mod not in seen:
                seen.append(mod)
        return " + ".join(seen)
    info = _lookup(name)
    return info.modality if info is not None else ""


def get_target(name: str) -> str:
    """Return target for a drug or combo. Combos preserve duplicates and order.

    Unknown drugs contribute "" (filtered out). Empty input returns "".
    """
    if not name or not name.strip():
        return ""
    parts = _split_combo(name)
    if len(parts) > 1:
        targets: list[str] = []
        for p in parts:
            info = _lookup(p)
            tgt = info.target if info is not None else ""
            if tgt:
                targets.append(tgt)
        return " + ".join(targets)
    info = _lookup(name)
    return info.target if info is not None else ""


def get_drug_info(name: str) -> DrugInfo | None:
    """Return the DrugInfo for a single (non-combo) drug, or None if unknown."""
    if not name or "+" in name:
        return None
    return _lookup(name)
