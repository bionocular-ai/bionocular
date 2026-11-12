"""Prompt-shape tests for treatment arm separator. Behavioural fixture tests live in Task 3."""
from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator


def test_prompt_lists_negative_examples() -> None:
    p = TreatmentArmSeparator._create_separation_prompt().lower()
    for phrase in ["subgroup", "biomarker cohort", "dose-escalation"]:
        assert phrase in p, f"missing negative example: {phrase}"


def test_prompt_includes_line_of_treatment_field() -> None:
    p = TreatmentArmSeparator._create_separation_prompt()
    assert "line_of_treatment" in p
    # Spot-check one valid value is documented
    assert "first_line" in p


def test_prompt_includes_confidence_rubric() -> None:
    p = TreatmentArmSeparator._create_separation_prompt()
    # Three rubric anchors must appear
    assert "1.0" in p and "0.7" in p and "0.4" in p


def test_prompt_has_multi_arm_example() -> None:
    p = TreatmentArmSeparator._create_separation_prompt()
    # Worked example must show >= 3 arms
    assert p.count('"arm_id"') >= 3


def test_prompt_consolidates_rule_blocks() -> None:
    """Old prompt had 3 overlapping rule blocks. New one has a single RULES section."""
    p = TreatmentArmSeparator._create_separation_prompt()
    assert "CRITICAL REQUIREMENTS" not in p
    assert "CONSERVATIVE APPROACH" not in p
    assert "STRICT RESPONSE RULES" not in p
    assert "RULES:" in p


def test_prompt_keeps_abstract_text_placeholder() -> None:
    p = TreatmentArmSeparator._create_separation_prompt()
    assert "{abstract_text}" in p
