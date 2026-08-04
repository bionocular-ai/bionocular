"""Prompt templates for clinical trial parameter extraction.

Single-pass extraction per trial: one LLM call returns all parameters
in a single structured JSON response. The full trial text is provided so
the model has complete context for every field.

Extracted fields (dashboard group-by mapping)
--------------------------------------------
  treatment_name             — officialTitle + briefSummary context (not grouped)
  modality                   — linked to treatment_name; multi-value → Group by "Modality"
  biomarker                  — full trial text → Group by "Biomarker"
  stage                      — full trial text → Group by "Stage"
  line_of_therapy            — full trial text → Group by "Line of therapy"
  previous_treatment_criteria — full trial text → Group by "Previous treatment"

Serialization: list fields are joined with "; " in CSV/DB. Dashboard and
repository must split on semicolon (or comma) to assign trials to multiple
columns when a trial has multiple values (e.g. modality "Vaccine; Small Molecule").
Allowed values below are the single source of truth; frontend group-by labels
and backend categorization should use these vocabularies.
"""

# ---------------------------------------------------------------------------
# Allowed vocabulary constants (single source of truth for extraction and
# dashboard group-by: Stage, Modality, Biomarker, Line of therapy, Previous treatment)
# ---------------------------------------------------------------------------

MODALITY_VALUES = [
    "Monoclonal Antibody",
    "Vaccine",
    "Immunostimulant/Cytokine",
    "Bispecific",
    "CAR-T",
    "NK or Myeloid Cell Therapy",
    "TIL Therapy",
    "Small Molecule",
    "Antibody-Drug Conjugate",
    "Oncolytic Virus",
    "Chemotherapy",
    "Other",
]

BIOMARKER_VALUES = [
    "BRAF (V600)",
    "PD-L1",
    "HLA-A*02:01",
    "LAG-3",
    "TMB",
    "c-KIT",
    "NRAS",
    "NF1",
    "PRAME",
    "CDKN2A / CDK4",
    "MSI-H / dMMR",
    "GNAQ / GNA11",
    "SF3B1 / EIF1AX",
    "BAP1",
    "MCPyV",
    "PTCH1 / SMO",
    "PIK3CA",
    "EGFR",
    "ctDNA (MRD)",
    "MART-1",
    "gp100",
    "Other",
]

STAGE_VALUES = [
    "Stage I",
    "Stage I/II",
    "Stage II",
    "Stage II/III",
    "Stage III",
    "Stage III/IV",
    "Stage IV",
]

LINE_OF_THERAPY_VALUES = [
    "1L",
    "2L",
    "3L",
    "R/R",
    "Adjuvant",
    "Neoadjuvant",
]

PREVIOUS_TREATMENT_VALUES = [
    "Failed IO",
    "No prior BRAFi",
    "IO Naive",
]

# The eight skin-cancer indications this pipeline covers. Single source of truth
# for the extraction scoping rule and the validation judge's vocabulary. These
# strings match the cancer_type tags emitted by CT.gov discovery / Supabase
# verbatim, so the judge never flags a live tag as out-of-vocabulary.
CANCER_TYPE_VALUES = [
    "Cutaneous Melanoma",
    "Cutaneous Melanoma with Brain/CNS Metastasis",
    "Acral Melanoma",
    "Uveal Melanoma",
    "Mucosal Melanoma",
    "Cutaneous Squamous Cell Carcinoma",
    "Basal Cell Carcinoma",
    "Merkel Cell Carcinoma",
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a clinical oncology data curator specialising in melanoma and "
    "skin cancer clinical trials. Your task is to extract structured data "
    "from trial records with high precision. "
    "Return ONLY the JSON object requested — no prose, no markdown code "
    "fences, no explanations. If a value is not determinable from the "
    "provided text, use null for single values or an empty array [] for "
    "multi-value fields."
)

# ---------------------------------------------------------------------------
# Vocabulary lists (formatted for prompt injection)
# ---------------------------------------------------------------------------

_MODALITY_LIST = "\n".join(f"  - {v}" for v in MODALITY_VALUES)
_BIOMARKER_LIST = "\n".join(f"  - {v}" for v in BIOMARKER_VALUES)
_STAGE_LIST = "\n".join(f"  - {v}" for v in STAGE_VALUES)
_LOT_LIST = "\n".join(f"  - {v}" for v in LINE_OF_THERAPY_VALUES)
_PREV_TX_LIST = "\n".join(f"  - {v}" for v in PREVIOUS_TREATMENT_VALUES)
_CANCER_TYPE_INLINE = " | ".join(CANCER_TYPE_VALUES)

