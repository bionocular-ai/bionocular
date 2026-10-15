"""Row selection and shaping for the landing page's Survival chart export.

The landing page labels the published CheckMate 067 medians next to curves drawn from
these twins, so the export must pick the right arms and refuse twins that no longer
cross 50% near those medians.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.export_landing_km import BG_ARMS, build


def _row(
    nct: str,
    arm: str,
    median: float,
    *,
    ref: str = "N Engl J Med 2019;381:1535-46.",
    comparison: str = "02",
    tail: float = 70.0,
) -> dict[str, Any]:
    coords = [
        {"time": 0.0, "surv": 100.0},
        {"time": median - 0.2, "surv": 55.0},
        {"time": median, "surv": 49.94},
        {"time": tail, "surv": 30.0},
    ]
    return {
        "nct_id": nct,
        "reference": ref,
        "comparison_label": comparison,
        "arm_name": arm,
        "endpoint": "PFS",
        "twin_coords": coords,
    }


def _rows(**override: float) -> list[dict[str, Any]]:
    medians = {
        "nivolumab_plus_ipilimumab": 11.46,
        "nivolumab": 7.11,
        "ipilimumab": 3.08,
        **override,
    }
    main = [_row("NCT01844505", arm, m) for arm, m in medians.items()]
    other_ref = _row(
        "NCT01844505", "nivolumab", 5.0, ref="N Engl J Med 2017;377:1345-56."
    )
    bg = [_row(nct, arm, 8.0) for nct, arm in BG_ARMS.items()]
    return [*main, other_ref, *bg]


def test_picks_the_2019_comparison_02_arms_in_chart_order() -> None:
    out = build(_rows())
    assert list(out["main"]) == ["nivolumab_plus_ipilimumab", "nivolumab", "ipilimumab"]
    assert out["main"]["nivolumab"][2] == [7.11, 49.9]


def test_cuts_points_after_60_months_but_counts_every_stored_point() -> None:
    out = build(_rows())
    assert all(t <= 60 for pts in out["main"].values() for t, _ in pts)
    assert out["stored"] == 12


def test_includes_one_background_curve_per_other_trial() -> None:
    out = build(_rows())
    assert [b["nct"] for b in out["bg"]] == list(BG_ARMS)


def test_refuses_twins_whose_median_drifted_from_the_published_label() -> None:
    with pytest.raises(AssertionError):
        build(_rows(nivolumab=9.0))
