#!/usr/bin/env python3
"""Unit tests for drug_knowledge canonicalization and drug_enricher."""

import logging

from src.domain.drug_knowledge import (
    canonicalize,
    get_drug_info,
    get_modality,
    get_target,
)
from src.domain.extraction_models import AttributeType
from src.domain.treatment_arm_models import TreatmentArmExtractionResult
from src.infrastructure.drug_enricher import enrich_result

# ---- canonicalize ---------------------------------------------------------


def test_canonicalize_brand() -> None:
    assert canonicalize("Opdivo") == "Nivolumab"


def test_canonicalize_dev_code() -> None:
    assert canonicalize("BMS-936558") == "Nivolumab"


def test_canonicalize_combo() -> None:
    assert canonicalize("Nivolumab + Ipilimumab") == "Nivolumab + Ipilimumab"


def test_canonicalize_combo_with_brands() -> None:
    assert canonicalize("Opdivo + Yervoy") == "Nivolumab + Ipilimumab"


def test_canonicalize_unknown_passthrough() -> None:
    assert canonicalize("FoobarMab") == "FoobarMab"


def test_canonicalize_empty() -> None:
    assert canonicalize("") == ""
    assert canonicalize("   ") == ""


def test_canonicalize_case_insensitive() -> None:
    assert canonicalize("pembrolizumab") == "Pembrolizumab"
    assert canonicalize("KEYTRUDA") == "Pembrolizumab"


# ---- get_modality / get_target -------------------------------------------


def test_get_modality_pembrolizumab() -> None:
    assert get_modality("Pembrolizumab") == "Antibody"


def test_get_target_pembrolizumab() -> None:
    assert get_target("Pembrolizumab") == "PD-1"


def test_get_modality_dabrafenib_trametinib_dedupe() -> None:
    # both Small Molecule → dedupe to one entry
    assert get_modality("Dabrafenib + Trametinib") == "Small Molecule"


def test_get_target_dabrafenib_trametinib_preserve() -> None:
    # targets differ; preserve order
    assert get_target("Dabrafenib + Trametinib") == "BRAF + MEK"


def test_get_modality_nivo_ipi() -> None:
    # both Antibody → dedupe
    assert get_modality("Nivolumab + Ipilimumab") == "Antibody"


def test_get_target_nivo_ipi() -> None:
    assert get_target("Nivolumab + Ipilimumab") == "PD-1 + CTLA-4"


def test_placebo() -> None:
    assert get_modality("Placebo") == "Inert"
    assert get_target("Placebo") == ""


def test_observation() -> None:
    assert canonicalize("obs") == "Observation"
    assert get_modality("Observation") == "Procedure"
    assert get_target("Observation") == ""


def test_unknown_returns_empty() -> None:
    assert get_modality("FoobarMab") == ""
    assert get_target("FoobarMab") == ""


def test_get_drug_info() -> None:
    info = get_drug_info("Tafinlar")
    assert info is not None
    assert info.canonical == "Dabrafenib"
    assert info.modality == "Small Molecule"
    assert info.target == "BRAF"


def test_get_drug_info_combo_returns_none() -> None:
    assert get_drug_info("Nivolumab + Ipilimumab") is None


def test_get_drug_info_unknown() -> None:
    assert get_drug_info("FoobarMab") is None


def test_til_lifileucel_known() -> None:
    info = get_drug_info("Amtagvi")
    assert info is not None
    assert info.canonical == "Lifileucel"
    assert info.modality == "Cell Therapy"


# ---- enricher ------------------------------------------------------------


def _make_result(arm_results: dict) -> TreatmentArmExtractionResult:
    return TreatmentArmExtractionResult(
        abstract_id="abs-1",
        arm_results=arm_results,
        overall_confidence=0.5,
        processing_time_ms=10,
    )


def test_enrich_replaces_arm_names_with_canonical() -> None:
    result = _make_result(
        {
            "arm-1": {
                "arm_id": "arm-1",
                "arm_name": "Opdivo",
                "generic_name": "Opdivo",
                "combination_drugs": [],
                "attributes": {},
            }
        }
    )
    enriched = enrich_result(result)
    arm = enriched.arm_results["arm-1"]
    assert arm["arm_name"] == "Nivolumab"
    assert arm["generic_name"] == "Nivolumab"


