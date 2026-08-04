"""Unit tests for the modality vocabulary and the modality-only extraction path.

The vocabulary is the gate: `TrialParameterExtractor` filters LLM output through
`MODALITY_VALUES`, so a value the prompt teaches but the list does not contain is
dropped and the run looks clean while producing nothing. These tests pin the two
sides together.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.app.trials_parameter_extraction_service import TrialParameterExtractor
from src.domain.trial_parameter_models import ExtractionStatus, TrialText
from src.domain.trials_extraction_prompts import (
    _MODALITY_FIELD,
    MODALITY_VALUES,
    build_extraction_prompt,
    build_modality_prompt,
)
from src.infrastructure.clinical_trials.repository import (
    _MODALITY_HEADERS,
    _MODALITY_OTHER,
)

_NEW_VALUES = [
    "Radiotherapy",
    "Surgery/Procedure",
    "Device",
    "Cell Therapy",
    "Photodynamic Therapy",
    "Radiopharmaceutical",
    "Gene Therapy",
]

# The second round of additions. Kept separate from _NEW_VALUES so each list
# still names the backfill it was added for.
_V2_VALUES = [
    "Imaging/Diagnostic Agent",
    "Protein/Peptide Therapeutic",
    "Dietary/Microbiome",
    "Behavioral/Digital Health",
]

_TRIAL = TrialText(
    nct_number="NCT00000001",
    official_title="Radiotherapy for cutaneous melanoma",
    brief_summary="Patients receive external beam radiotherapy.",
    full_text=(
        "NCT Number: NCT00000001\n\n"
        "primaryPurpose: TREATMENT\n\n"
        "officialTitle:\nRadiotherapy for cutaneous melanoma\n\n"
        "interventions:\n- RADIATION - External beam radiotherapy\n"
    ),
)


class _FakeLLM:
    """Records the prompt it was given and returns a canned payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.prompt: str = ""
        self.attribute_type: str | None = None

    async def extract_json(
        self,
        prompt: str,
        operation: str = "extraction",
        attribute_type: str | None = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        self.prompt = prompt
        self.attribute_type = attribute_type
        return self._payload


# --- vocabulary -------------------------------------------------------------


def test_new_modality_values_present() -> None:
    """The seven additions the backfill depends on are in the vocabulary."""
    for value in _NEW_VALUES:
        assert value in MODALITY_VALUES


def test_v2_modality_values_present() -> None:
    """The four additions the second backfill depends on are in the vocabulary."""
    for value in _V2_VALUES:
        assert value in MODALITY_VALUES


def test_repository_headers_match_the_vocabulary() -> None:
    """`repository.py` re-declares the vocabulary by hand for column ordering.

    The two lists have drifted before, which folds a real class into Other on the
    dashboard while extraction keeps producing it.
    """
    assert list(_MODALITY_HEADERS) == [v for v in MODALITY_VALUES if v != "Other"]
    assert _MODALITY_OTHER == "Other"


def test_modality_values_survive_the_column_encoding() -> None:
    """`modality` is a '; '-joined column the frontend splits on /[;,]/.

    A value containing either delimiter would be torn in half on the way back
    out, so neither may appear.
    """
    for value in MODALITY_VALUES:
        assert ";" not in value
        assert "," not in value


def test_modality_values_unique() -> None:
    assert len(MODALITY_VALUES) == len(set(MODALITY_VALUES))


# --- prompt content ---------------------------------------------------------


def test_extraction_prompt_offers_every_modality_value() -> None:
    prompt = build_extraction_prompt(_TRIAL.full_text)
    for value in MODALITY_VALUES:
        assert f"  - {value}" in prompt


def test_modality_prompt_offers_every_modality_value() -> None:
    prompt = build_modality_prompt(_TRIAL.full_text)
    for value in MODALITY_VALUES:
        assert f"  - {value}" in prompt


def test_both_prompts_share_one_modality_section() -> None:
    """The two runs must classify by identical rules or their output is not
    comparable, so the section is defined once and injected into both."""
    assert _MODALITY_FIELD in build_extraction_prompt(_TRIAL.full_text)
    assert _MODALITY_FIELD in build_modality_prompt(_TRIAL.full_text)


def test_modality_prompt_omits_the_other_fields() -> None:
    prompt = build_modality_prompt(_TRIAL.full_text)
    for field in ("### biomarker", "### stage", "### line_of_therapy"):
        assert field not in prompt
    assert '"biomarker"' not in prompt


def test_prompts_route_radiation_and_procedure_away_from_other() -> None:
    """The old prompt sent RADIATION and PROCEDURE to Other by instruction."""
    prompt = " ".join(build_modality_prompt(_TRIAL.full_text).split())
    assert "RADIATION → Radiotherapy" in prompt
    assert "PROCEDURE → Surgery/Procedure" in prompt
    assert "RADIATION → Other" not in prompt
    assert "PROCEDURE → Other" not in prompt


def test_prompt_keeps_non_treatment_studies_in_scope() -> None:
    """Diagnostic and supportive-care trials do administer something.

    The earlier rule returned [] whenever primaryPurpose was not TREATMENT, which
    is what sent every PET tracer and diet arm to Other or NULL. The four v2
    values only reach the output if that rule stays relaxed.
    """
    prompt = " ".join(build_modality_prompt(_TRIAL.full_text).split())
    assert "DIAGNOSTIC, SCREENING, PREVENTION or SUPPORTIVE_CARE still gets a" in prompt
    assert "Return [] only when nothing is administered" in prompt


def test_prompt_grounds_each_v2_value_with_an_example() -> None:
    """A value listed but never exemplified is one the model will not pick."""
    prompt = " ".join(build_modality_prompt(_TRIAL.full_text).split())
    for value, example in (
        ("Imaging/Diagnostic Agent", "PET tracers"),
        ("Protein/Peptide Therapeutic", "denileukin"),
        ("Dietary/Microbiome", "faecal microbiota transplant"),
        ("Behavioral/Digital Health", "patient-facing apps"),
    ):
        assert value in prompt
        assert example in prompt


def test_modality_prompt_includes_trial_text() -> None:
    assert "External beam radiotherapy" in build_modality_prompt(_TRIAL.full_text)


# --- modality-only extraction ----------------------------------------------


@pytest.mark.asyncio
async def test_modality_only_populates_modality_and_nothing_else() -> None:
    llm = _FakeLLM(
        {
            "treatment_name": "External beam radiotherapy",
            "modality": ["Radiotherapy"],
            "biomarker": ["PD-L1"],
            "stage": ["Stage IV"],
        }
    )
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    result = await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert result.modality == ["Radiotherapy"]
    assert result.extraction_status == ExtractionStatus.DONE
    # treatment_name is kept as review context for the backfill diff.
    assert result.treatment_name == "External beam radiotherapy"
    # Fields the narrow run does not own stay empty even when the LLM volunteers
    # them - the stored values for these are already correct.
    assert result.biomarker == []
    assert result.stage == []
    assert result.line_of_therapy == []
    assert result.previous_treatment_criteria == []


@pytest.mark.asyncio
async def test_modality_only_uses_the_narrow_prompt() -> None:
    llm = _FakeLLM({"modality": ["Radiotherapy"]})
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert "### biomarker" not in llm.prompt
    assert llm.attribute_type == "modality"


@pytest.mark.asyncio
async def test_modality_only_sends_the_narrowed_trial_text() -> None:
    """Only the mechanism sections are paid for when the source can split them."""
    trial = TrialText(
        nct_number="NCT00000002",
        official_title="Study of Agent X",
        brief_summary="Agent X is given intravenously.",
        full_text="mechanism sections\neligibilityCriteria:\nprior ipilimumab\n",
        modality_text="mechanism sections\n",
    )
    llm = _FakeLLM({"modality": ["Small Molecule"]})
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    await extractor.extract(trial, ["Cutaneous Melanoma"])

    assert "mechanism sections" in llm.prompt
    assert "eligibilityCriteria" not in llm.prompt
    assert "ipilimumab" not in llm.prompt


@pytest.mark.asyncio
async def test_modality_only_falls_back_to_full_text() -> None:
    """The .txt loader cannot split sections and leaves modality_text empty."""
    llm = _FakeLLM({"modality": ["Radiotherapy"]})
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    assert _TRIAL.modality_text == ""
    await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert "External beam radiotherapy" in llm.prompt


@pytest.mark.asyncio
async def test_modality_only_drops_values_outside_the_vocabulary() -> None:
    llm = _FakeLLM({"modality": ["Radiotherapy", "Proton Beam"]})
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    result = await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert result.modality == ["Radiotherapy"]


@pytest.mark.parametrize("value", _V2_VALUES)
@pytest.mark.asyncio
async def test_v2_values_survive_the_vocabulary_filter(value: str) -> None:
    """Each new value must round-trip; the filter drops anything unknown."""
    llm = _FakeLLM({"treatment_name": "Agent", "modality": [value]})
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    result = await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert result.modality == [value]
    assert result.extraction_status == ExtractionStatus.DONE


@pytest.mark.asyncio
async def test_modality_only_keeps_repeats_for_combinations() -> None:
    """One value per agent: a two-antibody regimen answers twice, and that arity
    is the answer. Consumers collapse repeats for display, so the extractor must
    not throw the information away."""
    llm = _FakeLLM(
        {
            "treatment_name": "Nivolumab + Ipilimumab",
            "modality": ["Monoclonal Antibody", "Monoclonal Antibody"],
        }
    )
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    result = await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert result.modality == ["Monoclonal Antibody", "Monoclonal Antibody"]


@pytest.mark.asyncio
async def test_modality_only_empty_result_is_partial_not_done() -> None:
    """An empty modality means "could not tell"; the backfill must not treat it
    as an answer and overwrite the stored value."""
    llm = _FakeLLM({"treatment_name": None, "modality": []})
    extractor = TrialParameterExtractor(llm, modality_only=True)  # type: ignore[arg-type]

    result = await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert result.modality == []
    assert result.extraction_status == ExtractionStatus.PARTIAL


@pytest.mark.asyncio
async def test_full_extraction_unchanged_by_the_flag() -> None:
    llm = _FakeLLM(
        {
            "treatment_name": "Nivolumab",
            "modality": ["Monoclonal Antibody"],
            "biomarker": ["PD-L1"],
            "stage": ["Stage IV"],
            "line_of_therapy": [],
            "previous_treatment_criteria": [],
        }
    )
    extractor = TrialParameterExtractor(llm)  # type: ignore[arg-type]

    result = await extractor.extract(_TRIAL, ["Cutaneous Melanoma"])

    assert result.modality == ["Monoclonal Antibody"]
    assert result.biomarker == ["PD-L1"]
    assert result.stage == ["Stage IV"]
    assert llm.attribute_type == "all_parameters"