# ---------------------------------------------------------------------------
# Single extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_USER = """\
## Task
Extract all clinical trial parameters from the trial text below in a single pass.

---

## Global rule
This pipeline covers eight skin cancer indications:
  {cancer_type_inline}

Some trials enrol multiple tumour types (basket trials, pan-tumour studies).
When that is the case, extract every field exclusively from the eligibility
criteria that apply to the skin cancer indication listed above. Discard any
requirements that belong to other tumour types (e.g. NSCLC, RCC, HNSCC,
colorectal, bladder). If a criterion is shared across all cohorts (e.g. ECOG
performance status), it is valid to use it.

---

## Field instructions

### treatment_name
The novel drug or drug combination that is the central subject of this trial.
Use the interventions section as the primary signal for the drug name(s), cross-
checked against the officialTitle and briefSummary. The interventions list is the
authoritative set of agents administered in the trial; titles and summaries may
omit, abbreviate, or use code names.

Ignore intervention entries that are not the investigational treatment: placebo,
best supportive care, sham, and diagnostic/imaging procedures. A comparator-arm
drug is not the treatment_name either (apply the single-agent rule below).

When an agent appears under several names (a development code, a brand name, and a
generic/INN name), prefer the generic (INN) name (e.g. gefitinib over "Iressa" or
"ZD1839"). Keep the code only when no generic name is available (unnamed
investigational agents).

Single agent: return the investigational drug name only — not the comparator.
  - Example: "Drug X vs. Nivolumab" → "Drug X"
  - Example: "Pembrolizumab vs. Dacarbazine" → "Pembrolizumab"
    (pembrolizumab is the investigational agent here; dacarbazine is the comparator)

Combination: if the trial tests two or more agents together as the
investigational regimen, return them joined with " + ".
  - Example: "V940 + Pembrolizumab vs. Pembrolizumab" → "V940 + Pembrolizumab"
    (pembrolizumab alone is the comparator; the combination is investigational)
  - Example: "Nivolumab + Relatlimab FDC" → "Nivolumab + Relatlimab"

Return null only if the treatment cannot be identified from the title or summary.

### modality
Choose the modality value(s) that best describe the mechanism of treatment_name.
- For a single agent return one value; for a combination return one per agent.
- Prefer the most specific match over "Other".
- Use "Other" only if the mechanism is identifiable but fits none of the
  specific categories (e.g. radiation, photodynamic therapy).
- Return [] if the mechanism is completely unidentifiable.
- Use the intervention `type` from the interventions section as a prior, not a
  final answer: GENETIC → CAR-T or TIL Therapy; PROCEDURE → Other (e.g. surgery);
  RADIATION → Other; DRUG → usually Small Molecule or Chemotherapy; BIOLOGICAL →
  an immunotherapy class (Monoclonal Antibody, Vaccine, Immunostimulant/Cytokine,
  Bispecific, Oncolytic Virus). The type narrows the options; decide the exact
  class from the drug name and mechanism, since type is not one-to-one.

Reference examples (modality → example drug):
  Monoclonal Antibody        → Pembrolizumab (PD-1), Nivolumab, Ipilimumab
  Vaccine                    → V940 (mRNA-4157), mRNA vaccines, plasmid DNA,
                               viral-vector immunotherapies
  Immunostimulant/Cytokine   → Aldesleukin (IL-2), interferons, interleukins
  Bispecific                 → Tebentafusp, bispecific antibodies
  CAR-T                      → IL13Ra2 CAR-T, CD19 CAR-T
  NK or Myeloid Cell Therapy → iNKT cell therapy, NK cell therapy
  TIL Therapy                → Lifileucel, autologous TIL infusion
  Small Molecule             → SX-682 (CXCR1/2 inhibitor), vemurafenib,
                               dabrafenib, trametinib
  Antibody-Drug Conjugate    → Ozuriftamab vedotin, HER3 ADC
  Oncolytic Virus            → Talimogene laherparepvec (Imlygic), T-VEC
  Chemotherapy               → Dacarbazine, Temozolomide, carboplatin
  Other                      → radiation, photodynamic therapy, adoptive cell
                               therapy not covered by CAR-T / TIL / NK

Combination example: "V940 + Pembrolizumab" → ["Vaccine", "Monoclonal Antibody"]
Allowed modality values:
{modality_list}

### biomarker
Tag a biomarker only when the trial requires patients to have a specific
molecular status to enrol or be assigned to a treatment arm:
  - Required as an inclusion criterion: e.g. "BRAF V600E-positive tumour",
    "NRAS mutant", "c-KIT amplified", "PD-L1 TPS ≥ 1%"
  - Used for mandatory cohort stratification or treatment assignment

