"""Derivation of `clinical_trials.cancer_type` from a trial's own conditions.

Every expected value here was checked against the production row for the NCT id
named in the test. The old behaviour derived the label from the ClinicalTrials.gov
search term instead, and `query.cond=Cutaneous melanoma` returns 3708 of the 3746
melanoma studies on the registry, so it tagged every uveal/acral/mucosal trial as
cutaneous as well.
"""

from src.infrastructure.clinical_trials.cancer_type_derivation import (
    derive_cancer_types,
)

CUTANEOUS = "Cutaneous Melanoma"
UVEAL = "Uveal Melanoma"
ACRAL = "Acral Melanoma"
MUCOSAL = "Mucosal Melanoma"
BCC = "Basal Cell Carcinoma"
CSCC = "Cutaneous Squamous Cell Carcinoma"
MERKEL = "Merkel Cell Carcinoma"
BRAIN_CNS = "Cutaneous Melanoma with Brain/CNS Metastasis"


# ---------------------------------------------------------------------------
# The original bug: a subtype string must not also feed the generic bucket.
# ---------------------------------------------------------------------------


def test_metastatic_uveal_melanoma_is_uveal_only():
    """NCT06581406. Stored value was ['Cutaneous Melanoma', 'Uveal Melanoma']."""
    result = derive_cancer_types(["Metastatic Uveal Melanoma"])
    assert result.buckets == [UVEAL]


def test_uveal_melanoma_is_uveal_only():
    """NCT04589832. Stored value was ['Cutaneous Melanoma'] - the uveal tag was missing."""
    result = derive_cancer_types(["Uveal Melanoma"])
    assert result.buckets == [UVEAL]


def test_acral_melanoma_is_acral_only():
    result = derive_cancer_types(["Acral Melanoma"])
    assert result.buckets == [ACRAL]


def test_mucosal_melanoma_is_mucosal_only():
    result = derive_cancer_types(["Mucosal Melanoma"])
    assert result.buckets == [MUCOSAL]


def test_a_separate_generic_melanoma_string_still_earns_the_generic_bucket():
    """Two independent strings, so this trial genuinely spans both."""
    result = derive_cancer_types(["Cutaneous Melanoma", "Uveal Melanoma"])
    assert result.buckets == [CUTANEOUS, UVEAL]


# ---------------------------------------------------------------------------
# Subtype synonyms. MeSH has no descriptor for acral or mucosal melanoma, and
# uveal trials routinely say "ocular" or "choroidal" instead.
# ---------------------------------------------------------------------------


def test_choroidal_melanoma_is_uveal():
    """NCT01253759. 78 trials name uveal melanoma only via a synonym."""
    result = derive_cancer_types(["Choroidal Melanoma"])
    assert result.buckets == [UVEAL]


def test_ocular_melanoma_is_uveal():
    result = derive_cancer_types(["Ocular Melanoma"])
    assert result.buckets == [UVEAL]


def test_intraocular_melanoma_is_uveal():
    result = derive_cancer_types(["Intraocular Melanoma"])
    assert result.buckets == [UVEAL]


def test_anorectal_melanoma_is_mucosal():
    result = derive_cancer_types(["Anorectal Melanoma"])
    assert result.buckets == [MUCOSAL]


# ---------------------------------------------------------------------------
# Negation. A naive substring rule tags these with the subtype they exclude.
# ---------------------------------------------------------------------------


def test_melanoma_excluding_uveal_is_not_uveal():
    """NCT07406724. Stored value was ['Cutaneous Melanoma', 'Uveal Melanoma']."""
    result = derive_cancer_types(["Melanoma (Excluding Uveal Melanoma)"])
    assert result.buckets == [CUTANEOUS]


def test_non_melanoma_skin_cancer_does_not_earn_a_melanoma_bucket():
    result = derive_cancer_types(["Non-Melanoma Skin Cancer (NMSC)"])
    assert CUTANEOUS not in result.buckets


def test_non_melanomatous_skin_cancer_does_not_earn_a_melanoma_bucket():
    """82 corpus rows mention melanoma only inside a negated span."""
    result = derive_cancer_types(["Non-melanomatous Skin Cancer"])
    assert CUTANEOUS not in result.buckets


def test_unhyphenated_nonmelanoma_does_not_earn_a_melanoma_bucket():
    """'Nonmelanoma' is one word, so it never reaches the negation split."""
    result = derive_cancer_types(["Nonmelanoma Skin Cancers", "Basal Cell Carcinoma"])
    assert result.buckets == [BCC]


