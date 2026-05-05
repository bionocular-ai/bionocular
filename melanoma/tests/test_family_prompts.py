"""Tests for family-grouped extraction prompts (Task 4)."""
from src.domain.extraction_models import AttributeFamily
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
    assert "computed_orr" in rr
    for fam, p in FAMILY_PROMPTS.items():
        if fam != AttributeFamily.RESPONSE_RATES:
            assert "computed_orr" not in p


def test_shared_rules_not_inlined() -> None:
    for p in FAMILY_PROMPTS.values():
        assert SHARED_EXTRACTION_RULES not in p


def test_arms_block_placeholder_in_every_prompt() -> None:
    for fam, p in FAMILY_PROMPTS.items():
        assert "{arms_block}" in p, f"missing {{arms_block}} in {fam}"


def test_each_prompt_under_400_words() -> None:
    for fam, p in FAMILY_PROMPTS.items():
        wc = len(p.split())
        assert wc <= 400, f"{fam} prompt too long: {wc} words"