Do not tag a biomarker when:
  - It is the target of the drug mechanism. A drug targeting a molecule does
    not mean the patient must carry that alteration.
      e.g. Relatlimab targets LAG-3 → do NOT tag "LAG-3"
           Ipilimumab targets CTLA-4 → do NOT tag "CTLA-4"
           Pembrolizumab targets PD-1 → do NOT tag "PD-L1" unless expression
           level (CPS, TPS, IHC score) is an explicit eligibility requirement
  - It is assessed as an exploratory, correlative, or secondary endpoint only
  - The requirement applies only to a non-skin-cancer cohort in a basket trial

A trial may have zero, one, or many biomarkers. Return ONLY values from the
allowed list. Use "Other" only when an unlisted biomarker clearly meets the
inclusion/stratification criteria above.
Allowed biomarker classes:
{biomarker_list}

### stage
The disease stage(s) this trial targets, based on AJCC staging language \
in the eligibility criteria. Map to the allowed values below.
  Explicit "Stage I" or early-stage only              → "Stage I"
  Spans Stage I and II                                → "Stage I/II"
  Explicit "Stage II" only                            → "Stage II"
  Spans Stage II and III                              → "Stage II/III"
  "Stage III" / "resected" / "unresectable"           → "Stage III"
  Spans Stage III and IV                              → "Stage III/IV"
  "Stage IV" / "metastatic" / "advanced"              → "Stage IV"
Do NOT infer stage from line_of_therapy context (e.g. "adjuvant" or \
"neoadjuvant" alone does not determine stage — look for the explicit AJCC \
stage in the eligibility criteria). A trial may apply to more than one stage \
range. Return only values from:
{stage_list}

### line_of_therapy
How many prior systemic treatments were required for eligibility. Apply \
these rules in order — the first match wins:
  1. If the trial explicitly describes a post-surgery setting to prevent
     recurrence (adjuvant)                           → "Adjuvant"
  2. If the trial explicitly describes treatment before a planned operation
     (neoadjuvant)                                   → "Neoadjuvant"
  3. If the trial uses "relapsed", "refractory", "failed", "progressed",
     or "R/R" language — even if a specific line count is also mentioned
     — prefer                                        → "R/R"
  4. "treatment-naïve" / "no prior systemic therapy" → "1L"
  5. "≥1 prior line" / "1 prior therapy" (without
     refractory language)                            → "2L"
  6. "≥2 prior lines" (without refractory language)  → "3L"
A trial may qualify for more than one value (e.g. both "Adjuvant" and \
"Neoadjuvant" if it has both arms). Return only values from:
{lot_list}

### previous_treatment_criteria
Specific prior-treatment eligibility constraints based on inclusion criteria \
only. Apply ALL that match:
  Prior anti-PD-1 / anti-PD-L1 / ICI was required
  as a positive inclusion criterion (e.g. "must have
  progressed on", "prior anti-PD-1 required")        → "Failed IO"
  "No prior BRAFi" / "BRAF inhibitor naive" stated
  as a positive inclusion criterion                  → "No prior BRAFi"
  "IO naive" / "immunotherapy naive" / "no prior
  checkpoint inhibitor" stated as a positive
  inclusion criterion                                → "IO Naive"
Note: only tag these from inclusion criteria text. Do not infer them from \
the absence of a requirement.
Return only values from:
{prev_tx_list}

---

## Trial text
{full_text}

---

## Output
Return valid JSON only, with exactly these keys:
{{
  "treatment_name": "string or null",
  "modality": [],
  "biomarker": [],
  "stage": [],
  "line_of_therapy": [],
  "previous_treatment_criteria": []
}}\
"""

# ---------------------------------------------------------------------------
# Public builder function
# ---------------------------------------------------------------------------


def build_extraction_prompt(full_text: str) -> str:
    """Return the single-pass extraction prompt for a trial.

    Args:
        full_text: Complete trial text (all sections, including officialTitle
            and briefSummary which are used for treatment_name and modality).

    Returns:
        Complete prompt string (system + user) ready to send to the LLM.
    """
    user = _EXTRACTION_USER.format(
        cancer_type_inline=_CANCER_TYPE_INLINE,
        modality_list=_MODALITY_LIST,
        biomarker_list=_BIOMARKER_LIST,
        stage_list=_STAGE_LIST,
        lot_list=_LOT_LIST,
        prev_tx_list=_PREV_TX_LIST,
        full_text=full_text.strip(),
    )
    return f"{_SYSTEM_PROMPT}\n\n{user}"
