"""Tests for AttributeFamily enum and FAMILY_TO_ATTRIBUTES map."""
from src.domain.extraction_models import (
    ABSTRACT_ATTRIBUTES,
    DERIVED_ATTRIBUTES,
    FAMILY_TO_ATTRIBUTES,
    PUBLICATION_ATTRIBUTES,
    SEPARATOR_SOURCED_ATTRIBUTES,
    AttributeFamily,
    AttributeType,
)


def test_every_extractable_publication_attribute_has_a_family() -> None:
    mapped = {a for attrs in FAMILY_TO_ATTRIBUTES.values() for a in attrs}
    extractable = set(PUBLICATION_ATTRIBUTES) - DERIVED_ATTRIBUTES - SEPARATOR_SOURCED_ATTRIBUTES
    missing = extractable - mapped
    assert not missing, f"unmapped extractable attrs: {missing}"


def test_every_extractable_abstract_attribute_has_a_family() -> None:
    mapped = {a for attrs in FAMILY_TO_ATTRIBUTES.values() for a in attrs}
    extractable = set(ABSTRACT_ATTRIBUTES) - DERIVED_ATTRIBUTES - SEPARATOR_SOURCED_ATTRIBUTES
    missing = extractable - mapped
    assert not missing, f"unmapped extractable abstract attrs: {missing}"


def test_no_attribute_in_two_families() -> None:
    seen: set[AttributeType] = set()
    for fam, attrs in FAMILY_TO_ATTRIBUTES.items():
        dup = seen & set(attrs)
        assert not dup, f"{fam}: {dup} already mapped to a previous family"
        seen.update(attrs)


def test_derived_attributes_not_in_any_family() -> None:
    for fam, attrs in FAMILY_TO_ATTRIBUTES.items():
        intersection = DERIVED_ATTRIBUTES & set(attrs)
        assert (
            not intersection
        ), f"{fam}: derived attrs must not be extracted by LLM, found {intersection}"


def test_os_family_membership() -> None:
    os_fam = FAMILY_TO_ATTRIBUTES[AttributeFamily.OS_FAMILY]
    assert AttributeType.MEDIAN_OS in os_fam
    assert AttributeType.OS_RATE_24M in os_fam
    assert AttributeType.HR_OS in os_fam
    assert AttributeType.CI_HR_OS in os_fam


def test_pfs_family_includes_rate_timepoints() -> None:
    pfs_fam = FAMILY_TO_ATTRIBUTES[AttributeFamily.PFS_FAMILY]
    assert AttributeType.MEDIAN_PFS in pfs_fam
    assert AttributeType.PFS_RATE_12M in pfs_fam


def test_ae_grade3_specific_has_at_least_20_attrs() -> None:
    """AE/TEAE/TRAE Grade 3+ specific blocks each contain a long list of named events (>=20)."""
    ae_g3 = FAMILY_TO_ATTRIBUTES[AttributeFamily.AE_GRADE3_SPECIFIC]
    teae_g3 = FAMILY_TO_ATTRIBUTES[AttributeFamily.TEAE_GRADE3_SPECIFIC]
    trae_g3 = FAMILY_TO_ATTRIBUTES[AttributeFamily.TRAE_GRADE3_SPECIFIC]
    # Each should contain at least 20 GRADE_3_PLUS_*_* attrs
    assert len(ae_g3) >= 20
    assert len(teae_g3) >= 20
    assert len(trae_g3) >= 20


def test_ae_general_includes_specific_aes() -> None:
    ae_gen = FAMILY_TO_ATTRIBUTES[AttributeFamily.AE_GENERAL]
    assert AttributeType.AE in ae_gen
    assert AttributeType.GRADE_3_PLUS_AE in ae_gen
    assert AttributeType.CRS in ae_gen  # Specific AEs block
    assert AttributeType.IRR in ae_gen


def test_identification_includes_line_of_treatment() -> None:
    ident = FAMILY_TO_ATTRIBUTES[AttributeFamily.IDENTIFICATION]
    assert AttributeType.LINE_OF_TREATMENT in ident
    assert AttributeType.NCT_NUMBER in ident


def test_all_12_families_present() -> None:
    for fam in AttributeFamily:
        assert fam in FAMILY_TO_ATTRIBUTES, f"missing prompt mapping for {fam}"