def test_enrich_replaces_combination_drugs() -> None:
    result = _make_result(
        {
            "arm-1": {
                "arm_id": "arm-1",
                "arm_name": "Opdivo + Yervoy",
                "generic_name": "Nivolumab + Ipilimumab",
                "combination_drugs": ["Opdivo", "Yervoy"],
                "attributes": {},
            }
        }
    )
    enriched = enrich_result(result)
    arm = enriched.arm_results["arm-1"]
    assert arm["combination_drugs"] == ["Nivolumab", "Ipilimumab"]


def test_enrich_attaches_modality_and_target() -> None:
    result = _make_result(
        {
            "arm-1": {
                "arm_id": "arm-1",
                "arm_name": "Pembrolizumab",
                "generic_name": "Pembrolizumab",
                "combination_drugs": [],
                "attributes": {},
            }
        }
    )
    enriched = enrich_result(result)
    attrs = enriched.arm_results["arm-1"]["attributes"]
    assert AttributeType.MODALITY.value in attrs
    assert AttributeType.TARGET.value in attrs
    assert attrs[AttributeType.MODALITY.value]["value"] == "Antibody"
    assert attrs[AttributeType.TARGET.value]["value"] == "PD-1"
    assert attrs[AttributeType.MODALITY.value]["source"] == "drug_knowledge"
    assert attrs[AttributeType.TARGET.value]["source"] == "drug_knowledge"


def test_enrich_combo_arm_dedupes_modality_preserves_target() -> None:
    result = _make_result(
        {
            "arm-1": {
                "arm_id": "arm-1",
                "arm_name": "Dabrafenib + Trametinib",
                "generic_name": "Dabrafenib + Trametinib",
                "combination_drugs": ["Dabrafenib", "Trametinib"],
                "attributes": {},
            }
        }
    )
    enriched = enrich_result(result)
    attrs = enriched.arm_results["arm-1"]["attributes"]
    assert attrs[AttributeType.MODALITY.value]["value"] == "Small Molecule"
    assert attrs[AttributeType.TARGET.value]["value"] == "BRAF + MEK"


def test_enrich_handles_unknown_drug_logs_warning(
    caplog: "logging.LogCaptureFixture",
) -> None:
    result = _make_result(
        {
            "arm-1": {
                "arm_id": "arm-1",
                "arm_name": "FoobarMab",
                "generic_name": "FoobarMab",
                "combination_drugs": [],
                "attributes": {},
            }
        }
    )
    with caplog.at_level(logging.WARNING, logger="src.infrastructure.drug_enricher"):
        enriched = enrich_result(result)
    arm = enriched.arm_results["arm-1"]
    # canonicalize passes unknowns through unchanged
    assert arm["arm_name"] == "FoobarMab"
    # modality/target empty
    assert arm["attributes"][AttributeType.MODALITY.value]["value"] == ""
    assert arm["attributes"][AttributeType.TARGET.value]["value"] == ""
    # warning logged
    assert any(
        "FoobarMab" in record.message and record.levelno == logging.WARNING
        for record in caplog.records
    )


def test_enrich_handles_missing_attributes_field() -> None:
    result = _make_result(
        {
            "arm-1": {
                "arm_id": "arm-1",
                "arm_name": "Nivolumab",
                "generic_name": "Nivolumab",
                "combination_drugs": [],
                # no "attributes" key
            }
        }
    )
    enriched = enrich_result(result)
    attrs = enriched.arm_results["arm-1"]["attributes"]
    assert attrs[AttributeType.MODALITY.value]["value"] == "Antibody"


def test_enrich_handles_empty_arm_results() -> None:
    result = _make_result({})
    enriched = enrich_result(result)
    assert enriched.arm_results == {}


def test_enrich_handles_missing_generic_name_falls_back_to_arm_name() -> None:
    result = _make_result(
        {
            "arm-1": {
                "arm_id": "arm-1",
                "arm_name": "Pembrolizumab",
                # no generic_name
                "combination_drugs": [],
                "attributes": {},
            }
        }
    )
    enriched = enrich_result(result)
    attrs = enriched.arm_results["arm-1"]["attributes"]
    assert attrs[AttributeType.MODALITY.value]["value"] == "Antibody"
    assert attrs[AttributeType.TARGET.value]["value"] == "PD-1"
