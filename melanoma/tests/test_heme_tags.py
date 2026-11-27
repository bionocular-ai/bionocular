"""The committed ASH trial -> heme cancer tag file the nightly sync reads."""

import re

from src.infrastructure.clinical_trials.heme_tags import load_heme_tags


def test_load_heme_tags_splits_names(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(
        "nct_id,cancer_types\nNCT1,Acute Myeloid Leukemia;Allogeneic Transplant / GVHD\n"
    )
    assert load_heme_tags(p) == {
        "NCT1": ["Acute Myeloid Leukemia", "Allogeneic Transplant / GVHD"]
    }


def test_committed_file_covers_the_ash_trials():
    tags = load_heme_tags()
    assert len(tags) == 679
    assert "NCT06681922" not in tags  # an alias; the resolver swaps it
    assert tags["NCT05289167"] == ["Acute Myeloid Leukemia"]
    assert all(re.fullmatch(r"NCT\d{8}", n) for n in tags)
    assert all(tags.values())
