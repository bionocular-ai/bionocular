"""Tests for family-grouped extraction prompts (Task 4)."""
from src.domain.extraction_models import FAMILY_TO_ATTRIBUTES, AttributeFamily
from src.domain.prompt_templates import FAMILY_PROMPTS, SHARED_EXTRACTION_RULES


def test_every_family_has_a_prompt() -> None:
    for fam in AttributeFamily:
        assert fam in FAMILY_PROMPTS, f"missing prompt for {fam}"


def test_ae_definition_in_ae_teae_trae_prompts() -> None:
    for fam in [
        AttributeFamily.AE_GENERAL,
        AttributeFamily.AE_GRADE3_SPECIFIC,
        AttributeFamily.TEAE_GENERAL,
        AttributeFamily.TEAE_GRADE3_SPECIFIC,
        AttributeFamily.TRAE_GENERAL,
        AttributeFamily.TRAE_GRADE3_SPECIFIC,
    ]:
        p = FAMILY_PROMPTS[fam]
        assert "Treatment-Emergent" in p and "Treatment-Related" in p


def test_no_inference_clause_present() -> None:
    for p in FAMILY_PROMPTS.values():
        assert "do not infer" in p.lower() or "do not compute" in p.lower()


def test_orr_fallback_only_in_response_rates() -> None:
    rr = FAMILY_PROMPTS[AttributeFamily.RESPONSE_RATES]
    assert "(CR + PR)" in rr or "CR + PR" in rr
    assert "SANCTIONED EXCEPTION" in rr
    for fam, p in FAMILY_PROMPTS.items():
        if fam != AttributeFamily.RESPONSE_RATES:
            assert "SANCTIONED EXCEPTION" not in p


def test_shared_rules_not_inlined() -> None:
    for p in FAMILY_PROMPTS.values():
        assert SHARED_EXTRACTION_RULES not in p


def test_arms_block_placeholder_in_every_prompt() -> None:
    for fam, p in FAMILY_PROMPTS.items():
        assert "{arms_block}" in p, f"missing {{arms_block}} in {fam}"


def test_each_prompt_under_700_words() -> None:
    for fam, p in FAMILY_PROMPTS.items():
        wc = len(p.split())
        assert wc <= 700, f"{fam} prompt too long: {wc} words"


def test_ci_hr_prompts_demand_range_not_single_value() -> None:
    for fam in [
        AttributeFamily.PFS_FAMILY,
        AttributeFamily.OS_FAMILY,
        AttributeFamily.EFS_RFS_MFS,
        AttributeFamily.TIME_TO_METRICS,
    ]:
        p = FAMILY_PROMPTS[fam]
        assert "two decimals" in p.lower(), f"{fam} missing 'two decimals'"
        assert "low-high" in p, f"{fam} missing 'low-high'"
        assert "Never return only one number" in p, f"{fam} missing single-number ban"


def test_no_cross_family_attribute_leakage() -> None:
    """TEAE prompt must not mention TRAE attrs and vice versa.

    Prevents the LLM from being asked to extract attrs from the wrong family.
    The shared DEFINITIONS block legitimately mentions all three terms; we
    skip it by splitting on the 'Scope of THIS family:' marker that follows
    the definitions block in every safety-family prompt.
    """
    safety_families = [
        AttributeFamily.AE_GENERAL,
        AttributeFamily.AE_GRADE3_SPECIFIC,
        AttributeFamily.TEAE_GENERAL,
        AttributeFamily.TEAE_GRADE3_SPECIFIC,
        AttributeFamily.TRAE_GENERAL,
        AttributeFamily.TRAE_GRADE3_SPECIFIC,
    ]
    marker = "Scope of THIS family:"
    for fam in safety_families:
        prompt = FAMILY_PROMPTS[fam]
        assert marker in prompt, f"{fam} missing scope marker"
        post_definitions = prompt.split(marker, 1)[1]
        fam_name = fam.value  # e.g. "teae_general", "trae_grade3_specific"
        if fam_name.startswith("teae"):
            assert (
                "trae_" not in post_definitions
            ), f"{fam} prompt leaks trae_* attrs after definitions block"
        elif fam_name.startswith("trae"):
            assert (
                "teae_" not in post_definitions
            ), f"{fam} prompt leaks teae_* attrs after definitions block"
        else:  # ae_*
            assert (
                "trae_" not in post_definitions
            ), f"{fam} prompt leaks trae_* attrs after definitions block"
            assert (
                "teae_" not in post_definitions
            ), f"{fam} prompt leaks teae_* attrs after definitions block"


def test_trae_general_has_single_arm_relabel_clause() -> None:
    p = FAMILY_PROMPTS[AttributeFamily.TRAE_GENERAL]
    assert "single-arm" in p.lower() or "Phase 1" in p
    assert (
        "all AEs were considered treatment-related" in p
        or "all adverse events were considered" in p.lower()
    )


def test_followup_families_reject_landmarks_and_endpoint_medians() -> None:
    """A '5-year RFS' landmark and a median RFS both got stored as follow-up length."""
    for fam in [
        AttributeFamily.PFS_FAMILY,
        AttributeFamily.OS_FAMILY,
        AttributeFamily.EFS_RFS_MFS,
        AttributeFamily.TIME_TO_METRICS,
    ]:
        p = FAMILY_PROMPTS[fam]
        assert "LANDMARK LABEL" in p, f"{fam} prompt lets a landmark become follow-up"
        assert (
            "ENDPOINT'S OWN MEDIAN" in p
        ), f"{fam} prompt confuses median with follow-up"


def test_efs_rfs_mfs_states_it_has_no_rate_fields() -> None:
    """Only OS and PFS have *_rate_* columns, so an RFS landmark rate has no home."""
    p = FAMILY_PROMPTS[AttributeFamily.EFS_RFS_MFS]
    assert "NO rate fields" in p
    assert "rfs_rate_" in p


def test_efs_rfs_mfs_has_non_substitution_rule() -> None:
    p = FAMILY_PROMPTS[AttributeFamily.EFS_RFS_MFS]
    assert "never copy" in p.lower() or "do not substitute" in p.lower()
    assert "PFS" in p and "OS" in p


def test_grade3_specific_attributes_in_family_to_attributes() -> None:
    """R1 attributes added to prompts must also have slots in FAMILY_TO_ATTRIBUTES."""
    expected = {
        AttributeFamily.AE_GRADE3_SPECIFIC: [
            "grade_3_plus_ae_neutrophil_count_decreased",
            "grade_3_plus_ae_wbc_decreased",
        ],
        AttributeFamily.TEAE_GRADE3_SPECIFIC: [
            "grade_3_plus_teae_neutrophil_count_decreased",
            "grade_3_plus_teae_wbc_decreased",
        ],
        AttributeFamily.TRAE_GRADE3_SPECIFIC: [
            "grade_3_plus_trae_neutrophil_count_decreased",
            "grade_3_plus_trae_wbc_decreased",
        ],
    }
    for fam, attrs in expected.items():
        registered = {a.value for a in FAMILY_TO_ATTRIBUTES[fam]}
        for full_name in attrs:
            assert (
                full_name in registered
            ), f"{full_name} listed in {fam.name} prompt but absent from FAMILY_TO_ATTRIBUTES"