def test_negation_does_not_leak_a_basket_marker():
    """'Carcinoma, Non-Small-Cell Lung' must not read as the bare basket 'Carcinoma'.

    Dropping the text after a negation marker can leave a fragment that matches an
    anchored basket pattern. 24 corpus rows phrase NSCLC this way.
    """
    result = derive_cancer_types(["Carcinoma, Non-Small-Cell Lung"])
    assert result.is_basket is False


def test_negation_does_not_hide_a_non_skin_site_from_the_scc_rule():
    """The organ can sit after the negation marker, leaving an apparently bare SCC.

    Without reading the whole string, 'Squamous Cell Carcinoma, Non-Small Cell Lung'
    reduces to 'squamous cell carcinoma', which the skin context of a co-listed
    basal cell carcinoma would then wrongly promote to cutaneous SCC.
    """
    result = derive_cancer_types(
        ["Squamous Cell Carcinoma, Non-Small Cell Lung", "Basal Cell Carcinoma"]
    )
    assert CSCC not in result.buckets
    assert result.buckets == [BCC]


# ---------------------------------------------------------------------------
# Modifiers never change the bucket.
# ---------------------------------------------------------------------------


def test_stage_and_status_modifiers_do_not_change_the_bucket():
    for condition in (
        "Uveal Melanoma",
        "Metastatic Uveal Melanoma",
        "Recurrent Uveal Melanoma",
        "Stage IV Uveal Melanoma AJCC v7",
        "Unresectable Metastatic Uveal Melanoma",
    ):
        assert derive_cancer_types([condition]).buckets == [UVEAL], condition


# ---------------------------------------------------------------------------
# Basket trials. These are what the "Rare melanoma" search term dragged in.
# ---------------------------------------------------------------------------


def test_bare_cancer_earns_no_bucket_and_is_flagged_as_a_basket():
    """NCT00020579. Stored value was six buckets, derived from the word 'Cancer'."""
    result = derive_cancer_types(["Cancer"])
    assert result.buckets == []
    assert result.is_basket is True


def test_advanced_solid_tumor_earns_no_bucket():
    result = derive_cancer_types(["Advanced Solid Tumor"])
    assert result.buckets == []
    assert result.is_basket is True


def test_solid_disease_is_a_basket_however_the_sponsor_words_it():
    """Sponsors write 'solid' with tumour, cancer or neoplasm interchangeably."""
    for condition in (
        "Advanced Solid Tumor",
        "Advanced Solid Cancer",
        "Locally Advanced Solid Neoplasm",
        "Metastatic Malignant Solid Neoplasm",
        "Unresectable Solid Tumours",
    ):
        assert derive_cancer_types([condition]).is_basket is True, condition


def test_a_basket_trial_still_earns_buckets_it_explicitly_names():
    """A basket flag annotates; it must not suppress explicit evidence."""
    result = derive_cancer_types(
        [
            "Melanoma",
            "Solid Tumor",
            "CRAF Gene Amplification",
        ]
    )
    assert result.buckets == [CUTANEOUS]
    assert result.is_basket is True


# ---------------------------------------------------------------------------
# Squamous cell carcinoma is a histology, not a site.
# ---------------------------------------------------------------------------


def test_head_and_neck_squamous_is_not_cutaneous_scc():
    """NCT03421912."""
    result = derive_cancer_types(
        [
            "Head and Neck Squamous Cell Carcinoma",
            "Colorectal Cancer",
            "Non Small Cell Lung Cancer",
        ]
    )
    assert result.buckets == []


def test_bare_squamous_with_no_skin_context_earns_nothing():
    """NCT03025724. Nothing in the record says skin."""
    result = derive_cancer_types(["Squamous Cell Carcinoma"])
    assert result.buckets == []


def test_bare_squamous_alongside_other_skin_cancers_is_cutaneous_scc():
    """NCT05202860."""
    result = derive_cancer_types(
        [
            "Actinic Keratoses",
            "Basal Cell Carcinoma",
            "Squamous Cell Carcinoma",
        ]
    )
    assert result.buckets == [BCC, CSCC]


def test_a_named_non_skin_site_beats_skin_context():
    """NCT05219578. Skin context is present, but the SCC is head and neck."""
    result = derive_cancer_types(
        [
            "Non Small Cell Lung Cancer",
            "Cutaneous Melanoma",
            "Head and Neck Squamous Cell Carcinoma",
        ]
    )
    assert CSCC not in result.buckets
    assert CUTANEOUS in result.buckets


def test_explicitly_cutaneous_squamous_is_cutaneous_scc():
    result = derive_cancer_types(["Cutaneous Squamous Cell Carcinoma"])
    assert result.buckets == [CSCC]


def test_a_skin_cancer_basket_earns_each_named_skin_bucket():
    """Excerpt from NCT02978625, which lists 39 conditions."""
    result = derive_cancer_types(
        [
            "Merkel Cell Carcinoma",
            "Skin Basal Cell Carcinoma",
            "Skin Squamous Cell Carcinoma",
            "Skin Adnexal Carcinoma",
            "Sezary Syndrome",
            "Extramammary Paget Disease",
            "Porocarcinoma",
            "Squamous Cell Carcinoma of Unknown Primary",
        ]
    )
    assert result.buckets == [BCC, CSCC, MERKEL]
    assert result.is_basket is True


# ---------------------------------------------------------------------------
# Basal cell and Merkel.
# ---------------------------------------------------------------------------


def test_basal_cell_cancer_counts_as_basal_cell_carcinoma():
    result = derive_cancer_types(["Basal Cell Cancer"])
    assert result.buckets == [BCC]


def test_basal_cell_nevus_syndrome_is_not_a_carcinoma():
    result = derive_cancer_types(["Basal Cell Nevus Syndrome"])
    assert result.buckets == []


def test_merkel_cell_carcinoma():
    result = derive_cancer_types(["Refractory Merkel Cell Carcinoma"])
    assert result.buckets == [MERKEL]


# ---------------------------------------------------------------------------
# Brain/CNS is a site tag riding on a histology, never a bucket on its own.
# ---------------------------------------------------------------------------


def test_brain_metastasis_is_additive_to_a_melanoma_bucket():
    result = derive_cancer_types(["Melanoma", "Brain Metastases"])
    assert result.buckets == [CUTANEOUS, BRAIN_CNS]


def test_brain_metastasis_without_melanoma_earns_no_brain_bucket():
    result = derive_cancer_types(["Breast Cancer", "Brain Metastases"])
    assert BRAIN_CNS not in result.buckets


def test_excluded_brain_metastases_do_not_earn_the_brain_bucket():
    result = derive_cancer_types(["Melanoma", "Without Brain Metastases"])
    assert BRAIN_CNS not in result.buckets


# ---------------------------------------------------------------------------
# Flags.
# ---------------------------------------------------------------------------


def test_bare_melanoma_sets_melanoma_unspecified():
    """3140 of 3410 melanoma trials never say cutaneous or skin."""
    result = derive_cancer_types(["Metastatic Melanoma"])
    assert result.buckets == [CUTANEOUS]
    assert result.melanoma_unspecified is True


def test_explicitly_cutaneous_melanoma_is_not_unspecified():
    result = derive_cancer_types(["Cutaneous Melanoma"])
    assert result.melanoma_unspecified is False


def test_a_named_subtype_is_not_unspecified():
    result = derive_cancer_types(["Uveal Melanoma"])
    assert result.melanoma_unspecified is False


def test_a_trial_with_no_melanoma_is_not_unspecified():
    result = derive_cancer_types(["Basal Cell Carcinoma"])
    assert result.melanoma_unspecified is False


# ---------------------------------------------------------------------------
# Evidence and determinism.
# ---------------------------------------------------------------------------


def test_evidence_quotes_the_original_condition_string():
    result = derive_cancer_types(["Metastatic Uveal Melanoma"])
    assert result.evidence[UVEAL] == "Metastatic Uveal Melanoma"


def test_buckets_are_sorted_so_repeated_runs_compare_equal():
    result = derive_cancer_types(
        ["Uveal Melanoma", "Merkel Cell Carcinoma", "Basal Cell Carcinoma"]
    )
    assert result.buckets == sorted(result.buckets)


def test_derivation_is_idempotent():
    conditions = ["Melanoma", "Uveal Melanoma", "Basal Cell Carcinoma"]
    assert derive_cancer_types(conditions) == derive_cancer_types(conditions)


def test_empty_conditions_earn_nothing():
    result = derive_cancer_types([])
    assert result.buckets == []
    assert result.is_basket is False
    assert result.melanoma_unspecified is False
